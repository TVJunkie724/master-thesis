"""
Unit tests for Azure L3 (Storage) layer components.

Tests cover:
- Cosmos DB Account/Database/Container create/destroy/check
- Blob container create/destroy/check
- L3 App Service Plan/Function App create/destroy/check
- Function deployment (Hot Reader, Movers)
- L3 adapter orchestration
- Pre-deployment checks
- Exception handling
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError, ClientAuthenticationError


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def mock_azure_provider():
    """Create a mock AzureProvider with all required clients."""
    provider = MagicMock()
    provider.location = "eastus"
    
    # Mock naming
    provider.naming.resource_group.return_value = "rg-test-twin"
    provider.naming.twin_name.return_value = "test-twin"
    provider.naming.storage_account.return_value = "testtwinsa"
    provider.naming.cosmos_account.return_value = "test-twin-cosmos"
    provider.naming.cosmos_database.return_value = "iot-data"
    provider.naming.hot_cosmos_container.return_value = "hot-data"
    provider.naming.cold_blob_container.return_value = "cold-data"
    provider.naming.archive_blob_container.return_value = "archive-data"
    provider.naming.l3_app_service_plan.return_value = "test-twin-l3-plan"
    provider.naming.l3_function_app.return_value = "test-twin-l3-functions"
    provider.naming.l2_function_app.return_value = "test-twin-l2-functions"
    
    # Mock clients
    provider.clients = {
        "cosmos": MagicMock(),
        "web": MagicMock(),
        "storage": MagicMock(),
        "blob": MagicMock(),
    }
    
    return provider


@pytest.fixture
def mock_config():
    """Create a mock project configuration."""
    config = MagicMock()
    config.digital_twin_name = "test-twin"
    config.iot_devices = [{"id": "device-1", "type": "sensor"}]
    return config


# ==========================================
# Cosmos DB Account Tests
# ==========================================

class TestCosmosAccount:
    """Tests for Cosmos DB Account create/destroy/check."""
    
    @patch("src.providers.azure.layers.layer_3_storage.check_cosmos_account")
    def test_create_cosmos_account_success(self, mock_check, mock_azure_provider):
        """Happy path: Cosmos DB Account created successfully."""
        mock_check.return_value = False  # Account doesn't exist, create should proceed
        from src.providers.azure.layers.layer_3_storage import create_cosmos_account
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(name="test-twin-cosmos")
        mock_azure_provider.clients["cosmos"].database_accounts.begin_create_or_update.return_value = mock_poller
        
        result = create_cosmos_account(mock_azure_provider)
        
        assert result == "test-twin-cosmos"
        mock_azure_provider.clients["cosmos"].database_accounts.begin_create_or_update.assert_called_once()
    
    def test_create_cosmos_account_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import create_cosmos_account
        
        with pytest.raises(ValueError, match="provider is required"):
            create_cosmos_account(None)
    
    def test_destroy_cosmos_account_success(self, mock_azure_provider):
        """Happy path: Cosmos DB Account destroyed."""
        from src.providers.azure.layers.layer_3_storage import destroy_cosmos_account
        
        mock_poller = MagicMock()
        mock_azure_provider.clients["cosmos"].database_accounts.begin_delete.return_value = mock_poller
        
        destroy_cosmos_account(mock_azure_provider)
        
        mock_azure_provider.clients["cosmos"].database_accounts.begin_delete.assert_called_once()
    
    def test_destroy_cosmos_account_not_found_handled(self, mock_azure_provider):
        """Error handling: ResourceNotFoundError handled gracefully."""
        from src.providers.azure.layers.layer_3_storage import destroy_cosmos_account
        
        mock_azure_provider.clients["cosmos"].database_accounts.begin_delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_cosmos_account(mock_azure_provider)
    
    def test_check_cosmos_account_exists_returns_true(self, mock_azure_provider):
        """Check: Returns True when account exists."""
        from src.providers.azure.layers.layer_3_storage import check_cosmos_account
        
        mock_azure_provider.clients["cosmos"].database_accounts.get.return_value = MagicMock()
        
        result = check_cosmos_account(mock_azure_provider)
        
        assert result is True
    
    def test_check_cosmos_account_missing_returns_false(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_3_storage import check_cosmos_account
        
        mock_azure_provider.clients["cosmos"].database_accounts.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_cosmos_account(mock_azure_provider)
        
        assert result is False


# ==========================================
# Cosmos DB Database Tests
# ==========================================

class TestCosmosDatabase:
    """Tests for Cosmos DB Database create/destroy/check."""
    
    def test_create_cosmos_database_success(self, mock_azure_provider):
        """Happy path: Database created."""
        from src.providers.azure.layers.layer_3_storage import create_cosmos_database
        
        mock_poller = MagicMock()
        mock_azure_provider.clients["cosmos"].sql_resources.begin_create_update_sql_database.return_value = mock_poller
        
        result = create_cosmos_database(mock_azure_provider)
        
        assert result == "iot-data"
    
    def test_create_cosmos_database_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import create_cosmos_database
        
        with pytest.raises(ValueError, match="provider is required"):
            create_cosmos_database(None)
    
    def test_destroy_cosmos_database_not_found_handled(self, mock_azure_provider):
        """Error handling: ResourceNotFoundError handled."""
        from src.providers.azure.layers.layer_3_storage import destroy_cosmos_database
        
        mock_azure_provider.clients["cosmos"].sql_resources.begin_delete_sql_database.side_effect = ResourceNotFoundError("Not found")
        
        destroy_cosmos_database(mock_azure_provider)  # Should not raise
    
    def test_check_cosmos_database_exists(self, mock_azure_provider):
        """Check: Returns True when exists."""
        from src.providers.azure.layers.layer_3_storage import check_cosmos_database
        
        mock_azure_provider.clients["cosmos"].sql_resources.get_sql_database.return_value = MagicMock()
        
        assert check_cosmos_database(mock_azure_provider) is True


# ==========================================
# Hot Cosmos Container Tests
# ==========================================

class TestHotCosmosContainer:
    """Tests for Hot Cosmos Container create/destroy/check."""
    
    def test_create_hot_cosmos_container_success(self, mock_azure_provider):
        """Happy path: Container created."""
        from src.providers.azure.layers.layer_3_storage import create_hot_cosmos_container
        
        mock_poller = MagicMock()
        mock_azure_provider.clients["cosmos"].sql_resources.begin_create_update_sql_container.return_value = mock_poller
        
        result = create_hot_cosmos_container(mock_azure_provider)
        
        assert result == "hot-data"
    
    def test_destroy_hot_cosmos_container_not_found_handled(self, mock_azure_provider):
        """Error handling: ResourceNotFoundError handled."""
        from src.providers.azure.layers.layer_3_storage import destroy_hot_cosmos_container
        
        mock_azure_provider.clients["cosmos"].sql_resources.begin_delete_sql_container.side_effect = ResourceNotFoundError("")
        
        destroy_hot_cosmos_container(mock_azure_provider)  # Should not raise
    
    def test_check_hot_cosmos_container_missing(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_3_storage import check_hot_cosmos_container
        
        mock_azure_provider.clients["cosmos"].sql_resources.get_sql_container.side_effect = ResourceNotFoundError("")
        
        assert check_hot_cosmos_container(mock_azure_provider) is False


# ==========================================
# Cold Blob Container Tests
# ==========================================

class TestColdBlobContainer:
    """Tests for Cold Blob Container create/destroy/check."""
    
    @patch("src.providers.azure.layers.layer_3_storage.check_cold_blob_container")
    def test_create_cold_blob_container_success(self, mock_check, mock_azure_provider):
        """Happy path: Container created."""
        mock_check.return_value = False  # Container doesn't exist
        from src.providers.azure.layers.layer_3_storage import create_cold_blob_container
        
        result = create_cold_blob_container(mock_azure_provider)
        
        assert result == "cold-data"
        mock_azure_provider.clients["storage"].blob_containers.create.assert_called_once()
    
    def test_create_cold_blob_container_already_exists(self, mock_azure_provider):
        """Edge case: Container already exists returns name."""
        from src.providers.azure.layers.layer_3_storage import create_cold_blob_container
        
        mock_azure_provider.clients["storage"].blob_containers.create.side_effect = HttpResponseError("ContainerAlreadyExists")
        
        result = create_cold_blob_container(mock_azure_provider)
        
        assert result == "cold-data"
    
    def test_destroy_cold_blob_container_not_found(self, mock_azure_provider):
        """Error handling: Not found handled."""
        from src.providers.azure.layers.layer_3_storage import destroy_cold_blob_container
        
        mock_azure_provider.clients["storage"].blob_containers.delete.side_effect = ResourceNotFoundError("")
        
        destroy_cold_blob_container(mock_azure_provider)  # Should not raise


# ==========================================
# Archive Blob Container Tests
# ==========================================

class TestArchiveBlobContainer:
    """Tests for Archive Blob Container create/destroy/check."""
    
    def test_create_archive_blob_container_success(self, mock_azure_provider):
        """Happy path: Container created."""
        from src.providers.azure.layers.layer_3_storage import create_archive_blob_container
        
        result = create_archive_blob_container(mock_azure_provider)
        
        assert result == "archive-data"
    
    def test_check_archive_blob_container_exists(self, mock_azure_provider):
        """Check: Returns True when exists."""
        from src.providers.azure.layers.layer_3_storage import check_archive_blob_container
        
        mock_azure_provider.clients["storage"].blob_containers.get.return_value = MagicMock()
        
        assert check_archive_blob_container(mock_azure_provider) is True


# ==========================================
# L3 App Service Plan Tests
# ==========================================

class TestL3AppServicePlan:
    """Tests for L3 App Service Plan create/destroy/check."""
    
    @patch('azure.mgmt.web.models.AppServicePlan')
    @patch('azure.mgmt.web.models.SkuDescription')
    def test_create_l3_app_service_plan_success(self, mock_sku, mock_plan, mock_azure_provider):
        """Happy path: Plan created."""
        from src.providers.azure.layers.layer_3_storage import create_l3_app_service_plan
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(id="/subscriptions/.../test-twin-l3-plan")
        mock_azure_provider.clients["web"].app_service_plans.begin_create_or_update.return_value = mock_poller
        
        result = create_l3_app_service_plan(mock_azure_provider)
        
        assert "/test-twin-l3-plan" in result
    
    def test_create_l3_app_service_plan_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import create_l3_app_service_plan
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l3_app_service_plan(None)
    
    def test_destroy_l3_app_service_plan_not_found(self, mock_azure_provider):
        """Error handling: Not found handled."""
        from src.providers.azure.layers.layer_3_storage import destroy_l3_app_service_plan
        
        mock_azure_provider.clients["web"].app_service_plans.delete.side_effect = ResourceNotFoundError("")
        
        destroy_l3_app_service_plan(mock_azure_provider)  # Should not raise
    
    def test_check_l3_app_service_plan_missing(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_3_storage import check_l3_app_service_plan
        
        mock_azure_provider.clients["web"].app_service_plans.get.side_effect = ResourceNotFoundError("")
        
        assert check_l3_app_service_plan(mock_azure_provider) is False


# ==========================================
# L3 Function App Tests
# ==========================================

class TestL3FunctionApp:
    """Tests for L3 Function App create/destroy/check."""
    
    @patch('src.providers.azure.layers.layer_3_storage._configure_l3_function_app_settings')
    @patch('src.providers.azure.layers.layer_setup_azure.get_managed_identity_id')
    def test_create_l3_function_app_success(self, mock_identity, mock_configure, mock_azure_provider, mock_config):
        """Happy path: Function App created."""
        from src.providers.azure.layers.layer_3_storage import create_l3_function_app
        
        mock_identity.return_value = "/subscriptions/.../test-identity"
        
        mock_plan = MagicMock()
        mock_plan.id = "/subscriptions/.../test-twin-l3-plan"
        mock_azure_provider.clients["web"].app_service_plans.get.return_value = mock_plan
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(name="test-twin-l3-functions")
        mock_azure_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        result = create_l3_function_app(mock_azure_provider, mock_config)
        
        assert result == "test-twin-l3-functions"
    
    def test_create_l3_function_app_missing_provider_raises(self, mock_config):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import create_l3_function_app
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l3_function_app(None, mock_config)
    
    def test_create_l3_function_app_missing_config_raises(self, mock_azure_provider):
        """Validation: None config raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import create_l3_function_app
        
        with pytest.raises(ValueError, match="config is required"):
            create_l3_function_app(mock_azure_provider, None)


