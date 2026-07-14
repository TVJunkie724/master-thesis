"""Project file browser API boundary tests."""

import json

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
    paths = {item["path"] for item in response.json()["files"] if item["type"] == "file"}
    assert "config_credentials.json" not in paths
    assert "config_credentials.json.example" in paths


def test_project_file_content_blocks_runtime_credentials(project_storage):
    response = client.get(
        f"/projects/{project_storage}/files/config_credentials.json"
    )

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
