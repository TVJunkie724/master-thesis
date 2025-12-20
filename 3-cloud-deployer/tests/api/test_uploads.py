
import pytest
import io
import zipfile
import json
import base64
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Adjust import based on your actual path
import rest_api 
import constants as CONSTANTS

client = TestClient(rest_api.app)

# Helper to create valid zip bytes
def create_valid_zip_bytes():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        # Minimal valid config content (based on recent user req)
        config_content = json.dumps({
            "digital_twin_name": "test-twin",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "DEBUG"
        })
        zf.writestr(CONSTANTS.CONFIG_FILE, config_content)
        # Add other required files as minimal empty jsons/lists
        for req in CONSTANTS.REQUIRED_CONFIG_FILES:
            if req != CONSTANTS.CONFIG_FILE:
                if req in [CONSTANTS.CONFIG_IOT_DEVICES_FILE, CONSTANTS.CONFIG_EVENTS_FILE, CONSTANTS.CONFIG_HIERARCHY_FILE]:
                     zf.writestr(req, "[]")
                elif req == CONSTANTS.CONFIG_OPTIMIZATION_FILE:
                     zf.writestr(req, json.dumps({"result": {}}))
                else:
                     zf.writestr(req, "{}")
                     
    bio.seek(0)
    return bio.getvalue()

@patch("file_manager.create_project_from_zip")
def test_create_project_binary(mock_create):
    """Test standard multipart upload"""
    zip_bytes = create_valid_zip_bytes()
    files = {"file": ("project.zip", zip_bytes, "application/zip")}
    
    response = client.post("/projects?project_name=test-bin", files=files)
    
    assert response.status_code == 200
    mock_create.assert_called_once()
    
@patch("file_manager.create_project_from_zip")
def test_create_project_base64(mock_create):
    """Test application/json base64 upload"""
    zip_bytes = create_valid_zip_bytes()
    b64_str = base64.b64encode(zip_bytes).decode('utf-8')
    
    payload = {
        "file_base64": b64_str,
        "filename": "project.zip"
    }
    
    response = client.post("/projects?project_name=test-b64", json=payload)
    assert response.status_code == 200
    mock_create.assert_called_once()

@patch("src.validator.validate_config_content")
def test_validate_config_binary(mock_val):
    """Test config validation with binary"""
    files = {"file": ("config.json", b"{}", "application/json")}
    response = client.post("/validate/config/config", files=files)
    assert response.status_code == 200
    mock_val.assert_called_once()

# NOTE: test_validate_config_base64 removed - /validate/config/{type} endpoint
# now only accepts file uploads, not JSON with base64.
# See test_validate_config_binary for the file upload test.

def test_invalid_base64_string():
    """Test invalid base64 string returns 400"""
    payload = {"file_base64": "not-a-valid-base64-string!!"}
    response = client.post("/projects?project_name=test-err", json=payload)
    assert response.status_code == 400
    assert "Invalid Base64" in response.json()["detail"]

def test_missing_base64_field():
    """Test json missing required field"""
    payload = {"other": "stuff"}
    response = client.post("/projects?project_name=test-err", json=payload)
    # The utility returns 400 if field missing
    assert response.status_code == 400
    assert "Missing 'file_base64'" in response.json()["detail"]
    
def test_unsupported_content_type():
    """Test text/plain"""
    response = client.post("/projects?project_name=test-err", content="raw text")
    assert response.status_code == 415
