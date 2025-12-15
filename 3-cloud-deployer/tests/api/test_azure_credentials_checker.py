"""
Unit tests for Azure Credentials Checker.

Tests cover:
- Credential validation
- Action matching logic
- Layer status calculation
- CLI integration
"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestAzureCredentialValidation:
    """Tests for Azure credential validation logic."""

    def test_check_azure_credentials_missing_fields(self):
        """Test validation fails with missing required fields."""
        from api.azure_credentials_checker import check_azure_credentials
        
        # Missing all fields
        result = check_azure_credentials({})
        assert result["status"] == "invalid"
        assert "Missing required credentials" in result["message"]
        
        # Missing some fields
        result = check_azure_credentials({
            "azure_subscription_id": "sub-123",
            "azure_tenant_id": "tenant-123"
            # Missing client_id and client_secret
        })
        assert result["status"] == "invalid"
        assert "azure_client_id" in result["message"]

    @patch('api.azure_credentials_checker._create_credential')
    @patch('api.azure_credentials_checker._get_caller_identity')
    @patch('api.azure_credentials_checker._get_role_assignments_with_permissions')
    def test_check_azure_credentials_valid(self, mock_roles, mock_identity, mock_cred):
        """Test successful credential validation with all permissions present."""
        from api.azure_credentials_checker import check_azure_credentials
        
        mock_identity.return_value = {
            "subscription_id": "sub-123",
            "subscription_name": "Test Sub",
            "tenant_id": "tenant-123",
            "state": "Enabled"
        }
        
        # Mock role assignments with all required actions
        mock_roles.return_value = {
            "assignments": [{"role_name": "Digital Twin Deployer", "principal_id": "sp-123"}],
            "all_actions": {
                "*",  # Wildcard covers everything
            },
            "all_data_actions": {
                "Microsoft.DigitalTwins/digitaltwins/write",
                "Microsoft.DigitalTwins/models/write",
                "Microsoft.DigitalTwins/query/action",
            },
        }
        
        result = check_azure_credentials({
            "azure_subscription_id": "sub-123",
            "azure_tenant_id": "tenant-123",
            "azure_client_id": "client-123",
            "azure_client_secret": "secret-123"
        })
        
        assert result["status"] == "valid"
        assert result["caller_identity"] is not None
        assert result["can_list_roles"] == True

    @patch('api.azure_credentials_checker._create_credential')
    @patch('api.azure_credentials_checker._get_caller_identity')
    @patch('api.azure_credentials_checker._get_role_assignments_with_permissions')
    def test_check_azure_credentials_partial(self, mock_roles, mock_identity, mock_cred):
        """Test partial credential validation when some actions are missing."""
        from api.azure_credentials_checker import check_azure_credentials
        
        mock_identity.return_value = {
            "subscription_id": "sub-123",
            "subscription_name": "Test Sub",
            "tenant_id": "tenant-123",
            "state": "Enabled"
        }
        
        # Missing some required actions
        mock_roles.return_value = {
            "assignments": [{"role_name": "Reader", "principal_id": "sp-123"}],
            "all_actions": {"*/read"},  # Only read
            "all_data_actions": set(),
        }
        
        result = check_azure_credentials({
            "azure_subscription_id": "sub-123",
            "azure_tenant_id": "tenant-123",
            "azure_client_id": "client-123",
            "azure_client_secret": "secret-123"
        })
        
        assert result["status"] in ["partial", "invalid"]


class TestActionMatching:
    """Tests for action matching logic."""

    def test_action_matches_direct(self):
        """Test direct action match returns 'exact'."""
        from api.azure_credentials_checker import _action_matches
        
        user_actions = {"Microsoft.Web/sites/write", "Microsoft.Web/sites/read"}
        
        # Direct match returns "exact"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "exact"
        # No match returns "none"
        assert _action_matches(user_actions, "Microsoft.Web/sites/delete") == "none"

    def test_action_matches_wildcard_all(self):
        """Test wildcard * matches everything and returns 'wildcard'."""
        from api.azure_credentials_checker import _action_matches
        
        user_actions = {"*"}
        
        # Wildcard matches return "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "wildcard"
        assert _action_matches(user_actions, "Microsoft.Storage/storageAccounts/delete") == "wildcard"

    def test_action_matches_suffix_wildcard(self):
        """Test suffix wildcard like Microsoft.Web/* returns 'wildcard'."""
        from api.azure_credentials_checker import _action_matches
        
        user_actions = {"Microsoft.Web/*"}
        
        # Prefix wildcard matches return "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/serverfarms/delete") == "wildcard"
        # Non-matching prefix returns "none"
        assert _action_matches(user_actions, "Microsoft.Storage/storageAccounts/write") == "none"

    def test_action_matches_read_wildcard(self):
        """Test */read wildcard returns 'wildcard' for read actions."""
        from api.azure_credentials_checker import _action_matches
        
        user_actions = {"*/read"}
        
        # Suffix wildcard matches return "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/sites/read") == "wildcard"
        assert _action_matches(user_actions, "Microsoft.Storage/storageAccounts/read") == "wildcard"
        # Non-matching suffix returns "none"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "none"


class TestComparePermissions:
    """Tests for permission comparison by layer."""

    def test_compare_permissions_all_valid(self):
        """Test all layers valid when all actions present."""
        from api.azure_credentials_checker import _compare_permissions
        
        role_info = {
            "assignments": [{"role_name": "Owner"}],
            "all_actions": {"*"},  # Owner has all actions
            "all_data_actions": {
                "Microsoft.DigitalTwins/digitaltwins/write",
                "Microsoft.DigitalTwins/models/write",
                "Microsoft.DigitalTwins/query/action",
            },
        }
        
        result = _compare_permissions(role_info)
        
        assert result["summary"]["valid_layers"] == result["summary"]["total_layers"]
        assert result["summary"]["invalid_layers"] == 0

    def test_compare_permissions_missing_actions(self):
        """Test layer invalid when required actions missing."""
        from api.azure_credentials_checker import _compare_permissions
        
        role_info = {
            "assignments": [{"role_name": "Reader"}],
            "all_actions": {"*/read"},  # Only read actions
            "all_data_actions": set(),
        }
        
        result = _compare_permissions(role_info)
        
        # Should have missing actions
        assert result["summary"]["valid_layers"] < result["summary"]["total_layers"]

    def test_compare_permissions_none_role_info(self):
        """Test handling of None role_info (couldn't list)."""
        from api.azure_credentials_checker import _compare_permissions
        
        result = _compare_permissions(None)
        
        assert result["summary"]["total_layers"] == 0


class TestAzureCredentialsFromConfig:
    """Tests for loading credentials from project config."""

    @patch('api.azure_credentials_checker.check_azure_credentials')
    @patch('src.core.state.get_active_project')
    @patch('src.core.state.get_project_upload_path')
    @patch('builtins.open')
    @patch('os.path.exists')
    def test_from_config_with_project_name(self, mock_exists, mock_open, mock_upload, mock_active, mock_check):
        """Test loading credentials from specific project."""
        from api.azure_credentials_checker import check_azure_credentials_from_config
        
        mock_exists.return_value = True
        mock_upload.return_value = "/app/upload"
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "azure": {
                "azure_subscription_id": "sub-123",
                "azure_tenant_id": "tenant-123",
                "azure_client_id": "client-123",
                "azure_client_secret": "secret-123"
            }
        })
        mock_check.return_value = {"status": "valid"}
        
        result = check_azure_credentials_from_config("my-project")
        
        mock_check.assert_called_once()
        assert result["project_name"] == "my-project"

    @patch('src.core.state.get_active_project')
    @patch('src.core.state.get_project_upload_path')
    @patch('os.path.exists')
    def test_from_config_missing_azure_section(self, mock_exists, mock_upload, mock_active):
        """Test error when Azure section missing from config."""
        from api.azure_credentials_checker import check_azure_credentials_from_config
        import builtins
        
        mock_exists.return_value = True
        mock_upload.return_value = "/app/upload"
        mock_active.return_value = "test-project"
        
        with patch.object(builtins, 'open', MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(
                    read=MagicMock(return_value='{"aws": {}}')
                )),
                __exit__=MagicMock(return_value=False)
            )
        )):
            result = check_azure_credentials_from_config()
        
        assert result["status"] == "error"
        assert "No Azure credentials" in result["message"]


