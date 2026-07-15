"""Project file browser API boundary tests."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import constants as CONSTANTS
import rest_api
from src.core.project_storage import ProjectStorage
import src.api.projects as project_routes


client = TestClient(rest_api.app)


@pytest.fixture
def project_storage(tmp_path, monkeypatch):
    storage = ProjectStorage(tmp_path)
    project_name = "test_api_files"
    project_dir = storage.deployment_project_path(project_name)
    project_dir.mkdir(parents=True)
    (project_dir / CONSTANTS.CONFIG_CREDENTIALS_FILE).write_text(
        json.dumps({"aws": {"aws_secret_access_key": "do-not-expose"}}),
        encoding="utf-8",
    )
    (project_dir / "config_credentials.json.example").write_text(
        json.dumps({"aws": {"aws_access_key_id": "example"}}),
        encoding="utf-8",
    )
    (project_dir / CONSTANTS.CONFIG_FILE).write_text(
        json.dumps({"digital_twin_name": project_name}),
        encoding="utf-8",
    )
    monkeypatch.setattr(project_routes, "get_project_storage", lambda: storage)
    return project_name


def test_project_file_tree_hides_runtime_credentials(project_storage):
    response = client.get(f"/projects/{project_storage}/files")

    assert response.status_code == 200
    paths = {
        item["path"] for item in response.json()["files"] if item["type"] == "file"
    }
    assert "config_credentials.json" not in paths
    assert "config_credentials.json.example" in paths


def test_project_file_content_blocks_runtime_credentials(project_storage):
    response = client.get(f"/projects/{project_storage}/files/config_credentials.json")

    assert response.status_code == 403
    assert "protected" in response.json()["detail"]


def test_project_file_content_allows_credential_examples(project_storage):
    response = client.get(
        f"/projects/{project_storage}/files/config_credentials.json.example"
    )

    assert response.status_code == 200
    assert response.json()["content"]["aws"]["aws_access_key_id"] == "example"


def test_project_import_rejects_oversized_upload_before_processing(
    monkeypatch,
):
    class ExistingStorage:
        @staticmethod
        def exists(_project_name):
            return True

    update_called = False

    def unexpected_update(*_args, **_kwargs):
        nonlocal update_called
        update_called = True

    monkeypatch.setattr(project_routes, "get_project_storage", ExistingStorage)
    monkeypatch.setattr(project_routes, "MAX_COMPRESSED_ARCHIVE_BYTES", 8)
    monkeypatch.setattr(
        project_routes.file_manager,
        "update_project_from_zip",
        unexpected_update,
    )

    response = client.post(
        "/projects/test/import",
        files={"file": ("project.zip", b"123456789", "application/zip")},
    )

    assert response.status_code == 413
    assert update_called is False


def test_operation_package_endpoint_stages_token_and_persists_project_definition(
    monkeypatch,
):
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


def test_operation_package_endpoint_discards_stage_when_definition_update_fails(
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


def test_project_delete_invalidates_operation_packages_before_storage(monkeypatch):
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
        project_routes, "get_operation_package_store", FakeOperationStore
    )
    monkeypatch.setattr(
        project_routes, "get_runtime_state_store", FakeRuntimeStateStore
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


def test_project_delete_rejects_active_operation(monkeypatch):
    class ActiveOperationStore:
        @staticmethod
        def discard_project(_project_name):
            raise project_routes.OperationPackageInUseError(
                "Project has an active deployment operation"
            )

    monkeypatch.setattr(
        project_routes, "get_operation_package_store", ActiveOperationStore
    )

    response = client.delete("/projects/test_operation")

    assert response.status_code == 409
    assert response.json()["detail"] == "Project has an active deployment operation"
