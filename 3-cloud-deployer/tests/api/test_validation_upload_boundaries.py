"""HTTP contract tests for bounded validation uploads."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import rest_api


client = TestClient(rest_api.app)


@pytest.mark.parametrize(
    ("module_name", "path", "files"),
    [
        (
            "validation_artifacts",
            "/validate/config/config",
            {"file": ("config.json", b"12345", "application/json")},
        ),
        (
            "validation_artifacts",
            "/validate/state-machine?provider=aws",
            {"file": ("workflow.json", b"12345", "application/json")},
        ),
        (
            "validation_artifacts",
            "/validate/function-code?provider=aws",
            {"file": ("handler.py", b"12345", "text/x-python")},
        ),
        (
            "validation_twin",
            "/validate/hierarchy?provider=aws",
            {"file": ("hierarchy.json", b"12345", "application/json")},
        ),
        (
            "validation_twin",
            "/validate/user-config?provider=aws",
            {"file": ("config_user.json", b"12345", "application/json")},
        ),
        (
            "validation_twin",
            "/validate/scene-config?provider=aws",
            {"scene_file": ("scene.json", b"12345", "application/json")},
        ),
        (
            "validation_payloads",
            "/validate/simulator/payloads",
            {"file": ("payloads.json", b"12345", "application/json")},
        ),
        (
            "validation_payloads",
            "/validate/payloads-with-devices",
            {
                "payloads_file": ("payloads.json", b"12345", "application/json"),
                "devices_file": ("devices.json", b"[]", "application/json"),
            },
        ),
    ],
)
def test_validation_uploads_are_rejected_at_the_route_boundary(
    module_name,
    path,
    files,
):
    with patch(f"src.api.{module_name}.MAX_VALIDATION_UPLOAD_BYTES", 4):
        response = client.post(path, files=files)

    assert response.status_code == 413
    assert response.json()["detail"] == "File too large. Maximum allowed size is 4 bytes."
