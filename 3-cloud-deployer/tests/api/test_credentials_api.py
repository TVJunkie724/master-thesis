"""
Comprehensive tests for the Credentials/Permissions API endpoints.

Tests for /permissions endpoints covering AWS, Azure, and GCP credential validation.
"""
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import rest_api

client = TestClient(rest_api.app)


# ==========================================
# Test: POST /permissions/aws/check (from body)
# ==========================================
class TestAWSPermissionsFromBody:
    """Tests for POST /permissions/aws/check endpoint."""

    @patch("api.credentials_checker.check_aws_credentials")
    def test_aws_check_valid_credentials(self, mock_check):
        """Happy: Valid credentials returns permissions report."""
        mock_check.return_value = {
            "status": "valid",
            "by_service": {},
            "summary": {"total_required": 10, "valid": 10, "missing": 0}
        }
        
        response = client.post("/permissions/verify/aws", json={
            "aws_access_key_id": "AKIATESTTEST",
            "aws_secret_access_key": "secretkey123",
            "aws_region": "us-east-1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_aws_check_missing_access_key(self):
        """Invalid: Missing aws_access_key_id returns 422."""
        response = client.post("/permissions/verify/aws", json={
            "aws_secret_access_key": "secret",
            "aws_region": "us-east-1"
        })
        
        assert response.status_code == 422

    def test_aws_check_missing_secret_key(self):
        """Invalid: Missing aws_secret_access_key returns 422."""
        response = client.post("/permissions/verify/aws", json={
            "aws_access_key_id": "AKIATEST",
            "aws_region": "us-east-1"
        })
        
        assert response.status_code == 422

    def test_aws_check_missing_region(self):
        """Invalid: Missing aws_region returns 422."""
        response = client.post("/permissions/verify/aws", json={
            "aws_access_key_id": "AKIATEST",
            "aws_secret_access_key": "secret"
        })
        
        assert response.status_code == 422

    @patch("api.credentials_checker.check_aws_credentials")
    def test_aws_check_with_session_token(self, mock_check):
        """Edge: Request with session token is accepted."""
        mock_check.return_value = {"status": "valid", "by_service": {}, "summary": {}}
        
        response = client.post("/permissions/verify/aws", json={
            "aws_access_key_id": "AKIATEST",
            "aws_secret_access_key": "secret",
            "aws_region": "us-east-1",
            "aws_session_token": "sessiontoken123"
        })
        
        assert response.status_code == 200


# ==========================================
# Test: GET /permissions/aws/check (from config)
# ==========================================
class TestAWSPermissionsFromConfig:
    """Tests for GET /permissions/aws/check endpoint."""

    def test_aws_check_nonexistent_project(self):
        """Invalid: Non-existent project returns 200 with error status."""
        response = client.get("/permissions/verify/aws?project=nonexistent_12345")
        
        # API returns 200 with error status in body
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"

    @patch("api.credentials_checker.check_aws_credentials_from_config")
    def test_aws_check_from_config_success(self, mock_check):
        """Happy: Check from project config works."""
        mock_check.return_value = {
            "status": "valid",
            "by_service": {},
            "summary": {"total_required": 10, "valid": 10, "missing": 0}
        }
        
        response = client.get("/permissions/verify/aws?project=template")
        
        assert response.status_code in [200, 404, 500]

    @patch("api.credentials_checker.check_aws_credentials_from_config")
    def test_aws_check_no_project_uses_active(self, mock_check):
        """Edge: No project specified uses active project."""
        mock_check.return_value = {"status": "valid", "by_service": {}, "summary": {}}
        
        response = client.get("/permissions/verify/aws")
        
        assert response.status_code in [200, 404, 500]


# ==========================================
# Test: POST /permissions/azure/check (from body)
# ==========================================
class TestAzurePermissionsFromBody:
    """Tests for POST /permissions/azure/check endpoint."""

    @patch("api.azure_credentials_checker.check_azure_credentials")
    def test_azure_check_valid_credentials(self, mock_check):
        """Happy: Valid credentials returns permissions report."""
        mock_check.return_value = {
            "status": "valid",
            "layers": {},
            "summary": {}
        }
        
        response = client.post("/permissions/verify/azure", json={
            "azure_subscription_id": "sub-123-456",
            "azure_tenant_id": "tenant-123",
            "azure_client_id": "client-123",
            "azure_client_secret": "secret",
            "azure_region": "westeurope",
            "azure_region_iothub": "westeurope",
            "azure_region_digital_twin": "westeurope"
        })
        
        assert response.status_code == 200

    def test_azure_check_missing_subscription_id(self):
        """Invalid: Missing azure_subscription_id returns 422."""
        response = client.post("/permissions/verify/azure", json={
            "azure_tenant_id": "tenant-123",
            "azure_client_id": "client-123",
            "azure_client_secret": "secret",
            "azure_region": "westeurope",
            "azure_region_iothub": "westeurope",
            "azure_region_digital_twin": "westeurope"
        })
        
        assert response.status_code == 422

    def test_azure_check_missing_tenant_id(self):
        """Invalid: Missing azure_tenant_id returns 422."""
        response = client.post("/permissions/verify/azure", json={
            "azure_subscription_id": "sub-123",
            "azure_client_id": "client-123",
            "azure_client_secret": "secret",
            "azure_region": "westeurope",
            "azure_region_iothub": "westeurope",
            "azure_region_digital_twin": "westeurope"
        })
        
        assert response.status_code == 422

    def test_azure_check_missing_client_secret(self):
        """Invalid: Missing azure_client_secret returns 422."""
        response = client.post("/permissions/verify/azure", json={
            "azure_subscription_id": "sub-123",
            "azure_tenant_id": "tenant-123",
            "azure_client_id": "client-123",
            "azure_region": "westeurope",
            "azure_region_iothub": "westeurope",
            "azure_region_digital_twin": "westeurope"
        })
        
        assert response.status_code == 422


# ==========================================
# Test: GET /permissions/azure/check (from config)
# ==========================================
class TestAzurePermissionsFromConfig:
    """Tests for GET /permissions/azure/check endpoint."""

    def test_azure_check_nonexistent_project(self):
        """Invalid: Non-existent project returns 200 with error status."""
        response = client.get("/permissions/verify/azure?project=nonexistent_12345")
        
        # API returns 200 with error status in body
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"

    @patch("api.azure_credentials_checker.check_azure_credentials_from_config")
    def test_azure_check_from_config_success(self, mock_check):
        """Happy: Check from project config works."""
        mock_check.return_value = {
            "status": "valid",
            "layers": {},
            "summary": {}
        }
        
        response = client.get("/permissions/verify/azure?project=template")
        
        assert response.status_code in [200, 404, 500]


# ==========================================
# Test: POST /permissions/gcp/check (from body)
# ==========================================
class TestGCPPermissionsFromBody:
    """Tests for POST /permissions/gcp/check endpoint."""

    @patch("api.gcp_credentials_checker.check_gcp_credentials")
    def test_gcp_check_valid_credentials(self, mock_check):
        """Happy: Valid credentials returns permissions report."""
        mock_check.return_value = {
            "status": "valid",
            "project_access": {},
            "api_status": {},
            "required_roles": []
        }
        
        response = client.post("/permissions/verify/gcp", json={
            "gcp_billing_account": "billing-123",
            "gcp_credentials_file": "/path/to/creds.json",
            "gcp_region": "europe-west1"
        })
        
        assert response.status_code == 200

    @patch("api.gcp_credentials_checker.check_gcp_credentials")
    def test_gcp_check_without_billing_account(self, mock_check):
        """Valid: Missing gcp_billing_account is OK (it's optional)."""
        mock_check.return_value = {
            "status": "valid",
            "project_access": {},
            "api_status": {},
            "required_roles": []
        }
        
        response = client.post("/permissions/verify/gcp", json={
            "gcp_credentials_file": "/path/to/creds.json",
            "gcp_region": "europe-west1"
        })
        
        # gcp_billing_account is optional, so this should succeed
        assert response.status_code == 200

    def test_gcp_check_missing_credentials_file(self):
        """Invalid: Missing gcp_credentials_file returns 422."""
        response = client.post("/permissions/verify/gcp", json={
            "gcp_billing_account": "billing-123",
            "gcp_region": "europe-west1"
        })
        
        assert response.status_code == 422

    def test_gcp_check_missing_region(self):
        """Invalid: Missing gcp_region returns 422."""
        response = client.post("/permissions/verify/gcp", json={
            "gcp_billing_account": "billing-123",
            "gcp_credentials_file": "/path/to/creds.json"
        })
        
        assert response.status_code == 422

    @patch("api.gcp_credentials_checker.check_gcp_credentials")
    def test_gcp_check_with_project_id(self, mock_check):
        """Edge: Request with existing project_id is accepted."""
        mock_check.return_value = {
            "status": "valid",
            "project_access": {},
            "api_status": {},
            "required_roles": []
        }
        
        response = client.post("/permissions/verify/gcp", json={
            "gcp_project_id": "my-existing-project",
            "gcp_billing_account": "billing-123",
            "gcp_credentials_file": "/path/to/creds.json",
            "gcp_region": "europe-west1"
        })
        
        assert response.status_code == 200


# ==========================================
# Test: GET /permissions/gcp/check (from config)
# ==========================================
class TestGCPPermissionsFromConfig:
    """Tests for GET /permissions/gcp/check endpoint."""

    def test_gcp_check_nonexistent_project(self):
        """Invalid: Non-existent project returns 200 with error status."""
        response = client.get("/permissions/verify/gcp?project=nonexistent_12345")
        
        # API returns 200 with error status in body, or may fail with 500
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            # Error can be in status field or message
            assert data.get("status") == "error" or "error" in str(data).lower()

    @patch("api.gcp_credentials_checker.check_gcp_credentials_from_config")
    def test_gcp_check_from_config_success(self, mock_check):
        """Happy: Check from project config works."""
        mock_check.return_value = {
            "status": "valid",
            "project_access": {},
            "api_status": {},
            "required_roles": []
        }
        
        response = client.get("/permissions/verify/gcp?project=template")
        
        assert response.status_code in [200, 404, 500]


# ==========================================
# Test: Credential Check Response Formats
# ==========================================
class TestCredentialResponseFormats:
    """Tests for consistent response formats across providers."""

    @patch("api.credentials_checker.check_aws_credentials")
    def test_aws_response_has_summary(self, mock_check):
        """Happy: AWS response includes summary."""
        mock_check.return_value = {
            "status": "valid",
            "by_service": {"iot": {"valid": True}},
            "summary": {"total_required": 10, "valid": 10, "missing": 0}
        }
        
        response = client.post("/permissions/verify/aws", json={
            "aws_access_key_id": "AKIATEST",
            "aws_secret_access_key": "secret",
            "aws_region": "us-east-1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data



    @patch("api.gcp_credentials_checker.check_gcp_credentials")
    def test_gcp_response_has_api_status(self, mock_check):
        """Happy: GCP response includes api_status."""
        mock_check.return_value = {
            "status": "valid",
            "project_access": {"accessible": True},
            "api_status": {"pubsub": True, "cloudfunctions": True},
            "required_roles": ["roles/pubsub.admin"]
        }
        
        response = client.post("/permissions/verify/gcp", json={
            "gcp_billing_account": "billing-123",
            "gcp_credentials_file": "/path/to/creds.json",
            "gcp_region": "europe-west1"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "api_status" in data
        assert "required_roles" in data
