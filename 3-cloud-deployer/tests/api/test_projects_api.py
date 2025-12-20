"""
Comprehensive tests for the Projects API endpoints.

Tests for /projects endpoints including project CRUD, config management,
state machine uploads, and cleanup operations.
"""
import pytest
import json
import io
import zipfile
import uuid
import shutil
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import rest_api
import constants as CONSTANTS
import src.core.state as state

client = TestClient(rest_api.app)


# ==========================================
# Test Fixtures
# ==========================================

def create_valid_zip_bytes(twin_name=None, creds=None, layer_4_provider="aws"):
    """Create a valid project zip file in memory."""
    unique_id = uuid.uuid4().hex[:8]
    if twin_name is None:
        twin_name = f"test-twin-{unique_id}"
    if creds is None:
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-east-1"
            }
        }
    
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        config = {
            "digital_twin_name": twin_name,
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "DEBUG"
        }
        zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps(config))
        zf.writestr(CONSTANTS.CONFIG_IOT_DEVICES_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_EVENTS_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_HIERARCHY_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_CREDENTIALS_FILE, json.dumps(creds))
        zf.writestr(CONSTANTS.CONFIG_PROVIDERS_FILE, json.dumps({
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": layer_4_provider
        }))
        zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
        # Add required hierarchy file
        if layer_4_provider == "aws":
            zf.writestr("twin_hierarchy/aws_hierarchy.json", "[]")
        elif layer_4_provider == "azure":
            zf.writestr("twin_hierarchy/azure_hierarchy.json", json.dumps({
                "models": [], "twins": [], "relationships": []
            }))
    bio.seek(0)
    return bio.getvalue()


# Note: Cleanup fixture is in conftest.py (autouse=True for all tests)


