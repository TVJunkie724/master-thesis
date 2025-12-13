"""
Azure Setup Layer Edge Case Tests.

Tests for foundational Azure resources:
- Resource Group management
- Managed Identity management
- Storage Account management
- Setup adapter orchestration

These tests mirror the AWS L0 edge case test pattern using mocked Azure SDK clients.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from azure.core.exceptions import ResourceNotFoundError


# ==========================================
# Resource Group Edge Case Tests
# ==========================================

class TestResourceGroupEdgeCases:
    """Edge case tests for Resource Group management."""
    
    def test_create_resource_group_success(self):
        """create_resource_group() should create RG with correct name and location."""
        from src.providers.azure.layers.layer_setup_azure import create_resource_group
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.clients = {"resource": MagicMock()}
        
        result = create_resource_group(mock_provider, location="westeurope")
        
        assert result == "rg-test-twin"
        mock_provider.clients["resource"].resource_groups.create_or_update.assert_called_once()
        call_args = mock_provider.clients["resource"].resource_groups.create_or_update.call_args
        assert call_args.kwargs["resource_group_name"] == "rg-test-twin"
        assert call_args.kwargs["parameters"]["location"] == "westeurope"
    
    def test_create_resource_group_already_exists_handles_gracefully(self):
        """create_resource_group() should not error if RG already exists."""
        from src.providers.azure.layers.layer_setup_azure import create_resource_group
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.clients = {"resource": MagicMock()}
        # create_or_update is idempotent, no error expected
        
        # Should not raise
        result = create_resource_group(mock_provider)
        assert result == "rg-test-twin"
    
    def test_destroy_resource_group_success(self):
        """destroy_resource_group() should delete RG."""
        from src.providers.azure.layers.layer_setup_azure import destroy_resource_group
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_poller = MagicMock()
        mock_provider.clients = {"resource": MagicMock()}
        mock_provider.clients["resource"].resource_groups.begin_delete.return_value = mock_poller
        
        destroy_resource_group(mock_provider)
        
        mock_provider.clients["resource"].resource_groups.begin_delete.assert_called_once_with("rg-test-twin")
        mock_poller.result.assert_called_once()
    
    def test_destroy_resource_group_not_found_handles_gracefully(self):
        """destroy_resource_group() should handle ResourceGroupNotFound gracefully."""
        from src.providers.azure.layers.layer_setup_azure import destroy_resource_group
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.clients = {"resource": MagicMock()}
        mock_provider.clients["resource"].resource_groups.begin_delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_resource_group(mock_provider)
    
    def test_check_resource_group_exists_returns_true(self):
        """check_resource_group() should return True when RG exists."""
        from src.providers.azure.layers.layer_setup_azure import check_resource_group
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.clients = {"resource": MagicMock()}
        
        result = check_resource_group(mock_provider)
        
        assert result is True
        mock_provider.clients["resource"].resource_groups.get.assert_called_once_with("rg-test-twin")
    
    def test_check_resource_group_missing_returns_false(self):
        """check_resource_group() should return False when RG doesn't exist."""
        from src.providers.azure.layers.layer_setup_azure import check_resource_group
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.clients = {"resource": MagicMock()}
        mock_provider.clients["resource"].resource_groups.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_resource_group(mock_provider)
        
        assert result is False


# ==========================================
# Managed Identity Edge Case Tests
# ==========================================