class TestRequiredPermissionsStructure:
    """Tests for the required permissions data structure."""

    def test_required_permissions_contains_all_layers(self):
        """Test all layers are defined in required permissions."""
        from api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS
        
        expected_layers = ["setup", "layer_0", "layer_1", "layer_2", "layer_3", "layer_4", "layer_5"]
        
        for layer in expected_layers:
            assert layer in REQUIRED_AZURE_PERMISSIONS, f"Missing layer: {layer}"

    def test_layer_1_requires_authorization_actions(self):
        """Test layer_1 requires role assignment actions."""
        from api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS
        
        layer_1 = REQUIRED_AZURE_PERMISSIONS["layer_1"]
        required_actions = layer_1.get("required_actions", [])
        
        # Should include authorization actions for managed identity
        assert any("Microsoft.Authorization" in a for a in required_actions)

    def test_layer_4_requires_data_actions(self):
        """Test layer_4 requires Digital Twins data plane actions."""
        from api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS
        
        layer_4 = REQUIRED_AZURE_PERMISSIONS["layer_4"]
        data_actions = layer_4.get("required_data_actions", [])
        
        assert len(data_actions) > 0
        assert any("digitaltwins" in a for a in data_actions)

    def test_builtin_roles_contain_key_roles(self):
        """Test AZURE_BUILTIN_ROLES contains essential roles."""
        from api.azure_credentials_checker import AZURE_BUILTIN_ROLES
        
        essential_roles = ["Owner", "Contributor", "Reader", "User Access Administrator"]
        
        for role in essential_roles:
            assert role in AZURE_BUILTIN_ROLES, f"Missing role: {role}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
