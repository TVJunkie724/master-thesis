"""Project file browser API boundary tests."""

import json
import os

from fastapi.testclient import TestClient

import constants as CONSTANTS
import rest_api
import src.core.state as state


client = TestClient(rest_api.app)


def _create_test_project(project_name: str) -> str:
    project_dir = os.path.join(
        state.get_project_upload_path(),
        project_name,
    )
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE), "w") as f:
        json.dump({"aws": {"aws_secret_access_key": "do-not-expose"}}, f)
    with open(os.path.join(project_dir, "config_credentials.json.example"), "w") as f:
        json.dump({"aws": {"aws_access_key_id": "example"}}, f)
    with open(os.path.join(project_dir, CONSTANTS.CONFIG_FILE), "w") as f:
        json.dump({"digital_twin_name": project_name}, f)
    return project_dir


def test_project_file_tree_hides_runtime_credentials():
    _create_test_project("test_api_files")

    response = client.get("/projects/test_api_files/files")

    assert response.status_code == 200
    paths = {item["path"] for item in response.json()["files"] if item["type"] == "file"}
    assert "config_credentials.json" not in paths
    assert "config_credentials.json.example" in paths


def test_project_file_content_blocks_runtime_credentials():
    _create_test_project("test_api_files")

    response = client.get("/projects/test_api_files/files/config_credentials.json")

    assert response.status_code == 403
    assert "protected" in response.json()["detail"]


def test_project_file_content_allows_credential_examples():
    _create_test_project("test_api_files")

    response = client.get("/projects/test_api_files/files/config_credentials.json.example")

    assert response.status_code == 200
    assert response.json()["content"]["aws"]["aws_access_key_id"] == "example"
