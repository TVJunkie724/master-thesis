"""
Unit tests for Azure L4 (ADT) layer components.

Tests cover:
- ADT Instance create/destroy/check
- DTDL Model upload/delete
- Twin create/destroy
- Relationship create
- L4 App Service Plan create/destroy/check
- L4 Function App create/destroy/check
- Event Grid Subscription create/destroy/check
- info_l4 status checks
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
    provider.subscription_id = "sub-12345"
    
    # Mock naming
    provider.naming.resource_group.return_value = "rg-test-twin"
    provider.naming.twin_name.return_value = "test-twin"
    provider.naming.storage_account.return_value = "testtwinsa"
    provider.naming.digital_twins_instance.return_value = "test-twin-adt"
    provider.naming.l4_app_service_plan.return_value = "test-twin-l4-plan"
    provider.naming.l4_function_app.return_value = "test-twin-l4-functions"
    provider.naming.iot_hub.return_value = "test-twin-iothub"
    provider.naming.managed_identity.return_value = "test-twin-identity"
    
    # Mock clients - use correct key names from Azure provider
    provider.clients = {
        "digitaltwins_mgmt": MagicMock(),  # Azure Digital Twins Management
        "digitaltwins": MagicMock(),        # Azure Digital Twins Data
        "web": MagicMock(),
        "authorization": MagicMock(),       # Role assignments
        "msi": MagicMock(),
        "eventgrid": MagicMock(),
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
# ADT Instance Tests
# ==========================================

class TestADTInstance:
    """Tests for ADT Instance create/destroy/check."""
    
    @patch("src.providers.azure.layers.layer_4_adt.check_adt_instance")
    def test_create_adt_instance_success(self, mock_check, mock_azure_provider):
        """Happy path: ADT instance created successfully."""
        mock_check.return_value = False  # Instance doesn't exist, create should proceed
        from src.providers.azure.layers.layer_4_adt import create_adt_instance
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(host_name="test-twin-adt.eastus.digitaltwins.azure.net")
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.begin_create_or_update.return_value = mock_poller
        
        # Mock managed identity access grant
        mock_azure_provider.clients["msi"].user_assigned_identities.get.return_value = MagicMock(
            principal_id="mi-principal-id"
        )
        mock_azure_provider.clients["authorization"].role_assignments.list_for_scope.return_value = []
        mock_azure_provider.clients["authorization"].role_assignments.create.return_value = MagicMock()
        
        result = create_adt_instance(mock_azure_provider)
        
        assert result is not None
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.begin_create_or_update.assert_called_once()
    
    def test_create_adt_instance_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_adt_instance
        
        with pytest.raises(ValueError, match="provider is required"):
            create_adt_instance(None)
    
    def test_destroy_adt_instance_success(self, mock_azure_provider):
        """Happy path: ADT instance destroyed."""
        from src.providers.azure.layers.layer_4_adt import destroy_adt_instance
        
        mock_poller = MagicMock()
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.begin_delete.return_value = mock_poller
        
        destroy_adt_instance(mock_azure_provider)
        
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.begin_delete.assert_called_once()
    
    def test_destroy_adt_instance_not_found_handled(self, mock_azure_provider):
        """Error handling: ResourceNotFoundError handled gracefully."""
        from src.providers.azure.layers.layer_4_adt import destroy_adt_instance
        
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.begin_delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_adt_instance(mock_azure_provider)
    
    def test_destroy_adt_instance_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import destroy_adt_instance
        
        with pytest.raises(ValueError, match="provider is required"):
            destroy_adt_instance(None)
    
    def test_check_adt_instance_exists_returns_true(self, mock_azure_provider):
        """Check: Returns True when instance exists."""
        from src.providers.azure.layers.layer_4_adt import check_adt_instance
        
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.get.return_value = MagicMock()
        
        result = check_adt_instance(mock_azure_provider)
        
        assert result is True
    
    def test_check_adt_instance_missing_returns_false(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_4_adt import check_adt_instance
        
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_adt_instance(mock_azure_provider)
        
        assert result is False
    
    def test_get_adt_instance_url_success(self, mock_azure_provider):
        """Happy path: Returns ADT URL."""
        from src.providers.azure.layers.layer_4_adt import get_adt_instance_url
        
        mock_adt = MagicMock()
        mock_adt.host_name = "test-twin-adt.eastus.digitaltwins.azure.net"
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.get.return_value = mock_adt
        
        result = get_adt_instance_url(mock_azure_provider)
        
        assert result == "https://test-twin-adt.eastus.digitaltwins.azure.net"
    
    def test_get_adt_instance_url_not_found_returns_none(self, mock_azure_provider):
        """Edge case: Returns None when instance not found."""
        from src.providers.azure.layers.layer_4_adt import get_adt_instance_url
        
        mock_azure_provider.clients["digitaltwins_mgmt"].digital_twins.get.side_effect = ResourceNotFoundError("Not found")
        
        result = get_adt_instance_url(mock_azure_provider)
        
        assert result is None


# ==========================================
# DTDL Model Tests
# ==========================================

class TestDTDLModels:
    """Tests for DTDL Model upload/delete."""
    
    @patch('azure.digitaltwins.core.DigitalTwinsClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('src.providers.azure.layers.layer_4_adt.get_adt_instance_url')
    def test_upload_adt_models_success(self, mock_url, mock_cred, mock_client, mock_azure_provider):
        """Happy path: Models uploaded successfully."""
        from src.providers.azure.layers.layer_4_adt import upload_adt_models
        
        mock_url.return_value = "https://test-twin-adt.digitaltwins.azure.net"
        
        models = [
            {"@id": "dtmi:test:model1;1", "displayName": "Model1"},
            {"@id": "dtmi:test:model2;1", "displayName": "Model2"}
        ]
        
        upload_adt_models(mock_azure_provider, models)
        
        mock_client.return_value.create_models.assert_called_once()
    
    def test_upload_adt_models_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import upload_adt_models
        
        with pytest.raises(ValueError, match="provider is required"):
            upload_adt_models(None, [{"@id": "test;1"}])
    
    def test_upload_adt_models_empty_list_raises(self, mock_azure_provider):
        """Validation: Empty models list raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import upload_adt_models
        
        with pytest.raises(ValueError, match="models is required"):
            upload_adt_models(mock_azure_provider, [])
    
    @patch('azure.digitaltwins.core.DigitalTwinsClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('src.providers.azure.layers.layer_4_adt.get_adt_instance_url')
    def test_delete_adt_models_success(self, mock_url, mock_cred, mock_client, mock_azure_provider):
        """Happy path: Models deleted."""
        from src.providers.azure.layers.layer_4_adt import delete_adt_models
        
        mock_url.return_value = "https://test-twin-adt.digitaltwins.azure.net"
        model_ids = ["dtmi:test:model1;1", "dtmi:test:model2;1"]
        
        delete_adt_models(mock_azure_provider, model_ids)
        
        assert mock_client.return_value.delete_model.call_count == 2
    
    def test_delete_adt_models_not_found_handled(self, mock_azure_provider):
        """Error handling: ResourceNotFoundError handled gracefully."""
        from src.providers.azure.layers.layer_4_adt import delete_adt_models
        
        mock_azure_provider.clients["digitaltwins"].delete_model.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        delete_adt_models(mock_azure_provider, ["dtmi:test:model1;1"])


# ==========================================
# Twin Instance Tests
# ==========================================

class TestTwinInstances:
    """Tests for Digital Twin create/destroy."""
    
    @patch('azure.digitaltwins.core.DigitalTwinsClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('src.providers.azure.layers.layer_4_adt.get_adt_instance_url')
    def test_create_adt_twin_success(self, mock_url, mock_cred, mock_client, mock_azure_provider):
        """Happy path: Twin created successfully."""
        from src.providers.azure.layers.layer_4_adt import create_adt_twin
        
        mock_url.return_value = "https://test-twin-adt.digitaltwins.azure.net"
        
        create_adt_twin(
            mock_azure_provider,
            twin_id="twin-1",
            model_id="dtmi:test:model;1",
            properties={"temperature": 25.0}
        )
        
        mock_client.return_value.upsert_digital_twin.assert_called_once()
    
    def test_create_adt_twin_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_adt_twin
        
        with pytest.raises(ValueError, match="provider is required"):
            create_adt_twin(None, "twin-1", "dtmi:test;1")
    
    def test_create_adt_twin_missing_twin_id_raises(self, mock_azure_provider):
        """Validation: Empty twin_id raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_adt_twin
        
        with pytest.raises(ValueError, match="twin_id is required"):
            create_adt_twin(mock_azure_provider, "", "dtmi:test;1")
    
    @patch('azure.digitaltwins.core.DigitalTwinsClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('src.providers.azure.layers.layer_4_adt.get_adt_instance_url')
    def test_destroy_adt_twin_success(self, mock_url, mock_cred, mock_client, mock_azure_provider):
        """Happy path: Twin destroyed."""
        from src.providers.azure.layers.layer_4_adt import destroy_adt_twin
        
        mock_url.return_value = "https://test-twin-adt.digitaltwins.azure.net"
        mock_client.return_value.list_incoming_relationships.return_value = []
        mock_client.return_value.list_relationships.return_value = []
        
        destroy_adt_twin(mock_azure_provider, "twin-1")
        
        mock_client.return_value.delete_digital_twin.assert_called_once()
    
    @patch('azure.digitaltwins.core.DigitalTwinsClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('src.providers.azure.layers.layer_4_adt.get_adt_instance_url')
    def test_destroy_adt_twin_not_found_handled(self, mock_url, mock_cred, mock_client, mock_azure_provider):
        """Error handling: ResourceNotFoundError handled gracefully."""
        from src.providers.azure.layers.layer_4_adt import destroy_adt_twin
        
        mock_url.return_value = "https://test-twin-adt.digitaltwins.azure.net"
        mock_client.return_value.list_incoming_relationships.return_value = []
        mock_client.return_value.list_relationships.return_value = []
        mock_client.return_value.delete_digital_twin.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_adt_twin(mock_azure_provider, "twin-1")


# ==========================================
# Relationship Tests
# ==========================================

class TestRelationships:
    """Tests for ADT Relationship create."""
    
    @patch('azure.digitaltwins.core.DigitalTwinsClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('src.providers.azure.layers.layer_4_adt.get_adt_instance_url')
    def test_create_adt_relationship_success(self, mock_url, mock_cred, mock_client, mock_azure_provider):
        """Happy path: Relationship created."""
        from src.providers.azure.layers.layer_4_adt import create_adt_relationship
        
        mock_url.return_value = "https://test-twin-adt.digitaltwins.azure.net"
        
        create_adt_relationship(
            mock_azure_provider,
            source_twin_id="parent-twin",
            target_twin_id="child-twin",
            relationship_name="contains"
        )
        
        mock_client.return_value.upsert_relationship.assert_called_once()
    
    def test_create_adt_relationship_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_adt_relationship
        
        with pytest.raises(ValueError, match="provider is required"):
            create_adt_relationship(None, "src", "tgt", "contains")
    
    def test_create_adt_relationship_missing_source_raises(self, mock_azure_provider):
        """Validation: Empty source_twin_id raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_adt_relationship
        
        with pytest.raises(ValueError, match="source_twin_id is required"):
            create_adt_relationship(mock_azure_provider, "", "tgt", "contains")


# ==========================================
# L4 App Service Plan Tests
# ==========================================

class TestL4AppServicePlan:
    """Tests for L4 App Service Plan create/destroy/check."""
    
    @patch('azure.mgmt.web.models.AppServicePlan')
    @patch('azure.mgmt.web.models.SkuDescription')
    def test_create_l4_app_service_plan_success(self, mock_sku, mock_plan, mock_azure_provider):
        """Happy path: Plan created."""
        from src.providers.azure.layers.layer_4_adt import create_l4_app_service_plan
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(id="/subscriptions/.../test-twin-l4-plan")
        mock_azure_provider.clients["web"].app_service_plans.begin_create_or_update.return_value = mock_poller
        
        result = create_l4_app_service_plan(mock_azure_provider)
        
        assert "/test-twin-l4-plan" in result
    
    def test_create_l4_app_service_plan_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_l4_app_service_plan
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l4_app_service_plan(None)
    
    def test_destroy_l4_app_service_plan_not_found(self, mock_azure_provider):
        """Error handling: Not found handled."""
        from src.providers.azure.layers.layer_4_adt import destroy_l4_app_service_plan
        
        mock_azure_provider.clients["web"].app_service_plans.delete.side_effect = ResourceNotFoundError("")
        
        destroy_l4_app_service_plan(mock_azure_provider)  # Should not raise
    
    def test_check_l4_app_service_plan_missing(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_4_adt import check_l4_app_service_plan
        
        mock_azure_provider.clients["web"].app_service_plans.get.side_effect = ResourceNotFoundError("")
        
        assert check_l4_app_service_plan(mock_azure_provider) is False


# ==========================================
# L4 Function App Tests
# ==========================================

class TestL4FunctionApp:
    """Tests for L4 Function App create/destroy/check."""
    
    @patch('src.providers.azure.layers.layer_4_adt._configure_l4_function_app_settings')
    @patch('src.providers.azure.layers.layer_4_adt._deploy_l4_functions')
    @patch('src.providers.azure.layers.layer_setup_azure.get_managed_identity_id')
    def test_create_l4_function_app_success(
        self, mock_identity, mock_deploy, mock_configure, mock_azure_provider, mock_config
    ):
        """Happy path: Function App created."""
        from src.providers.azure.layers.layer_4_adt import create_l4_function_app
        
        mock_identity.return_value = "/subscriptions/.../test-identity"
        
        mock_plan = MagicMock()
        mock_plan.id = "/subscriptions/.../test-twin-l4-plan"
        mock_azure_provider.clients["web"].app_service_plans.get.return_value = mock_plan
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(name="test-twin-l4-functions")
        mock_azure_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        result = create_l4_function_app(
            mock_azure_provider, mock_config, "https://test-twin-adt.digitaltwins.azure.net"
        )
        
        assert result == "test-twin-l4-functions"
    
    def test_create_l4_function_app_missing_provider_raises(self, mock_config):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_l4_function_app
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l4_function_app(None, mock_config, "https://adt.url")
    
    def test_create_l4_function_app_missing_config_raises(self, mock_azure_provider):
        """Validation: None config raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_l4_function_app
        
        with pytest.raises(ValueError, match="config is required"):
            create_l4_function_app(mock_azure_provider, None, "https://adt.url")
    
    def test_create_l4_function_app_missing_url_raises(self, mock_azure_provider, mock_config):
        """Validation: Empty adt_instance_url raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_l4_function_app
        
        with pytest.raises(ValueError, match="adt_instance_url is required"):
            create_l4_function_app(mock_azure_provider, mock_config, "")
    
    def test_destroy_l4_function_app_not_found(self, mock_azure_provider):
        """Error handling: Not found handled."""
        from src.providers.azure.layers.layer_4_adt import destroy_l4_function_app
        
        mock_azure_provider.clients["web"].web_apps.delete.side_effect = ResourceNotFoundError("")
        
        destroy_l4_function_app(mock_azure_provider)  # Should not raise
    
    def test_check_l4_function_app_exists(self, mock_azure_provider):
        """Check: Returns True when exists."""
        from src.providers.azure.layers.layer_4_adt import check_l4_function_app
        
        mock_azure_provider.clients["web"].web_apps.get.return_value = MagicMock()
        
        assert check_l4_function_app(mock_azure_provider) is True
    
    def test_check_l4_function_app_missing(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_4_adt import check_l4_function_app
        
        mock_azure_provider.clients["web"].web_apps.get.side_effect = ResourceNotFoundError("")
        
        assert check_l4_function_app(mock_azure_provider) is False


# ==========================================
# Event Grid Subscription Tests
# ==========================================

class TestEventGridSubscription:
    """Tests for Event Grid Subscription create/destroy/check."""
    
    def test_create_adt_event_grid_subscription_success(self, mock_azure_provider, mock_config):
        """Happy path: Event Grid subscription created."""
        from src.providers.azure.layers.layer_4_adt import create_adt_event_grid_subscription
        
        # Mock Function App URL retrieval
        mock_azure_provider.clients["web"].web_apps.get.return_value = MagicMock(
            default_host_name="test-twin-l4-functions.azurewebsites.net"
        )
        
        # Mock event subscription creation
        mock_poller = MagicMock()
        mock_azure_provider.clients["eventgrid"].event_subscriptions.begin_create_or_update.return_value = mock_poller
        
        create_adt_event_grid_subscription(mock_azure_provider, mock_config)
        
        mock_azure_provider.clients["eventgrid"].event_subscriptions.begin_create_or_update.assert_called_once()
    
    def test_create_adt_event_grid_subscription_missing_provider_raises(self, mock_config):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_4_adt import create_adt_event_grid_subscription
        
        with pytest.raises(ValueError, match="provider is required"):
            create_adt_event_grid_subscription(None, mock_config)
    
    def test_destroy_adt_event_grid_subscription_not_found(self, mock_azure_provider):
        """Error handling: Not found handled."""
        from src.providers.azure.layers.layer_4_adt import destroy_adt_event_grid_subscription
        
        mock_azure_provider.clients["eventgrid"].event_subscriptions.begin_delete.side_effect = ResourceNotFoundError("")
        
        destroy_adt_event_grid_subscription(mock_azure_provider)  # Should not raise
    
    def test_check_adt_event_grid_subscription_exists(self, mock_azure_provider):
        """Check: Returns True when exists."""
        from src.providers.azure.layers.layer_4_adt import check_adt_event_grid_subscription
        
        mock_azure_provider.clients["eventgrid"].event_subscriptions.get.return_value = MagicMock()
        
        assert check_adt_event_grid_subscription(mock_azure_provider) is True
    
    def test_check_adt_event_grid_subscription_missing(self, mock_azure_provider):
        """Check: Returns False when not found."""
        from src.providers.azure.layers.layer_4_adt import check_adt_event_grid_subscription
        
        mock_azure_provider.clients["eventgrid"].event_subscriptions.get.side_effect = ResourceNotFoundError("")
        
        assert check_adt_event_grid_subscription(mock_azure_provider) is False


# ==========================================
# Info/Status Tests
# ==========================================

class TestInfoL4:
    """Tests for info_l4 status checks."""
    
    @patch('src.providers.azure.layers.layer_4_adt.check_adt_instance')
    @patch('src.providers.azure.layers.layer_4_adt.check_l4_app_service_plan')
    @patch('src.providers.azure.layers.layer_4_adt.check_l4_function_app')
    @patch('src.providers.azure.layers.layer_4_adt.check_adt_event_grid_subscription')
    def test_info_l4_all_deployed(
        self, mock_event, mock_app, mock_plan, mock_adt, mock_azure_provider
    ):
        """Happy path: All components deployed."""
        from src.providers.azure.layers.layer_4_adt import info_l4
        
        mock_adt.return_value = True
        mock_plan.return_value = True
        mock_app.return_value = True
        mock_event.return_value = True
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        
        result = info_l4(mock_context, mock_azure_provider)
        
        assert result["adt_instance"] is True
        assert result["app_service_plan"] is True
        assert result["function_app"] is True
    
    @patch('src.providers.azure.layers.layer_4_adt.check_adt_instance')
    @patch('src.providers.azure.layers.layer_4_adt.check_l4_app_service_plan')
    @patch('src.providers.azure.layers.layer_4_adt.check_l4_function_app')
    @patch('src.providers.azure.layers.layer_4_adt.check_adt_event_grid_subscription')
    def test_info_l4_none_deployed(
        self, mock_event, mock_app, mock_plan, mock_adt, mock_azure_provider
    ):
        """Edge case: No components deployed."""
        from src.providers.azure.layers.layer_4_adt import info_l4
        
        mock_adt.return_value = False
        mock_plan.return_value = False
        mock_app.return_value = False
        mock_event.return_value = False
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        
        result = info_l4(mock_context, mock_azure_provider)
        
        assert result["adt_instance"] is False
        assert result["app_service_plan"] is False
        assert result["function_app"] is False