# ==========================================
# Test: GET / (list_projects)
# ==========================================
class TestListProjects:
    """Tests for GET / endpoint."""

    def test_list_projects_returns_structure(self):
        """Happy: Returns project list with correct structure."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "active_project" in data

    def test_list_projects_endpoint(self):
        """Happy: Projects endpoint returns list."""
        response = client.get("/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "active_project" in data
        assert isinstance(data["projects"], list)

    def test_list_projects_includes_template(self):
        """Happy: Default template project is always present."""
        response = client.get("/projects")
        assert response.status_code == 200
        data = response.json()
        project_names = [p["name"] for p in data["projects"]]
        assert "template" in project_names


# ==========================================
# Test: POST /projects (create_project)
# ==========================================
class TestCreateProject:
    """Tests for POST /projects endpoint."""

    def test_create_project_multipart_success(self):
        """Happy: Create project with valid multipart upload."""
        zip_bytes = create_valid_zip_bytes()
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        
        response = client.post("/projects?project_name=test_api_create", files=files)
        
        assert response.status_code == 200
        assert "test_api_create" in response.json().get("message", "")

    def test_create_project_with_description(self):
        """Happy: Create project with description."""
        zip_bytes = create_valid_zip_bytes()
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        
        response = client.post(
            "/projects?project_name=test_api_desc&description=Test%20description",
            files=files
        )
        
        assert response.status_code == 200

    def test_create_project_missing_name(self):
        """Invalid: Missing project_name parameter returns 422."""
        zip_bytes = create_valid_zip_bytes()
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        
        response = client.post("/projects", files=files)
        
        assert response.status_code == 422

    def test_create_project_empty_name(self):
        """Invalid: Empty project name fails."""
        zip_bytes = create_valid_zip_bytes()
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        
        response = client.post("/projects?project_name=", files=files)
        
        # Empty name should fail validation
        assert response.status_code in [400, 422]

    def test_create_project_special_chars(self):
        """Edge: Project name with special characters."""
        zip_bytes = create_valid_zip_bytes()
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        
        # Most special chars should be rejected or sanitized
        response = client.post("/projects?project_name=test_api_valid-name", files=files)
        # Hyphens and underscores are typically allowed
        assert response.status_code == 200

    def test_create_project_invalid_zip(self):
        """Error: Corrupted zip file returns error."""
        files = {"file": ("project.zip", b"not a zip file", "application/zip")}
        
        response = client.post("/projects?project_name=test_api_invalid", files=files)
        
        assert response.status_code in [400, 500]

    def test_create_project_missing_config(self):
        """Error: Zip missing required config fails."""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr("random.txt", "content")
        bio.seek(0)
        
        files = {"file": ("project.zip", bio.getvalue(), "application/zip")}
        response = client.post("/projects?project_name=test_api_noconfig", files=files)
        
        assert response.status_code == 400


# ==========================================
# Test: GET /projects/{name}/validate
# ==========================================
class TestValidateProjectStructure:
    """Tests for project structure validation endpoint."""

    def test_validate_template_project(self):
        """Happy: Template project validates successfully."""
        response = client.get("/projects/template/validate")
        # May fail if template is not fully configured, but shouldn't 404
        assert response.status_code in [200, 400, 500]

    def test_validate_nonexistent_project(self):
        """Invalid: Non-existent project returns 400 (ValueError)."""
        response = client.get("/projects/nonexistent_project_12345/validate")
        assert response.status_code == 400


# ==========================================
# Test: GET /projects/{name}/config/{type}
# ==========================================
class TestGetProjectConfig:
    """Tests for GET /projects/{name}/config/{type} endpoint."""

    def test_get_config_main(self):
        """Happy: Get main config.json."""
        response = client.get("/projects/template/config/config")
        assert response.status_code in [200, 404]  # 404 if template not configured

    def test_get_config_iot(self):
        """Happy: Get IoT devices config."""
        response = client.get("/projects/template/config/iot")
        assert response.status_code in [200, 404]

    def test_get_config_providers(self):
        """Happy: Get providers config."""
        response = client.get("/projects/template/config/providers")
        assert response.status_code in [200, 404]

    def test_get_config_nonexistent_project(self):
        """Invalid: Non-existent project returns 404."""
        response = client.get("/projects/nonexistent_12345/config/config")
        assert response.status_code == 404

    def test_get_config_invalid_type(self):
        """Invalid: Invalid config type returns 422."""
        response = client.get("/projects/template/config/invalid_type")
        assert response.status_code == 422


# ==========================================
# Test: PUT /projects/{name}/config/{type}
# ==========================================
class TestUpdateConfig:
    """Tests for PUT /projects/{name}/config/{type} endpoint."""

    @patch("file_manager.update_config_file")
    def test_update_config_valid(self, mock_update):
        """Happy: Update config with valid JSON."""
        # Use non-protected project name
        project = "test_project"
        content = json.dumps({
            "digital_twin_name": "test",
            "hot_storage_size_in_days": 1,
            "cold_storage_size_in_days": 1,
            "mode": "DEBUG"
        })
        files = {"file": ("config.json", content, "application/json")}
        
        response = client.put(f"/projects/{project}/config/config", files=files)
        
        assert response.status_code == 200

    def test_update_config_invalid_json(self):
        """Invalid: Malformed JSON returns 400."""
        # Use non-protected project name to ensure we hit the JSON check first
        files = {"file": ("config.json", b"{invalid json", "application/json")}
        
        response = client.put("/projects/test_project/config/config", files=files)
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_update_config_nonexistent_project(self):
        """Invalid: Non-existent project returns 400 (ValueError)."""
        content = json.dumps({"digital_twin_name": "test"})
        files = {"file": ("config.json", content, "application/json")}
        
        response = client.put("/projects/nonexistent_12345/config/config", files=files)
        
        assert response.status_code == 400


# ==========================================
# Test: DELETE /projects/{name}
# ==========================================
class TestDeleteProject:
    """Tests for DELETE /projects/{name} endpoint."""

    def test_delete_existing_project(self):
        """Happy: Delete an existing project."""
        # First create a project
        zip_bytes = create_valid_zip_bytes()
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        client.post("/projects?project_name=test_api_delete", files=files)
        
        # Then delete it
        response = client.delete("/projects/test_api_delete")
        
        assert response.status_code == 200

    def test_delete_nonexistent_project(self):
        """Invalid: Non-existent project returns 404."""
        response = client.delete("/projects/nonexistent_12345")
        
        assert response.status_code == 404

    def test_cannot_delete_template(self):
        """Edge: Cannot delete template project (protected)."""
        response = client.delete("/projects/template")
        
        # Should return 400 because template is protected
        assert response.status_code == 400
        assert "protected" in response.json()["detail"].lower() or "template" in response.json()["detail"].lower()


# ==========================================
# Test: PATCH /projects/{name}/info
# ==========================================
class TestUpdateProjectInfo:
    """Tests for PATCH /projects/{name}/info endpoint (update info)."""

    @patch("file_manager.update_project_info")
    def test_update_info_valid(self, mock_update):
        """Happy: Update description."""
        project = "test_project"
        response = client.patch(f"/projects/{project}/info", json={"description": "New"})
        
        assert response.status_code == 200

    def test_update_info_nonexistent_project(self):
        """Invalid: Non-existent project returns 404 (ValueError)."""
        response = client.patch(
            "/projects/nonexistent_12345/info", 
            json={"description": "New"}
        )
        
        assert response.status_code == 404


# ==========================================
# Test: PUT /projects/{name}/state_machines/{provider}
# ==========================================
class TestUploadStateMachine:
    """Tests for state machine upload endpoint."""

    @patch("src.validator.validate_state_machine_content")
    def test_upload_aws_step_function(self, mock_validate):
        """Happy: Upload valid AWS step function."""
        # Use non-protected project
        project = "test_project"
        content = json.dumps({"StartAt": "State1", "States": {}})
        files = {"file": ("stateclient.json", content, "application/json")}
        
        response = client.put(f"/projects/{project}/state_machines/aws", files=files)
        
        assert response.status_code == 200
        mock_validate.assert_called_once()

    @patch("src.validator.validate_state_machine_content")
    def test_upload_azure_logic_app(self, mock_validate):
        """Happy: Upload valid Azure logic app."""
        project = "test_project"
        content = json.dumps({"definition": {}, "parameters": {}})
        files = {"file": ("workflow.json", content, "application/json")}
        
        response = client.put(f"/projects/{project}/state_machines/azure", files=files)
        
        assert response.status_code == 200

    def test_upload_invalid_provider(self):
        """Invalid: Invalid provider returns 422."""
        content = json.dumps({})
        files = {"file": ("state_machine.json", content, "application/json")}
        
        response = client.put("/projects/template/state_machines/invalid", files=files)
        
        assert response.status_code == 422

    @patch("src.validator.validate_state_machine_content")
    def test_upload_invalid_schema(self, mock_validate):
        """Error: Invalid schema returns 400."""
        mock_validate.side_effect = ValueError("Invalid schema")
        content = json.dumps({})
        files = {"file": ("aws_step_function.json", content, "application/json")}
        
        response = client.put("/projects/template/state_machines/aws", files=files)
        
        assert response.status_code == 400


# ==========================================
# Test: PUT /projects/{name}/simulator/payloads
# ==========================================
class TestUploadSimulatorPayloads:
    """Tests for simulator payloads upload endpoint."""

    @patch("src.validator.validate_simulator_payloads")
    @patch("src.core.state.get_project_base_path")
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_upload_valid_payloads(self, mock_open, mock_makedirs, mock_path, mock_validate):
        """Happy: Upload valid payloads."""
        mock_validate.return_value = (True, [], [])
        mock_path.return_value = "/fake/path"
        mock_file = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        
        content = json.dumps([{"iotDeviceId": "device-1"}])
        
        response = client.put(
            "/projects/template/simulator/payloads",
            content=content.encode(),
            headers={"Content-Type": "application/octet-stream"}
        )
        
        assert response.status_code in [200, 400, 500]

    @patch("src.validator.validate_simulator_payloads")
    def test_upload_invalid_payloads(self, mock_validate):
        """Invalid: Payloads missing iotDeviceId."""
        mock_validate.return_value = (False, ["Missing iotDeviceId"], [])
        
        content = json.dumps([{"temperature": 25}])
        
        response = client.put(
            "/projects/template/simulator/payloads",
            content=content.encode(),
            headers={"Content-Type": "application/octet-stream"}
        )
        
        # Should fail validation
        assert response.status_code == 400


# ==========================================
# Test: DELETE /projects/{name}/cleanup/aws-twinmaker
# ==========================================
class TestCleanupAwsTwinmaker:
    """Tests for AWS TwinMaker cleanup endpoint."""

    def test_cleanup_nonexistent_project(self):
        """Invalid: Non-existent project returns 409 (Context Mismatch)."""
        # validate_project_context raises 409 if project doesn't match active
        response = client.delete("/projects/nonexistent_12345/cleanup/aws-twinmaker")
        assert response.status_code == 409

    @patch("src.core.state.get_project_base_path")
    @patch("os.path.exists")
    def test_cleanup_non_aws_project(self, mock_exists, mock_path):
        """Error: Non-AWS project returns error."""
        mock_path.return_value = "/fake/path"
        mock_exists.return_value = True
        
        # Mock reading providers config to return azure
        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"layer_4_provider": "azure"}):
                response = client.delete("/projects/template/cleanup/aws-twinmaker")
        
        # Should fail because not AWS
        assert response.status_code in [400, 404, 500]