# ==========================================
# Hot Reader Function Tests
# ==========================================

class TestHotReaderFunction:
    """Tests for Hot Reader function deployment."""
    
    @patch('src.providers.azure.layers.layer_3_storage._deploy_function_code_via_kudu')
    @patch('os.path.exists', return_value=True)
    def test_deploy_hot_reader_function_success(self, mock_exists, mock_kudu, mock_azure_provider):
        """Happy path: Function deployed."""
        from src.providers.azure.layers.layer_3_storage import deploy_hot_reader_function
        
        deploy_hot_reader_function(mock_azure_provider, "/test/project")
        
        mock_kudu.assert_called_once()
    
    @patch('os.path.exists', return_value=False)
    def test_deploy_hot_reader_function_no_code_skipped(self, mock_exists, mock_azure_provider):
        """Edge case: No function code skips deployment."""
        from src.providers.azure.layers.layer_3_storage import deploy_hot_reader_function
        
        # Should not raise
        deploy_hot_reader_function(mock_azure_provider, "/test/project")
    
    def test_deploy_hot_reader_function_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import deploy_hot_reader_function
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_hot_reader_function(None, "/test")
    
    def test_deploy_hot_reader_function_missing_project_path_raises(self, mock_azure_provider):
        """Validation: Empty project_path raises ValueError."""
        from src.providers.azure.layers.layer_3_storage import deploy_hot_reader_function
        
        with pytest.raises(ValueError, match="project_path is required"):
            deploy_hot_reader_function(mock_azure_provider, "")


