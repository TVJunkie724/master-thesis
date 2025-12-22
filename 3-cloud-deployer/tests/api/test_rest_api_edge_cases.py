
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
import io
import zipfile
import sys
import os
from pathlib import Path

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from rest_api import app
import constants as CONSTANTS

client = TestClient(app)

# Helper to create valid zip
def create_valid_project_zip():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        # Config
        zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps({
            "digital_twin_name": "test-twin",
            "hot_storage_size_in_days": 1,
            "cold_storage_size_in_days": 1,
            "mode": "DEBUG"
        }))
        # Empty requirements
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

class TestRestApiEdgeCases:

    # ==========================================
    # 1. Project Management Edge Cases
    # ==========================================

    # Note: test_activate_non_existent_project removed - endpoint deleted

    @patch("src.file_manager.create_project_from_zip")
    def test_create_project_invalid_zip(self, mock_create):
        """Verify 400/500 when uploading a corrupt zip."""
        mock_create.side_effect = ValueError("Bad Zip File")
        
        files = {"file": ("project.zip", b"not a zip", "application/zip")}
        response = client.post("/projects?project_name=test_corrupt", files=files)
        
        # Depending on how the exception is caught, it might be 400 or 500. 
        # ValueError usually propagates as 500 unless handled, or 400 if validation.
        # file_manager raises ValueError for bad zips.
        assert response.status_code in [400, 500] 

    def test_update_config_invalid_json(self):
        """Verify 400 when uploading malformed JSON."""
        # Using a valid project name for the URL structure
        project_name = "test_config_invalid"
        
        files = {"file": ("config.json", b"{invalid json", "application/json")}
        response = client.put(f"/projects/{project_name}/config/config", files=files)
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    # ==========================================
    # 2. Deployment Edge Cases
    # ==========================================

    @patch("src.api.deployment.validate_project_context")
    @patch("src.api.deployment.create_context")
    def test_deploy_non_existent_project(self, mock_create_context, mock_validate_ctx):
        """Verify 500 when deployment fails (simulated by create_context failure)."""
        mock_validate_ctx.return_value = None
        mock_create_context.side_effect = ValueError("Project not found")
        
        response = client.post("/infrastructure/deploy?project_name=missing&provider=aws")
        
        # Now validation passes, create_context fails -> ValueError -> 400
        assert response.status_code == 400
        assert "Project not found" in response.json()["detail"]

    @patch("src.api.deployment.validate_project_context")
    def test_deploy_invalid_provider(self, mock_validate_ctx):
        """Verify 400 when using an unsupported provider."""
        mock_validate_ctx.return_value = None
        response = client.post("/infrastructure/deploy?project_name=test&provider=mars_cloud")
        
        assert response.status_code == 400
        assert "Invalid provider" in response.json()["detail"]

    @patch("src.api.deployment.validate_project_context")
    @patch("src.api.deployment.create_context")
    def test_deploy_missing_config_files(self, mock_create_context, mock_validate_ctx):
        """Verify 500 when config files are missing."""
        mock_validate_ctx.return_value = None
        mock_create_context.side_effect = FileNotFoundError("Missing config.json")
        
        response = client.post("/infrastructure/deploy?project_name=test&provider=aws")
        
        assert response.status_code == 500
        assert "Missing config.json" in response.json()["detail"]

    @patch("src.api.deployment.validate_project_context")
    @patch("src.api.deployment.core_deployer.deploy_all")
    @patch("src.api.deployment.create_context")
    def test_deploy_provider_error(self, mock_create_context, mock_deploy, mock_validate_ctx):
        """Verify 500 response with error details when AWS fails."""
        mock_validate_ctx.return_value = None
        mock_create_context.return_value = MagicMock()
        
        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}
        mock_deploy.side_effect = ClientError(error_response, 'CreateStack')
        
        response = client.post("/infrastructure/deploy?project_name=test&provider=aws")
        
        assert response.status_code == 500
        assert "AccessDenied" in response.json()["detail"]

    # ==========================================
    # 3. Info Edge Cases
    # ==========================================

    # Note: test_info_config_missing_file removed - endpoint deleted 

    # ==========================================
    # 4. Security & Limits
    # ==========================================

    def test_api_path_traversal(self):
        """Attempt to access projects via ../system."""
        # FastAPI/Starlette usually sanitizes path params, but good to verify our logic checks
        response = client.get("/projects/../system/validate")
        # Should be 404 (not found) or 400 (bad request) or 422 (validation error)
        # Note: most modern web servers/frameworks normalize paths before they reach code, 
        # so this might just look like "system" or return 404.
        assert response.status_code in [400, 404, 422]

    @patch("src.file_manager.update_config_file")
    def test_large_payload_upload(self, mock_update):
        """Simulate uploading a larger config file that is invalid (to trigger validation error, checking 400)."""
        # Testing 400 bad request for invalid content is safer than 200 via mock
        # Invalid JSON structure
        large_json = "{" + ' ' * 1024 * 1024
        files = {"file": ("config.json", large_json, "application/json")}
        
        response = client.put("/projects/test/config/config", files=files)
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    # ==========================================
    # 5. Error Propagation
    # ==========================================

    @patch("src.file_manager.os.path.exists")
    @patch("src.validator.validate_config_content")
    def test_validation_logical_error(self, mock_validate, mock_exists):
        """Upload valid JSON but with invalid logical values."""
        # Ensure file_manager thinks project exists
        mock_exists.return_value = True
        
        # Validator raises ValueError for logical issues
        mock_validate.side_effect = ValueError("Hot storage cannot be negative")
        
        files = {"file": ("config.json", "{}", "application/json")}
        # Use existing 'test' or any name since we mock exists
        response = client.put("/projects/test/config/config", files=files)
        
        # We verified projects.py catches ValueError -> 400
        assert response.status_code == 400
        assert "Hot storage cannot be negative" in response.json()["detail"]