class TestManagedIdentityEdgeCases:
    """Edge case tests for Managed Identity management."""
    
    def test_create_managed_identity_success(self):
        """create_managed_identity() should create identity with correct name."""
        from src.providers.azure.layers.layer_setup_azure import create_managed_identity
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        mock_provider.location = "westeurope"
        
        mock_identity = MagicMock()
        mock_identity.id = "/subscriptions/xxx/resourceGroups/rg-test-twin/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test-twin-identity"
        mock_identity.client_id = "client-id-123"
        mock_identity.principal_id = "principal-id-456"
        
        mock_provider.clients = {"msi": MagicMock()}
        mock_provider.clients["msi"].user_assigned_identities.create_or_update.return_value = mock_identity
        
        result = create_managed_identity(mock_provider)
        
        assert result["client_id"] == "client-id-123"
        assert result["principal_id"] == "principal-id-456"
    
    def test_create_managed_identity_already_exists_returns_existing(self):
        """create_managed_identity() should return existing identity if already created."""
        from src.providers.azure.layers.layer_setup_azure import create_managed_identity
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        mock_provider.location = "westeurope"
        
        mock_identity = MagicMock()
        mock_identity.id = "existing-id"
        mock_identity.client_id = "existing-client-id"
        mock_identity.principal_id = "existing-principal-id"
        
        mock_provider.clients = {"msi": MagicMock()}
        mock_provider.clients["msi"].user_assigned_identities.create_or_update.return_value = mock_identity
        
        result = create_managed_identity(mock_provider)
        
        assert result["client_id"] == "existing-client-id"
    
    def test_destroy_managed_identity_success(self):
        """destroy_managed_identity() should delete identity."""
        from src.providers.azure.layers.layer_setup_azure import destroy_managed_identity
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        mock_provider.clients = {"msi": MagicMock()}
        
        destroy_managed_identity(mock_provider)
        
        mock_provider.clients["msi"].user_assigned_identities.delete.assert_called_once()
    
    def test_destroy_managed_identity_not_found_handles_gracefully(self):
        """destroy_managed_identity() should handle NotFound gracefully."""
        from src.providers.azure.layers.layer_setup_azure import destroy_managed_identity
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        mock_provider.clients = {"msi": MagicMock()}
        mock_provider.clients["msi"].user_assigned_identities.delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_managed_identity(mock_provider)
    
    def test_check_managed_identity_exists_returns_true(self):
        """check_managed_identity() should return True when identity exists."""
        from src.providers.azure.layers.layer_setup_azure import check_managed_identity
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        mock_provider.clients = {"msi": MagicMock()}
        
        result = check_managed_identity(mock_provider)
        
        assert result is True
    
    def test_check_managed_identity_missing_returns_false(self):
        """check_managed_identity() should return False when identity doesn't exist."""
        from src.providers.azure.layers.layer_setup_azure import check_managed_identity
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        mock_provider.clients = {"msi": MagicMock()}
        mock_provider.clients["msi"].user_assigned_identities.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_managed_identity(mock_provider)
        
        assert result is False
    
    def test_get_managed_identity_id_returns_id(self):
        """get_managed_identity_id() should return the full resource ID."""
        from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.managed_identity.return_value = "test-twin-identity"
        
        mock_identity = MagicMock()
        mock_identity.id = "/subscriptions/xxx/providers/test-twin-identity"
        mock_provider.clients = {"msi": MagicMock()}
        mock_provider.clients["msi"].user_assigned_identities.get.return_value = mock_identity
        
        result = get_managed_identity_id(mock_provider)
        
        assert result == "/subscriptions/xxx/providers/test-twin-identity"


# ==========================================
# Storage Account Edge Case Tests
# ==========================================