# ==========================================
# Hot-Cold Mover Function Tests
# ==========================================

class TestHotColdMoverFunction:
    """Tests for Hot-Cold Mover function."""
    
    @patch('src.providers.azure.layers.layer_3_storage._deploy_function_code_via_kudu')
    @patch('os.path.exists', return_value=True)
    def test_deploy_hot_cold_mover_function_success(self, mock_exists, mock_kudu, mock_azure_provider, mock_config):
        """Happy path: Mover deployed."""
        from src.providers.azure.layers.layer_3_storage import deploy_hot_cold_mover_function
        
        deploy_hot_cold_mover_function(mock_azure_provider, mock_config, "/test/project")
        
        mock_kudu.assert_called_once()
    
    def test_deploy_hot_cold_mover_missing_params_raises(self, mock_azure_provider, mock_config):
        """Validation: Missing params raise ValueError."""
        from src.providers.azure.layers.layer_3_storage import deploy_hot_cold_mover_function
        
        with pytest.raises(ValueError):
            deploy_hot_cold_mover_function(None, mock_config, "/test")
        
        with pytest.raises(ValueError):
            deploy_hot_cold_mover_function(mock_azure_provider, None, "/test")


# ==========================================
# L3 Adapter Tests
# ==========================================

class TestL3Adapter:
    """Tests for L3 adapter orchestration."""
    
    @patch('src.providers.azure.layers.l3_adapter._check_l2_deployed', return_value=True)
    @patch('src.providers.azure.layers.layer_3_storage.create_cosmos_account')
    @patch('src.providers.azure.layers.layer_3_storage.create_cosmos_database')
    @patch('src.providers.azure.layers.layer_3_storage.create_hot_cosmos_container')
    @patch('src.providers.azure.layers.layer_3_storage.create_l3_app_service_plan')
    @patch('src.providers.azure.layers.layer_3_storage.create_l3_function_app')
    @patch('src.providers.azure.layers.layer_3_storage.deploy_hot_reader_function')
    @patch('src.providers.azure.layers.layer_3_storage.deploy_hot_reader_last_entry_function')
    def test_deploy_l3_hot_success(
        self, mock_reader_last, mock_reader, mock_func_app, mock_plan,
        mock_container, mock_db, mock_account, mock_l2_check, mock_azure_provider
    ):
        """Happy path: L3 Hot deployed."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_hot
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.project_path.parent.parent = "/test/path"
        
        deploy_l3_hot(mock_context, mock_azure_provider)
        
        mock_account.assert_called_once()
        mock_db.assert_called_once()
        mock_container.assert_called_once()
        mock_plan.assert_called_once()
        mock_func_app.assert_called_once()
    
    @patch('src.providers.azure.layers.l3_adapter._check_l2_deployed', side_effect=RuntimeError("L3 requires L2 to be deployed first"))
    def test_deploy_l3_hot_without_l2_raises(self, mock_l2_check, mock_azure_provider):
        """Pre-flight: L3 without L2 raises RuntimeError."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_hot
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        
        with pytest.raises(RuntimeError, match="L3 requires L2"):
            deploy_l3_hot(mock_context, mock_azure_provider)
    
    @patch('src.providers.azure.layers.layer_3_storage.create_cold_blob_container')
    @patch('src.providers.azure.layers.layer_3_storage.deploy_hot_cold_mover_function')
    def test_deploy_l3_cold_success(self, mock_mover, mock_container, mock_azure_provider):
        """Happy path: L3 Cold deployed."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_cold
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.project_path.parent.parent = "/test/path"
        
        deploy_l3_cold(mock_context, mock_azure_provider)
        
        mock_container.assert_called_once()
        mock_mover.assert_called_once()
    
    @patch('src.providers.azure.layers.layer_3_storage.create_archive_blob_container')
    @patch('src.providers.azure.layers.layer_3_storage.deploy_cold_archive_mover_function')
    def test_deploy_l3_archive_success(self, mock_mover, mock_container, mock_azure_provider):
        """Happy path: L3 Archive deployed."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_archive
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.project_path.parent.parent = "/test/path"
        
        deploy_l3_archive(mock_context, mock_azure_provider)
        
        mock_container.assert_called_once()
        mock_mover.assert_called_once()


# ==========================================
# Naming Integration Tests
# ==========================================

class TestL3NamingIntegration:
    """Tests for L3 naming function integration."""
    
    def test_l3_app_service_plan_naming(self):
        """Verify l3_app_service_plan returns expected format."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("factory-twin")
        
        assert naming.l3_app_service_plan() == "factory-twin-l3-plan"
    
    def test_l3_function_app_naming(self):
        """Verify l3_function_app returns expected format."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("factory-twin")
        
        assert naming.l3_function_app() == "factory-twin-l3-functions"
    
    def test_cosmos_naming(self):
        """Verify Cosmos DB naming."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("factory-twin")
        
        assert naming.cosmos_account() == "factory-twin-cosmos"
        assert naming.cosmos_database() == "iot-data"
        assert naming.hot_cosmos_container() == "hot-data"
    
    def test_blob_container_naming(self):
        """Verify Blob container naming."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("factory-twin")
        
        assert naming.cold_blob_container() == "cold-data"
        assert naming.archive_blob_container() == "archive-data"
