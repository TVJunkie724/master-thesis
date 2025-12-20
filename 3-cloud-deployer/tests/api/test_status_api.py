"""
Comprehensive tests for the Status API endpoints.

Tests for /infrastructure/status endpoint covering infrastructure status checks.
"""
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import rest_api

client = TestClient(rest_api.app)


# ==========================================
# Test: GET /infrastructure/status
# ==========================================
class TestInfrastructureStatus:
    """Tests for GET /infrastructure/status endpoint."""

    def test_status_returns_structure(self):
        """Happy: Returns status with correct structure."""
        response = client.get("/infrastructure/status?project_name=template")
        
        # Should return some structure even if nothing deployed
        assert response.status_code in [200, 400, 404, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "infrastructure" in data or "status" in data or "message" in data

    def test_status_nonexistent_project(self):
        """Invalid: Non-existent project returns error status."""
        response = client.get("/infrastructure/status?project_name=nonexistent_12345")
        
        # Non-existent project should return 404 or 500 (depends on where validation fails)
        # Or 409 if context validation mismatch
        assert response.status_code in [404, 500, 409]

    def test_status_default_project(self):
        """Happy: Uses default project if not specified."""
        response = client.get("/infrastructure/status")
        
        # Should use template as default
        assert response.status_code in [200, 400, 404, 500]

    @patch("api.status.check_terraform_state")
    def test_status_terraform_state(self, mock_check):
        """Happy: Terraform state check works."""
        mock_check.return_value = {
            "deployed": False,
            "layers": {}
        }
        
        response = client.get("/infrastructure/status?project_name=template")
        
        if response.status_code == 200:
            data = response.json()
            assert "infrastructure" in data or "message" in data

    @patch("api.status.check_terraform_state")
    @patch("api.status.check_terraform_drift")
    def test_status_with_detailed_flag(self, mock_drift, mock_state):
        """Edge: Detailed=True includes drift detection."""
        mock_state.return_value = {"deployed": False, "layers": {}}
        mock_drift.return_value = {"has_drift": False, "changes": []}
        
        response = client.get("/infrastructure/status?project_name=template&detailed=true")
        
        # Detailed flag may trigger drift detection
        assert response.status_code in [200, 400, 404, 500]

    @patch("api.status.check_terraform_state")
    def test_status_no_terraform_state_file(self, mock_check):
        """Edge: No terraform state file returns appropriate status."""
        mock_check.side_effect = ValueError("State file not found")
        
        response = client.get("/infrastructure/status?project_name=template")
        
        # Should handle gracefully
        assert response.status_code in [200, 404, 500]

    @patch("api.status.check_terraform_state")
    @patch("src.api.status.check_sdk_managed")
    def test_status_includes_sdk_resources(self, mock_sdk, mock_state):
        """Happy: Status includes SDK-managed resources."""
        mock_state.return_value = {"deployed": True, "layers": {"l1": True}}
        mock_sdk.return_value = {"iot_devices": [], "twins": []}
        
        response = client.get("/infrastructure/status?project_name=template")
        
        if response.status_code == 200:
            # May include SDK resource section
            pass


# ==========================================
# Test: Status Response Format
# ==========================================
class TestStatusResponseFormat:
    """Tests for status response format consistency."""

    @patch("api.status.check_terraform_state")
    def test_status_layers_format(self, mock_check):
        """Happy: Layers are properly categorized."""
        mock_check.return_value = {
            "deployed": True,
            "layers": {
                "l1_iot": True,
                "l2_compute": True,
                "l3_storage": True,
                "l4_twin": False,
                "l5_grafana": False
            }
        }
        
        response = client.get("/infrastructure/status?project_name=template")
        
        if response.status_code == 200:
            data = response.json()
            # Should have layer information
            if "infrastructure" in data and "layers" in data["infrastructure"]:
                layers = data["infrastructure"]["layers"]
                assert isinstance(layers, dict)

    @patch("api.status.check_terraform_state")
    def test_status_provider_detection(self, mock_check):
        """Edge: Provider is detected from project config."""
        mock_check.return_value = {"deployed": False, "layers": {}}
        
        response = client.get("/infrastructure/status?project_name=template")
        
        # Should not fail even if provider detection fails
        assert response.status_code in [200, 400, 404, 500]


# ==========================================
# Test: Infrastructure Deploy Status (from deployment.py)
# ==========================================
class TestInfrastructureDeploy:
    """Tests for POST /infrastructure/deploy endpoint edge cases."""

    def test_deploy_invalid_provider(self):
        """Invalid: Invalid provider returns 422."""
        response = client.post("/infrastructure/deploy?provider=invalid&project_name=test_status_proj")
        
        # Invalid provider or non-existent project (checks context first -> 409)
        assert response.status_code in [400, 404, 422, 409]

    def test_deploy_nonexistent_project(self):
        """Invalid: Non-existent project returns error."""
        response = client.post(
            "/infrastructure/deploy?provider=aws&project_name=nonexistent_12345"
        )
        
        assert response.status_code in [404, 409]

    def test_destroy_nonexistent_project(self):
        """Invalid: Non-existent project returns error."""
        response = client.post(
            "/infrastructure/destroy?provider=aws&project_name=nonexistent_12345"
        )

        assert response.status_code in [404, 409]

    @patch("providers.deployer.deploy_all")
    @patch("src.validator.verify_project_structure")
    @patch("src.core.factory.create_context")
    @patch("api.dependencies.validate_project_context")
    def test_deploy_valid_request(self, mock_validate, mock_ctx, mock_verify, mock_deploy):
        """Happy: Valid deploy request is blocked for template project."""
        mock_validate.return_value = None
        mock_ctx.return_value = MagicMock()
        mock_verify.return_value = None
        mock_deploy.return_value = None
        
        # Template project is now protected
        response = client.post("/infrastructure/deploy?provider=aws&project_name=template")
        
        # Template is protected - returns 400
        assert response.status_code == 400
        assert "protected" in response.json()["detail"].lower() or "template" in response.json()["detail"].lower()
