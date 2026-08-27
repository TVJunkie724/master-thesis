"""Bounded Twin deployment-workspace API tests."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import rest_api
import src.api.projects as project_routes

client = TestClient(rest_api.app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/projects"),
        ("POST", "/projects"),
        ("GET", "/projects/twin/validate"),
        ("GET", "/projects/twin/config/config"),
        ("PUT", "/projects/twin/config/config"),
        ("POST", "/projects/twin/import"),
        ("GET", "/projects/twin/export"),
        ("GET", "/projects/twin/summary"),
        ("GET", "/projects/twin/files"),
        ("GET", "/projects/twin/files/config.json"),
        ("PATCH", "/projects/twin/info"),
        ("PUT", "/projects/twin/state_machines/aws"),
        ("PUT", "/projects/twin/simulator/payloads"),
        ("DELETE", "/projects/twin/cleanup/aws-twinmaker"),
    ],
)
def test_product_style_project_surfaces_are_not_routed(method, path):
    response = client.request(method, path)

    assert response.status_code == 404


def test_operation_package_rejects_oversized_upload_before_processing(
    monkeypatch,
):
    stage_called = False

    class FakeStore:
        @staticmethod
        def stage(_project_name, _content):
            nonlocal stage_called
            stage_called = True

    monkeypatch.setattr(project_routes, "get_operation_package_store", FakeStore)
    monkeypatch.setattr(project_routes, "MAX_COMPRESSED_ARCHIVE_BYTES", 8)

    response = client.post(
        "/projects/test/operation-package",
        files={"file": ("project.zip", b"123456789", "application/zip")},
    )

    assert response.status_code == 413
    assert stage_called is False


def test_operation_package_stages_token_and_persists_definition(monkeypatch):
    calls = []

    class FakeStore:
        def stage(self, project_name, content):
            calls.append(("stage", project_name, content))
            return SimpleNamespace(
                token="opaque-operation-token",
                expires_at=datetime(2026, 7, 14, tzinfo=timezone.utc),
                warnings=["stage warning"],
            )

        def discard(self, token):
            calls.append(("discard", token))

    class MissingStorage:
        @staticmethod
        def exists(_project_name):
            return False

    monkeypatch.setattr(project_routes, "get_operation_package_store", FakeStore)
    monkeypatch.setattr(project_routes, "get_project_storage", MissingStorage)
    monkeypatch.setattr(
        project_routes.file_manager,
        "create_project_from_zip",
        lambda project_name, content: {
            "project_name": project_name,
            "warnings": ["definition warning"],
        },
    )

    response = client.post(
        "/projects/test_operation/operation-package",
        files={"file": ("project.zip", b"deployment-package", "application/zip")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_name": "test_operation",
        "operation_token": "opaque-operation-token",
        "expires_at": "2026-07-14T00:00:00+00:00",
        "warnings": ["definition warning", "stage warning"],
    }
    assert calls == [("stage", "test_operation", b"deployment-package")]


def test_operation_package_discards_stage_when_definition_update_fails(
    monkeypatch,
):
    discarded = []

    class FakeStore:
        @staticmethod
        def stage(_project_name, _content):
            return SimpleNamespace(
                token="opaque-operation-token",
                expires_at=datetime(2026, 7, 14, tzinfo=timezone.utc),
                warnings=[],
            )

        @staticmethod
        def discard(token):
            discarded.append(token)

    class ExistingStorage:
        @staticmethod
        def exists(_project_name):
            return True

    def failing_update(_project_name, _content):
        raise ValueError("invalid definition")

    monkeypatch.setattr(project_routes, "get_operation_package_store", FakeStore)
    monkeypatch.setattr(project_routes, "get_project_storage", ExistingStorage)
    monkeypatch.setattr(
        project_routes.file_manager,
        "update_project_from_zip",
        failing_update,
    )

    response = client.post(
        "/projects/test_operation/operation-package",
        files={"file": ("project.zip", b"deployment-package", "application/zip")},
    )

    assert response.status_code == 400
    assert discarded == ["opaque-operation-token"]


def test_workspace_delete_invalidates_packages_before_storage(monkeypatch):
    calls = []

    class FakeOperationStore:
        @staticmethod
        def discard_project(project_name):
            calls.append(("discard_packages", project_name))

    class FakeRuntimeStateStore:
        @staticmethod
        def delete(project_name):
            calls.append(("delete_state", project_name))

    monkeypatch.setattr(
        project_routes,
        "get_operation_package_store",
        FakeOperationStore,
    )
    monkeypatch.setattr(
        project_routes,
        "get_runtime_state_store",
        FakeRuntimeStateStore,
    )
    monkeypatch.setattr(
        project_routes.file_manager,
        "delete_project",
        lambda project_name: calls.append(("delete_project", project_name)),
    )

    response = client.delete("/projects/test_operation")

    assert response.status_code == 200
    assert calls == [
        ("discard_packages", "test_operation"),
        ("delete_project", "test_operation"),
        ("delete_state", "test_operation"),
    ]


def test_workspace_delete_rejects_active_operation(monkeypatch):
    class ActiveOperationStore:
        @staticmethod
        def discard_project(_project_name):
            raise project_routes.OperationPackageInUseError(
                "Project has an active deployment operation"
            )

    monkeypatch.setattr(
        project_routes,
        "get_operation_package_store",
        ActiveOperationStore,
    )

    response = client.delete("/projects/test_operation")

    assert response.status_code == 409
    assert response.json()["detail"] == "Project has an active deployment operation"