class TestStorageAccountEdgeCases:
    """Edge case tests for Storage Account management."""
    
    def test_create_storage_account_success(self):
        """create_storage_account() should create with correct SKU and kind."""
        from src.providers.azure.layers.layer_setup_azure import create_storage_account
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.location = "westeurope"
        mock_poller = MagicMock()
        mock_provider.clients = {"storage": MagicMock()}
        mock_provider.clients["storage"].storage_accounts.begin_create.return_value = mock_poller
        
        result = create_storage_account(mock_provider)
        
        assert result == "testtwinstorage"
        mock_provider.clients["storage"].storage_accounts.begin_create.assert_called_once()
        call_args = mock_provider.clients["storage"].storage_accounts.begin_create.call_args
        assert call_args.kwargs["parameters"]["sku"]["name"] == "Standard_LRS"
        assert call_args.kwargs["parameters"]["kind"] == "StorageV2"
    
    def test_create_storage_account_already_exists_handles_gracefully(self):
        """create_storage_account() should handle existing account gracefully."""
        from src.providers.azure.layers.layer_setup_azure import create_storage_account
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.location = "westeurope"
        mock_poller = MagicMock()
        mock_provider.clients = {"storage": MagicMock()}
        mock_provider.clients["storage"].storage_accounts.begin_create.return_value = mock_poller
        
        # Should not raise
        result = create_storage_account(mock_provider)
        assert result == "testtwinstorage"
    
    def test_destroy_storage_account_success(self):
        """destroy_storage_account() should delete storage account."""
        from src.providers.azure.layers.layer_setup_azure import destroy_storage_account
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.clients = {"storage": MagicMock()}
        
        destroy_storage_account(mock_provider)
        
        mock_provider.clients["storage"].storage_accounts.delete.assert_called_once()
    
    def test_destroy_storage_account_not_found_handles_gracefully(self):
        """destroy_storage_account() should handle NotFound gracefully."""
        from src.providers.azure.layers.layer_setup_azure import destroy_storage_account
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.clients = {"storage": MagicMock()}
        mock_provider.clients["storage"].storage_accounts.delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_storage_account(mock_provider)
    
    def test_check_storage_account_exists_returns_true(self):
        """check_storage_account() should return True when account exists."""
        from src.providers.azure.layers.layer_setup_azure import check_storage_account
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.clients = {"storage": MagicMock()}
        
        result = check_storage_account(mock_provider)
        
        assert result is True
    
    def test_check_storage_account_missing_returns_false(self):
        """check_storage_account() should return False when account doesn't exist."""
        from src.providers.azure.layers.layer_setup_azure import check_storage_account
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.clients = {"storage": MagicMock()}
        mock_provider.clients["storage"].storage_accounts.get_properties.side_effect = ResourceNotFoundError("Not found")
        
        result = check_storage_account(mock_provider)
        
        assert result is False


# ==========================================
# Setup Adapter Orchestration Tests
# ==========================================

class TestSetupAdapterOrchestration:
    """Tests for setup adapter orchestration logic."""
    
    @patch("src.providers.azure.layers.l_setup_adapter.create_resource_group")
    @patch("src.providers.azure.layers.l_setup_adapter.create_managed_identity")
    @patch("src.providers.azure.layers.l_setup_adapter.create_storage_account")
    def test_deploy_setup_creates_all_resources_in_order(
        self, mock_storage, mock_identity, mock_rg
    ):
        """deploy_setup() should create RG → Identity → Storage in order."""
        from src.providers.azure.layers.l_setup_adapter import deploy_setup
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_provider = MagicMock()
        mock_provider.location = "westeurope"
        
        mock_identity.return_value = {"id": "id", "client_id": "cid", "principal_id": "pid"}
        
        deploy_setup(mock_context, mock_provider)
        
        # Verify order
        mock_rg.assert_called_once()
        mock_identity.assert_called_once()
        mock_storage.assert_called_once()
    
    @patch("src.providers.azure.layers.l_setup_adapter.destroy_storage_account")
    @patch("src.providers.azure.layers.l_setup_adapter.destroy_managed_identity")
    @patch("src.providers.azure.layers.l_setup_adapter.destroy_resource_group")
    def test_destroy_setup_removes_all_resources(
        self, mock_rg, mock_identity, mock_storage
    ):
        """destroy_setup() should remove resources in reverse order."""
        from src.providers.azure.layers.l_setup_adapter import destroy_setup
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_provider = MagicMock()
        
        destroy_setup(mock_context, mock_provider)
        
        mock_storage.assert_called_once()
        mock_identity.assert_called_once()
        mock_rg.assert_called_once()
    
    @patch("src.providers.azure.layers.l_setup_adapter.check_resource_group")
    @patch("src.providers.azure.layers.l_setup_adapter.check_managed_identity")
    @patch("src.providers.azure.layers.l_setup_adapter.check_storage_account")
    def test_info_setup_reports_all_resource_status(
        self, mock_check_storage, mock_check_identity, mock_check_rg
    ):
        """info_setup() should check and report status of all resources."""
        from src.providers.azure.layers.l_setup_adapter import info_setup
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_provider = MagicMock()
        
        mock_check_rg.return_value = True
        mock_check_identity.return_value = True
        mock_check_storage.return_value = False
        
        result = info_setup(mock_context, mock_provider)
        
        assert result["resource_group"] is True
        assert result["managed_identity"] is True
        assert result["storage_account"] is False
