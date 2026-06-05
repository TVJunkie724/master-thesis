"""
Tests for the GCP Credentials Checker module.

Tests the project state and billing validation logic with mocked GCP responses.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from pathlib import Path


# Helper to create mock SA parse return value (tuple format)
def _make_mock_parse_return(project_id="test-project", client_email="sa@test.iam.gserviceaccount.com"):
    """Create the (display_info, sa_info, credentials) tuple that _parse_service_account_json returns."""
    display_info = {
        "project_id": project_id,
        "client_email": client_email,
        "private_key_id": "abc123..."
    }
    sa_info = {
        "type": "service_account",
        "project_id": project_id,
        "client_email": client_email,
        "private_key_id": "abc123def456",
        "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n"
    }
    mock_credentials = MagicMock()
    return (display_info, sa_info, mock_credentials)


class TestGCPProjectStateValidation:
    """Tests for GCP project state validation."""

    @patch('api.gcp_credentials_checker._check_billing_enabled')
    @patch('api.gcp_credentials_checker._check_project_access')
    @patch('api.gcp_credentials_checker._parse_service_account_json')
    @patch.object(Path, 'exists', return_value=True)
    def test_deleted_project_detected(self, mock_path_exists, mock_parse, mock_project_access, mock_billing):
        """Test validation fails for projects marked for deletion."""
        from api.gcp_credentials_checker import check_gcp_credentials
        
        mock_parse.return_value = _make_mock_parse_return()
        mock_project_access.return_value = {
            "status": "accessible",
            "project_id": "test-project",
            "display_name": "Test Project",
            "state": "DELETE_REQUESTED"  # Key: project is being deleted
        }
        
        result = check_gcp_credentials({
            "gcp_credentials_file": "/tmp/fake_creds.json",
            "gcp_region": "europe-west1",
            "gcp_project_id": "test-project"
        })
        
        # Should fail with clear message about project state
        assert result["status"] == "invalid"
        assert "DELETE_REQUESTED" in result["message"]
        assert "project" in result["message"].lower()

    @patch('api.gcp_credentials_checker._check_enabled_apis')
    @patch('api.gcp_credentials_checker._check_iam_permissions')
    @patch('api.gcp_credentials_checker._validate_gcp_region')
    @patch('api.gcp_credentials_checker._check_billing_enabled')
    @patch('api.gcp_credentials_checker._check_project_access')
    @patch('api.gcp_credentials_checker._parse_service_account_json')
    @patch.object(Path, 'exists', return_value=True)
    def test_active_project_proceeds(self, mock_path_exists, mock_parse, mock_project_access,
                                     mock_billing, mock_region, mock_iam, mock_apis):
        """Test active projects proceed with validation."""
        from api.gcp_credentials_checker import check_gcp_credentials
        
        mock_parse.return_value = _make_mock_parse_return()
        mock_project_access.return_value = {
            "status": "accessible",
            "project_id": "test-project",
            "display_name": "Test Project",
            "state": "ACTIVE"  # Project is active
        }
        mock_billing.return_value = {
            "status": "checked",
            "billing_enabled": True,
            "billing_account": "billingAccounts/ABC123"
        }
        mock_region.return_value = {"valid": True, "region": "europe-west1"}
        mock_apis.return_value = {
            "status": "checked",
            "by_layer": {"setup": {"status": "valid"}}
        }
        mock_iam.return_value = {
            "status": "checked",
            "summary": {"total_required": 1, "valid": 1, "missing": 0},
            "by_layer": {"setup": {"status": "valid", "valid": ["resourcemanager.projects.get"], "missing": []}},
        }
        
        result = check_gcp_credentials({
            "gcp_credentials_file": "/tmp/fake_creds.json",
            "gcp_region": "europe-west1",
            "gcp_project_id": "test-project"
        })
        
        # Should proceed (project is active)
        assert result["status"] in ["valid", "partial"]


class TestGCPBillingValidation:
    """Tests for GCP billing account validation."""

    @patch('api.gcp_credentials_checker._check_billing_enabled')
    @patch('api.gcp_credentials_checker._check_project_access')
    @patch('api.gcp_credentials_checker._parse_service_account_json')
    @patch.object(Path, 'exists', return_value=True)
    def test_billing_disabled_detected(self, mock_path_exists, mock_parse, mock_project_access, mock_billing):
        """Test validation fails when billing is not enabled."""
        from api.gcp_credentials_checker import check_gcp_credentials
        
        mock_parse.return_value = _make_mock_parse_return()
        mock_project_access.return_value = {
            "status": "accessible",
            "project_id": "test-project",
            "display_name": "Test Project",
            "state": "ACTIVE"
        }
        mock_billing.return_value = {
            "status": "checked",
            "billing_enabled": False,  # Key: billing is disabled
            "billing_account": None
        }
        
        result = check_gcp_credentials({
            "gcp_credentials_file": "/tmp/fake_creds.json",
            "gcp_region": "europe-west1",
            "gcp_project_id": "test-project"
        })
        
        # Should fail with clear message about billing
        assert result["status"] == "invalid"
        assert "billing" in result["message"].lower()

    @patch('api.gcp_credentials_checker._check_enabled_apis')
    @patch('api.gcp_credentials_checker._check_iam_permissions')
    @patch('api.gcp_credentials_checker._validate_gcp_region')
    @patch('api.gcp_credentials_checker._check_billing_enabled')
    @patch('api.gcp_credentials_checker._check_project_access')
    @patch('api.gcp_credentials_checker._parse_service_account_json')
    @patch.object(Path, 'exists', return_value=True)
    def test_billing_check_skipped_gracefully(self, mock_path_exists, mock_parse, mock_project_access, 
                                              mock_billing, mock_region, mock_iam, mock_apis):
        """Test that billing check is skipped gracefully if SDK not installed."""
        from api.gcp_credentials_checker import check_gcp_credentials
        
        mock_parse.return_value = _make_mock_parse_return()
        mock_project_access.return_value = {
            "status": "accessible",
            "project_id": "test-project",
            "display_name": "Test Project",
            "state": "ACTIVE"
        }
        mock_billing.return_value = {
            "status": "skipped",
            "reason": "google-cloud-billing not installed",
            "billing_enabled": None
        }
        mock_region.return_value = {"valid": True, "region": "europe-west1"}
        mock_apis.return_value = {
            "status": "checked",
            "by_layer": {"setup": {"status": "valid"}}
        }
        mock_iam.return_value = {
            "status": "checked",
            "summary": {"total_required": 1, "valid": 1, "missing": 0},
            "by_layer": {"setup": {"status": "valid", "valid": ["resourcemanager.projects.get"], "missing": []}},
        }
        
        result = check_gcp_credentials({
            "gcp_credentials_file": "/tmp/fake_creds.json",
            "gcp_region": "europe-west1",
            "gcp_project_id": "test-project"
        })
        
        # Should still proceed - billing check skipped gracefully
        assert result["status"] in ["valid", "partial"]
        assert result["billing_status"]["status"] == "skipped"


class TestCheckBillingEnabledFunction:
    """Tests for the _check_billing_enabled helper function."""

    def test_billing_enabled_returns_true(self):
        """Test billing check when billing is enabled."""
        from api.gcp_credentials_checker import _check_billing_enabled
        
        mock_billing_module = MagicMock()
        mock_client = Mock()
        mock_billing_module.CloudBillingClient.return_value = mock_client
        mock_client.get_project_billing_info.return_value = Mock(
            billing_enabled=True,
            billing_account_name="billingAccounts/ABC123"
        )
        
        mock_google = MagicMock()
        mock_google.cloud.billing_v1 = mock_billing_module
        
        with patch.dict('sys.modules', {
            'google': mock_google,
            'google.cloud': mock_google.cloud,
            'google.cloud.billing_v1': mock_billing_module,
        }):
            result = _check_billing_enabled("test-project")
            
            assert result["status"] == "checked"
            assert result["billing_enabled"] is True
            assert result["billing_account"] == "billingAccounts/ABC123"

    def test_billing_disabled_returns_false(self):
        """Test billing check when billing is disabled."""
        from api.gcp_credentials_checker import _check_billing_enabled
        
        mock_billing_module = MagicMock()
        mock_client = Mock()
        mock_billing_module.CloudBillingClient.return_value = mock_client
        mock_client.get_project_billing_info.return_value = Mock(
            billing_enabled=False,
            billing_account_name=""
        )
        
        mock_google = MagicMock()
        mock_google.cloud.billing_v1 = mock_billing_module
        
        with patch.dict('sys.modules', {
            'google': mock_google,
            'google.cloud': mock_google.cloud,
            'google.cloud.billing_v1': mock_billing_module,
        }):
            result = _check_billing_enabled("test-project")
            
            assert result["status"] == "checked"
            assert result["billing_enabled"] is False


class TestGCPPermissionContractMetadata:
    """Tests for GCP permission contract metadata in checker responses."""

    def test_missing_credentials_response_includes_permission_contract(self):
        from api.gcp_credentials_checker import (
            REQUIRED_GCP_PERMISSIONS,
            check_gcp_credentials,
        )

        result = check_gcp_credentials({})

        assert result["status"] == "invalid"
        assert result["required_permissions"] == REQUIRED_GCP_PERMISSIONS
        assert "workflows.workflows.create" in _all_required_gcp_permissions(
            REQUIRED_GCP_PERMISSIONS
        )

    def test_from_config_error_response_includes_permission_contract(self):
        from api.gcp_credentials_checker import (
            REQUIRED_GCP_PERMISSIONS,
            check_gcp_credentials_from_config,
        )

        result = check_gcp_credentials_from_config(None)

        assert result["status"] == "error"
        assert result["required_permissions"] == REQUIRED_GCP_PERMISSIONS
        assert "resourcemanager.projects.setIamPolicy" in _all_required_gcp_permissions(
            REQUIRED_GCP_PERMISSIONS
        )

    @patch('api.gcp_credentials_checker._check_enabled_apis')
    @patch('api.gcp_credentials_checker._check_iam_permissions')
    @patch('api.gcp_credentials_checker._validate_gcp_region')
    @patch('api.gcp_credentials_checker._check_billing_enabled')
    @patch('api.gcp_credentials_checker._check_project_access')
    @patch('api.gcp_credentials_checker._parse_service_account_json')
    def test_missing_iam_permissions_returns_partial(self, mock_parse, mock_project_access,
                                                     mock_billing, mock_region, mock_iam,
                                                     mock_apis):
        from api.gcp_credentials_checker import check_gcp_credentials

        mock_parse.return_value = _make_mock_parse_return()
        mock_project_access.return_value = {
            "status": "accessible",
            "project_id": "test-project",
            "display_name": "Test Project",
            "state": "ACTIVE",
        }
        mock_billing.return_value = {"status": "checked", "billing_enabled": True}
        mock_region.return_value = {"valid": True, "region": "europe-west1"}
        mock_apis.return_value = {
            "status": "checked",
            "by_layer": {"layer_2": {"status": "valid"}},
        }
        mock_iam.return_value = {
            "status": "checked",
            "resource": "projects/test-project",
            "summary": {"total_required": 2, "valid": 1, "missing": 1},
            "by_layer": {
                "layer_2": {
                    "status": "partial",
                    "valid": ["workflows.workflows.create"],
                    "missing": ["workflows.operations.get"],
                }
            },
        }

        result = check_gcp_credentials({
            "gcp_credentials_file": '{"type":"service_account"}',
            "gcp_region": "europe-west1",
            "gcp_project_id": "test-project",
        })

        assert result["status"] == "partial"
        assert "permissions are missing" in result["message"]
        assert result["permission_status"]["summary"]["missing"] == 1

    @patch('api.gcp_credentials_checker._check_enabled_apis')
    @patch('api.gcp_credentials_checker._check_iam_permissions')
    @patch('api.gcp_credentials_checker._validate_gcp_region')
    @patch('api.gcp_credentials_checker._check_billing_enabled')
    @patch('api.gcp_credentials_checker._check_project_access')
    @patch('api.gcp_credentials_checker._parse_service_account_json')
    def test_iam_permission_check_failure_returns_partial(self, mock_parse, mock_project_access,
                                                          mock_billing, mock_region, mock_iam,
                                                          mock_apis):
        from api.gcp_credentials_checker import check_gcp_credentials

        mock_parse.return_value = _make_mock_parse_return()
        mock_project_access.return_value = {
            "status": "accessible",
            "project_id": "test-project",
            "display_name": "Test Project",
            "state": "ACTIVE",
        }
        mock_billing.return_value = {"status": "checked", "billing_enabled": True}
        mock_region.return_value = {"valid": True, "region": "europe-west1"}
        mock_apis.return_value = {
            "status": "checked",
            "by_layer": {"layer_2": {"status": "valid"}},
        }
        mock_iam.return_value = {
            "status": "check_failed",
            "resource": "projects/test-project",
            "error": "permission denied",
        }

        result = check_gcp_credentials({
            "gcp_credentials_file": '{"type":"service_account"}',
            "gcp_region": "europe-west1",
            "gcp_project_id": "test-project",
        })

        assert result["status"] == "partial"
        assert "Permission check failed" in result["message"]
        assert result["permission_status"]["status"] == "check_failed"


def _all_required_gcp_permissions(required_permissions: dict) -> set[str]:
    return {
        permission
        for group in required_permissions.values()
        for permission in group["permissions"]
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
