"""
Azure L1 (IoT/Data Acquisition) Unit Tests.

Comprehensive tests for all L1 components covering:
- Happy path: create, destroy, check functions work correctly
- Validation: fail-fast for missing required parameters
- Error handling: proper handling of ResourceNotFoundError and other exceptions
- Edge cases: partial deployment, duplicate resources, etc.

Test Classes:
    - TestIoTHub: IoT Hub create/destroy/check
    - TestRBACRoleAssignment: RBAC role assignment management
    - TestL1AppServicePlan: App Service Plan create/destroy/check
    - TestL1FunctionApp: Function App create/destroy/check
    - TestDispatcherFunction: Dispatcher function deployment
    - TestEventGridSubscription: Event Grid subscription management
    - TestIoTDevice: IoT device registration and simulator config
    - TestConnectorFunction: Multi-cloud connector function
    - TestL1Adapter: Adapter orchestration functions
    - TestPreDeploymentChecks: Pre-flight dependency verification
    - TestExceptionHandling: Comprehensive exception handling
    - TestSimulatorConfig: Simulator configuration generation
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import json
import os
import tempfile


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def mock_provider():
    """Create a mock AzureProvider for testing."""
    provider = MagicMock()
    provider.subscription_id = "test-subscription-123"
    provider.location = "westeurope"
    
    # Mock naming
    provider.naming.resource_group.return_value = "test-twin-rg"
    provider.naming.iot_hub.return_value = "test-twin-iothub"
    provider.naming.managed_identity.return_value = "test-twin-identity"
    provider.naming.l1_app_service_plan.return_value = "test-twin-l1-plan"
    provider.naming.l1_function_app.return_value = "test-twin-l1-functions"
    provider.naming.event_grid_subscription.return_value = "test-twin-dispatcher-sub"
    provider.naming.storage_account.return_value = "testtwinstore"
    provider.naming.iot_device.side_effect = lambda device_id: f"test-twin-{device_id}"
    
    # Mock clients
    provider.clients = {
        "iothub": MagicMock(),
        "eventgrid": MagicMock(),
        "authorization": MagicMock(),
        "web": MagicMock(),
        "msi": MagicMock(),
        "storage": MagicMock(),
    }
    
    return provider


@pytest.fixture
def mock_config():
    """Create a mock ProjectConfig for testing."""
    config = MagicMock()
    config.digital_twin_name = "test-twin"
    config.hot_storage_size_in_days = 7
    config.cold_storage_size_in_days = 30
    config.mode = "production"
    config.iot_devices = [
        {"id": "sensor-001", "type": "temperature"},
        {"id": "sensor-002", "type": "humidity"},
    ]
    config.events = {}
    config.providers = {
        "layer_1_provider": "azure",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "azure",
    }
    return config


@pytest.fixture
def mock_context(mock_config):
    """Create a mock DeploymentContext for testing."""
    context = MagicMock()
    context.config = mock_config
    context.project_path = "/app/upload/test-project"
    return context


# ==========================================
# TestIoTHub
# ==========================================

class TestIoTHub:
    """Tests for IoT Hub create/destroy/check functions."""
    
    def test_create_iot_hub_success(self, mock_provider):
        """Should create IoT Hub and return hub name."""
        from src.providers.azure.layers.layer_1_iot import create_iot_hub
        
        # Setup mock
        mock_poller = MagicMock()
        mock_hub = MagicMock()
        mock_hub.name = "test-twin-iothub"
        mock_poller.result.return_value = mock_hub
        mock_provider.clients["iothub"].iot_hub_resource.begin_create_or_update.return_value = mock_poller
        
        # Execute
        result = create_iot_hub(mock_provider)
        
        # Verify
        assert result == "test-twin-iothub"
        mock_provider.clients["iothub"].iot_hub_resource.begin_create_or_update.assert_called_once()
    
    def test_create_iot_hub_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_1_iot import create_iot_hub
        
        with pytest.raises(ValueError, match="provider is required"):
            create_iot_hub(None)
    
    def test_destroy_iot_hub_success(self, mock_provider):
        """Should delete IoT Hub successfully."""
        from src.providers.azure.layers.layer_1_iot import destroy_iot_hub
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = None
        mock_provider.clients["iothub"].iot_hub_resource.begin_delete.return_value = mock_poller
        
        # Should not raise
        destroy_iot_hub(mock_provider)
        
        mock_provider.clients["iothub"].iot_hub_resource.begin_delete.assert_called_once()
    
    def test_destroy_iot_hub_handles_not_found(self, mock_provider):
        """Should handle ResourceNotFoundError gracefully in destroy."""
        from src.providers.azure.layers.layer_1_iot import destroy_iot_hub
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["iothub"].iot_hub_resource.begin_delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_iot_hub(mock_provider)
    
    def test_check_iot_hub_exists(self, mock_provider):
        """Should return True when IoT Hub exists."""
        from src.providers.azure.layers.layer_1_iot import check_iot_hub
        
        mock_provider.clients["iothub"].iot_hub_resource.get.return_value = MagicMock()
        
        result = check_iot_hub(mock_provider)
        
        assert result is True
    
    def test_check_iot_hub_not_found(self, mock_provider):
        """Should return False when IoT Hub doesn't exist."""
        from src.providers.azure.layers.layer_1_iot import check_iot_hub
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["iothub"].iot_hub_resource.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_iot_hub(mock_provider)
        
        assert result is False


# ==========================================
# TestRBACRoleAssignment
# ==========================================

class TestRBACRoleAssignment:
    """Tests for RBAC role assignment functions."""
    
    def test_assign_roles_success(self, mock_provider):
        """Should assign RBAC roles to managed identity."""
        from src.providers.azure.layers.layer_1_iot import assign_managed_identity_roles
        
        # Mock identity lookup
        mock_identity = MagicMock()
        mock_identity.principal_id = "principal-123"
        mock_provider.clients["msi"].user_assigned_identities.get.return_value = mock_identity
        
        # Mock role assignment (with 30s sleep patched)
        with patch("src.providers.azure.layers.layer_1_iot.time.sleep"):
            assign_managed_identity_roles(mock_provider)
        
        # Should create at least one role assignment
        assert mock_provider.clients["authorization"].role_assignments.create.called
    
    def test_assign_roles_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_1_iot import assign_managed_identity_roles
        
        with pytest.raises(ValueError, match="provider is required"):
            assign_managed_identity_roles(None)
    
    def test_destroy_roles_success(self, mock_provider):
        """Should remove RBAC role assignments."""
        from src.providers.azure.layers.layer_1_iot import destroy_managed_identity_roles
        
        mock_identity = MagicMock()
        mock_identity.principal_id = "principal-123"
        mock_provider.clients["msi"].user_assigned_identities.get.return_value = mock_identity
        
        # Mock role assignments list
        mock_assignment = MagicMock()
        mock_assignment.principal_id = "principal-123"
        mock_assignment.id = "/subscriptions/test/role-assignment-1"
        mock_provider.clients["authorization"].role_assignments.list_for_scope.return_value = [mock_assignment]
        
        destroy_managed_identity_roles(mock_provider)
        
        mock_provider.clients["authorization"].role_assignments.delete_by_id.assert_called()
    
    def test_check_roles_exist(self, mock_provider):
        """Should return True when roles are assigned."""
        from src.providers.azure.layers.layer_1_iot import check_managed_identity_roles
        
        mock_identity = MagicMock()
        mock_identity.principal_id = "principal-123"
        mock_provider.clients["msi"].user_assigned_identities.get.return_value = mock_identity
        
        mock_assignment = MagicMock()
        mock_assignment.principal_id = "principal-123"
        mock_provider.clients["authorization"].role_assignments.list_for_scope.return_value = [mock_assignment]
        
        result = check_managed_identity_roles(mock_provider)
        
        assert result is True
    
    def test_handles_duplicate_assignment(self, mock_provider):
        """Should handle RoleAssignmentExists error gracefully."""
        from src.providers.azure.layers.layer_1_iot import assign_managed_identity_roles
        from azure.core.exceptions import HttpResponseError
        
        mock_identity = MagicMock()
        mock_identity.principal_id = "principal-123"
        mock_provider.clients["msi"].user_assigned_identities.get.return_value = mock_identity
        
        # Simulate role already exists error
        error = HttpResponseError("RoleAssignmentExists")
        mock_provider.clients["authorization"].role_assignments.create.side_effect = error
        
        with patch("src.providers.azure.layers.layer_1_iot.time.sleep"):
            # Should not raise - handles duplicate gracefully
            assign_managed_identity_roles(mock_provider)


# ==========================================
# TestL1AppServicePlan
# ==========================================

class TestL1AppServicePlan:
    """Tests for L1 App Service Plan functions."""
    
    def test_create_plan_success(self, mock_provider):
        """Should create App Service Plan and return ID."""
        from src.providers.azure.layers.layer_1_iot import create_l1_app_service_plan
        
        mock_poller = MagicMock()
        mock_plan = MagicMock()
        mock_plan.id = "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Web/serverfarms/test-plan"
        mock_poller.result.return_value = mock_plan
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.return_value = mock_poller
        
        result = create_l1_app_service_plan(mock_provider)
        
        assert "/subscriptions" in result
    
    def test_destroy_plan_success(self, mock_provider):
        """Should delete App Service Plan."""
        from src.providers.azure.layers.layer_1_iot import destroy_l1_app_service_plan
        
        destroy_l1_app_service_plan(mock_provider)
        
        mock_provider.clients["web"].app_service_plans.delete.assert_called_once()
    
    def test_check_plan_exists(self, mock_provider):
        """Should return True when plan exists."""
        from src.providers.azure.layers.layer_1_iot import check_l1_app_service_plan
        
        mock_provider.clients["web"].app_service_plans.get.return_value = MagicMock()
        
        result = check_l1_app_service_plan(mock_provider)
        
        assert result is True
    
    def test_create_plan_idempotent(self, mock_provider):
        """Should use begin_create_or_update for idempotency."""
        from src.providers.azure.layers.layer_1_iot import create_l1_app_service_plan
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(id="/test")
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.return_value = mock_poller
        
        create_l1_app_service_plan(mock_provider)
        
        # Verify create_or_update (not just create) is used
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.assert_called()


# ==========================================
# TestL1FunctionApp
# ==========================================

class TestL1FunctionApp:
    """Tests for L1 Function App functions."""
    
    def test_create_function_app_success(self, mock_provider, mock_config):
        """Should create Function App and configure settings."""
        from src.providers.azure.layers.layer_1_iot import create_l1_function_app
        
        # Mock plan lookup
        mock_plan = MagicMock()
        mock_plan.id = "/subscriptions/test/plan"
        mock_provider.clients["web"].app_service_plans.get.return_value = mock_plan
        
        # Mock web app creation
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(name="test-twin-l1-functions")
        mock_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        # Mock storage keys
        mock_keys = MagicMock()
        mock_keys.keys = [MagicMock(value="test-key")]
        mock_provider.clients["storage"].storage_accounts.list_keys.return_value = mock_keys
        
        # Mock managed identity lookup (patch at the source module where it's imported from)
        with patch("src.providers.azure.layers.layer_setup_azure.get_managed_identity_id") as mock_get_identity:
            mock_get_identity.return_value = "/subscriptions/test/identity"
            result = create_l1_function_app(mock_provider, mock_config)
        
        assert result == "test-twin-l1-functions"
    
    def test_create_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_1_iot import create_l1_function_app
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l1_function_app(None, mock_config)
    
    def test_create_validates_config(self, mock_provider):
        """Should raise ValueError if config is None."""
        from src.providers.azure.layers.layer_1_iot import create_l1_function_app
        
        with pytest.raises(ValueError, match="config is required"):
            create_l1_function_app(mock_provider, None)
    
    def test_destroy_function_app_success(self, mock_provider):
        """Should delete Function App."""
        from src.providers.azure.layers.layer_1_iot import destroy_l1_function_app
        
        destroy_l1_function_app(mock_provider)
        
        mock_provider.clients["web"].web_apps.delete.assert_called_once()
    
    def test_verify_settings_configured(self, mock_provider, mock_config):
        """Should configure app settings including DIGITAL_TWIN_INFO."""
        from src.providers.azure.layers.layer_1_iot import create_l1_function_app
        
        mock_plan = MagicMock(id="/test/plan")
        mock_provider.clients["web"].app_service_plans.get.return_value = mock_plan
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(name="test-app")
        mock_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        mock_keys = MagicMock()
        mock_keys.keys = [MagicMock(value="key")]
        mock_provider.clients["storage"].storage_accounts.list_keys.return_value = mock_keys
        
        with patch("src.providers.azure.layers.layer_setup_azure.get_managed_identity_id") as mock_get_identity:
            mock_get_identity.return_value = "/test/identity"
            create_l1_function_app(mock_provider, mock_config)
        
        # Verify settings were updated
        mock_provider.clients["web"].web_apps.update_application_settings.assert_called()


# ==========================================
# TestDispatcherFunction
# ==========================================

class TestDispatcherFunction:
    """Tests for Dispatcher function deployment."""
    
    def test_deploy_dispatcher_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_1_iot import deploy_dispatcher_function
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_dispatcher_function(None, "/test/path")
    
    def test_deploy_dispatcher_validates_path(self, mock_provider):
        """Should raise ValueError if project_path is None."""
        from src.providers.azure.layers.layer_1_iot import deploy_dispatcher_function
        
        with pytest.raises(ValueError, match="project_path is required"):
            deploy_dispatcher_function(mock_provider, None)
    
    def test_destroy_dispatcher_no_error(self, mock_provider):
        """Should complete without error."""
        from src.providers.azure.layers.layer_1_iot import destroy_dispatcher_function
        
        # Should not raise
        destroy_dispatcher_function(mock_provider)
    
    def test_check_dispatcher_lists_functions(self, mock_provider):
        """Should check for dispatcher function in app."""
        from src.providers.azure.layers.layer_1_iot import check_dispatcher_function
        
        mock_function = MagicMock()
        mock_function.name = "dispatcher"
        mock_provider.clients["web"].web_apps.list_functions.return_value = [mock_function]
        
        result = check_dispatcher_function(mock_provider)
        
        assert result is True
    
    def test_check_dispatcher_not_found(self, mock_provider):
        """Should return False when dispatcher not in function list."""
        from src.providers.azure.layers.layer_1_iot import check_dispatcher_function
        
        mock_function = MagicMock()
        mock_function.name = "other-function"
        mock_provider.clients["web"].web_apps.list_functions.return_value = [mock_function]
        
        result = check_dispatcher_function(mock_provider)
        
        assert result is False


# ==========================================
# TestEventGridSubscription
# ==========================================

class TestEventGridSubscription:
    """Tests for Event Grid subscription functions."""
    
    def test_create_subscription_success(self, mock_provider, mock_config):
        """Should create Event Grid subscription."""
        from src.providers.azure.layers.layer_1_iot import create_event_grid_subscription
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock()
        mock_provider.clients["eventgrid"].event_subscriptions.begin_create_or_update.return_value = mock_poller
        
        create_event_grid_subscription(mock_provider, mock_config)
        
        mock_provider.clients["eventgrid"].event_subscriptions.begin_create_or_update.assert_called_once()
    
    def test_create_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_1_iot import create_event_grid_subscription
        
        with pytest.raises(ValueError, match="provider is required"):
            create_event_grid_subscription(None, mock_config)
    
    def test_destroy_subscription_success(self, mock_provider):
        """Should delete Event Grid subscription."""
        from src.providers.azure.layers.layer_1_iot import destroy_event_grid_subscription
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = None
        mock_provider.clients["eventgrid"].event_subscriptions.begin_delete.return_value = mock_poller
        
        destroy_event_grid_subscription(mock_provider)
        
        mock_provider.clients["eventgrid"].event_subscriptions.begin_delete.assert_called_once()
    
    def test_check_subscription_exists(self, mock_provider):
        """Should return True when subscription exists."""
        from src.providers.azure.layers.layer_1_iot import check_event_grid_subscription
        
        mock_provider.clients["eventgrid"].event_subscriptions.get.return_value = MagicMock()
        
        result = check_event_grid_subscription(mock_provider)
        
        assert result is True
    
    def test_verify_filter_config(self, mock_provider, mock_config):
        """Should configure subscription with DeviceTelemetry filter."""
        from src.providers.azure.layers.layer_1_iot import create_event_grid_subscription
        
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock()
        mock_provider.clients["eventgrid"].event_subscriptions.begin_create_or_update.return_value = mock_poller
        
        create_event_grid_subscription(mock_provider, mock_config)
        
        # Check call includes DeviceTelemetry filter
        call_args = mock_provider.clients["eventgrid"].event_subscriptions.begin_create_or_update.call_args
        event_info = call_args.kwargs.get("event_subscription_info", {})
        assert "filter" in event_info or len(call_args.args) > 2


# ==========================================
# TestIoTDevice
# ==========================================

class TestIoTDevice:
    """Tests for IoT device management functions."""
    
    def test_create_device_validates_params(self, mock_provider, mock_config):
        """Should raise ValueError for missing required params."""
        from src.providers.azure.layers.layer_1_iot import create_iot_device
        
        device = {"id": "sensor-001"}
        
        with pytest.raises(ValueError, match="iot_device is required"):
            create_iot_device(None, mock_provider, mock_config, "/test")
        
        with pytest.raises(ValueError, match="provider is required"):
            create_iot_device(device, None, mock_config, "/test")
    
    def test_destroy_device_validates_params(self, mock_provider):
        """Should raise ValueError for missing params."""
        from src.providers.azure.layers.layer_1_iot import destroy_iot_device
        
        with pytest.raises(ValueError, match="iot_device is required"):
            destroy_iot_device(None, mock_provider)
    
    def test_check_device_validates_params(self, mock_provider):
        """Should raise ValueError for missing params."""
        from src.providers.azure.layers.layer_1_iot import check_iot_device
        
        with pytest.raises(ValueError, match="iot_device is required"):
            check_iot_device(None, mock_provider)
    
    def test_generate_simulator_config_creates_file(self, mock_config):
        """Should generate config_generated.json in correct location."""
        from src.providers.azure.layers.layer_1_iot import _generate_simulator_config
        
        device = {"id": "sensor-001"}
        device_conn_str = "HostName=test.azure-devices.net;DeviceId=sensor-001;SharedAccessKey=abc123"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            _generate_simulator_config(device, device_conn_str, mock_config, tmpdir)
            
            config_path = os.path.join(tmpdir, "iot_device_simulator", "azure", "config_generated.json")
            assert os.path.exists(config_path)
            
            with open(config_path, "r") as f:
                config_data = json.load(f)
            
            assert config_data["connection_string"] == device_conn_str
            assert config_data["device_id"] == "sensor-001"
    
    def test_duplicate_device_handled(self, mock_provider, mock_config):
        """Should handle duplicate device error appropriately."""
        from src.providers.azure.layers.layer_1_iot import create_iot_device
        
        device = {"id": "sensor-001"}
        
        # Mock get_iot_hub_connection_string and the IoTHubRegistryManager import
        with patch("src.providers.azure.layers.layer_1_iot._get_iot_hub_connection_string", return_value="conn-str"):
            with patch("azure.iot.hub.IoTHubRegistryManager") as mock_registry:
                mock_manager = MagicMock()
                mock_manager.create_device_with_sas.side_effect = Exception("DeviceAlreadyExists")
                mock_registry.return_value = mock_manager
                
                with pytest.raises(Exception, match="DeviceAlreadyExists"):
                    create_iot_device(device, mock_provider, mock_config, "/test")


# ==========================================
# TestConnectorFunction
# ==========================================

class TestConnectorFunction:
    """Tests for multi-cloud connector function."""
    
    def test_deploy_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_1_iot import deploy_connector_function
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_connector_function(None, mock_config, "/test", "http://remote", "token")
    
    def test_deploy_missing_url_raises(self, mock_provider, mock_config):
        """Should raise ValueError if remote URL is empty."""
        from src.providers.azure.layers.layer_1_iot import deploy_connector_function
        
        with pytest.raises(ValueError, match="remote_ingestion_url is required"):
            deploy_connector_function(mock_provider, mock_config, "/test", "", "token")
    
    def test_deploy_missing_token_raises(self, mock_provider, mock_config):
        """Should raise ValueError if token is empty."""
        from src.providers.azure.layers.layer_1_iot import deploy_connector_function
        
        with pytest.raises(ValueError, match="inter_cloud_token is required"):
            deploy_connector_function(mock_provider, mock_config, "/test", "http://remote", "")
    
    @patch('requests.post')
    @patch('util.compile_azure_function')
    @patch('os.path.exists', return_value=True)
    def test_deploy_sets_app_settings(self, mock_exists, mock_compile, mock_post, mock_provider, mock_config):
        """Should configure REMOTE_INGESTION_URL and INTER_CLOUD_TOKEN."""
        from src.providers.azure.layers.layer_1_iot import deploy_connector_function
        
        # Mock publish credentials
        mock_creds = MagicMock()
        mock_creds.publishing_user_name = "test_user"
        mock_creds.publishing_password = "test_pass"
        mock_provider.clients["web"].web_apps.list_publishing_credentials.return_value.result.return_value = mock_creds
        
        # Mock util.compile_azure_function
        mock_compile.return_value = b"fake_zip_content"
        
        # Mock requests.post for Kudu
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        mock_settings = MagicMock()
        mock_settings.properties = {"EXISTING_SETTING": "value"}
        mock_provider.clients["web"].web_apps.list_application_settings.return_value = mock_settings
        
        deploy_connector_function(mock_provider, mock_config, "/test", "http://remote.example.com", "secret-token")
        
        # Verify settings were updated
        mock_provider.clients["web"].web_apps.update_application_settings.assert_called()
    
    def test_check_connector_configured(self, mock_provider):
        """Should return True when connector settings are present."""
        from src.providers.azure.layers.layer_1_iot import check_connector_function
        
        mock_settings = MagicMock()
        mock_settings.properties = {
            "REMOTE_INGESTION_URL": "http://example.com",
            "INTER_CLOUD_TOKEN": "token123"
        }
        mock_provider.clients["web"].web_apps.list_application_settings.return_value = mock_settings
        
        result = check_connector_function(mock_provider)
        
        assert result is True
    
    def test_check_connector_not_configured(self, mock_provider):
        """Should return False when connector settings are missing."""
        from src.providers.azure.layers.layer_1_iot import check_connector_function
        
        mock_settings = MagicMock()
        mock_settings.properties = {"OTHER_SETTING": "value"}
        mock_provider.clients["web"].web_apps.list_application_settings.return_value = mock_settings
        
        result = check_connector_function(mock_provider)
        
        assert result is False


# ==========================================
# TestL1Adapter
# ==========================================

class TestL1Adapter:
    """Tests for L1 adapter orchestration functions."""
    
    def test_deploy_calls_all_create_functions(self, mock_context, mock_provider):
        """Should call all create functions in correct order."""
        # Patch at the source module where imports happen
        with patch("src.providers.azure.layers.layer_1_iot.create_iot_hub") as mock_hub, \
             patch("src.providers.azure.layers.layer_1_iot.assign_managed_identity_roles") as mock_rbac, \
             patch("src.providers.azure.layers.layer_1_iot.create_l1_app_service_plan") as mock_plan, \
             patch("src.providers.azure.layers.layer_1_iot.create_l1_function_app") as mock_app, \
             patch("src.providers.azure.layers.layer_1_iot.deploy_dispatcher_function") as mock_disp, \
             patch("src.providers.azure.layers.layer_1_iot.create_event_grid_subscription") as mock_eg, \
             patch("src.providers.azure.layers.layer_1_iot.create_iot_device") as mock_device, \
             patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_setup_info:
            
            # Mock setup check to pass
            mock_setup_info.return_value = {
                "resource_group": True,
                "managed_identity": True,
                "storage_account": True
            }
            
            from src.providers.azure.layers.l1_adapter import deploy_l1
            deploy_l1(mock_context, mock_provider)
            
            # Verify all functions called
            mock_hub.assert_called_once()
            mock_rbac.assert_called_once()
            mock_plan.assert_called_once()
            mock_app.assert_called_once()
            mock_disp.assert_called_once()
            mock_eg.assert_called_once()
            # Devices called per device in config
            assert mock_device.call_count == 2
    
    def test_destroy_calls_all_destroy_functions(self, mock_context, mock_provider):
        """Should call all destroy functions in reverse order."""
        with patch("src.providers.azure.layers.layer_1_iot.destroy_iot_hub") as mock_hub, \
             patch("src.providers.azure.layers.layer_1_iot.destroy_managed_identity_roles") as mock_rbac, \
             patch("src.providers.azure.layers.layer_1_iot.destroy_l1_app_service_plan") as mock_plan, \
             patch("src.providers.azure.layers.layer_1_iot.destroy_l1_function_app") as mock_app, \
             patch("src.providers.azure.layers.layer_1_iot.destroy_dispatcher_function") as mock_disp, \
             patch("src.providers.azure.layers.layer_1_iot.destroy_event_grid_subscription") as mock_eg, \
             patch("src.providers.azure.layers.layer_1_iot.destroy_iot_device") as mock_device:
            
            from src.providers.azure.layers.l1_adapter import destroy_l1
            destroy_l1(mock_context, mock_provider)
            
            # Verify all destroy functions called
            mock_hub.assert_called_once()
            mock_rbac.assert_called_once()
            mock_plan.assert_called_once()
            mock_app.assert_called_once()
            mock_disp.assert_called_once()
            mock_eg.assert_called_once()
    
    def test_info_checks_all_components(self, mock_context, mock_provider):
        """Should check all L1 components and return status dict."""
        with patch("src.providers.azure.layers.layer_1_iot.info_l1") as mock_info:
            mock_info.return_value = {
                "iot_hub": True,
                "rbac_roles": True,
                "app_service_plan": True,
                "function_app": True,
            }
            
            from src.providers.azure.layers.l1_adapter import info_l1
            result = info_l1(mock_context, mock_provider)
            
            assert isinstance(result, dict)
            mock_info.assert_called_once()
    
    def test_info_returns_dict(self, mock_context, mock_provider):
        """Should return dictionary with component status."""
        with patch("src.providers.azure.layers.layer_1_iot.check_iot_hub", return_value=True), \
             patch("src.providers.azure.layers.layer_1_iot.check_managed_identity_roles", return_value=True), \
             patch("src.providers.azure.layers.layer_1_iot.check_l1_app_service_plan", return_value=True), \
             patch("src.providers.azure.layers.layer_1_iot.check_l1_function_app", return_value=True), \
             patch("src.providers.azure.layers.layer_1_iot.check_dispatcher_function", return_value=False), \
             patch("src.providers.azure.layers.layer_1_iot.check_event_grid_subscription", return_value=False), \
             patch("src.providers.azure.layers.layer_1_iot.check_iot_device", return_value=True):
            
            from src.providers.azure.layers.layer_1_iot import info_l1
            result = info_l1(mock_context, mock_provider)
            
            assert isinstance(result, dict)
            assert "iot_hub" in result
            assert "function_app" in result


# ==========================================
# TestPreDeploymentChecks
# ==========================================

class TestPreDeploymentChecks:
    """Tests for pre-flight dependency verification."""
    
    def test_deploy_fails_without_setup(self, mock_context, mock_provider):
        """Should raise RuntimeError if setup layer not deployed."""
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_setup:
            mock_setup.return_value = {
                "resource_group": True,
                "managed_identity": False,  # Not deployed
                "storage_account": True
            }
            
            from src.providers.azure.layers.l1_adapter import deploy_l1
            
            with pytest.raises(RuntimeError, match="Setup Layer not fully deployed"):
                deploy_l1(mock_context, mock_provider)
    
    def test_deploy_passes_with_setup(self, mock_context, mock_provider):
        """Should proceed when setup layer is deployed."""
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_setup, \
             patch("src.providers.azure.layers.layer_1_iot.create_iot_hub"), \
             patch("src.providers.azure.layers.layer_1_iot.assign_managed_identity_roles"), \
             patch("src.providers.azure.layers.layer_1_iot.create_l1_app_service_plan"), \
             patch("src.providers.azure.layers.layer_1_iot.create_l1_function_app"), \
             patch("src.providers.azure.layers.layer_1_iot.deploy_dispatcher_function"), \
             patch("src.providers.azure.layers.layer_1_iot.create_event_grid_subscription"), \
             patch("src.providers.azure.layers.layer_1_iot.create_iot_device"):
            
            mock_setup.return_value = {
                "resource_group": True,
                "managed_identity": True,
                "storage_account": True
            }
            
            from src.providers.azure.layers.l1_adapter import deploy_l1
            
            # Should not raise
            deploy_l1(mock_context, mock_provider)
    
    def test_verify_l0_for_multicloud(self, mock_context, mock_provider):
        """Should check L0 if Azure is L2 in multi-cloud."""
        # Set up multi-cloud: AWS L1 → Azure L2
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure"
        }
        
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_setup, \
             patch("src.providers.azure.layers.l0_adapter.info_l0") as mock_l0:
            
            mock_setup.return_value = {
                "resource_group": True,
                "managed_identity": True,
                "storage_account": True
            }
            
            mock_l0.return_value = {"function_app": False}
            
            from src.providers.azure.layers.l1_adapter import deploy_l1
            
            with pytest.raises(RuntimeError, match="L0 Glue Layer not deployed"):
                deploy_l1(mock_context, mock_provider)
    
    def test_simple_pass_fail_message(self, mock_context, mock_provider):
        """Should use simple error message without component details."""
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_setup:
            mock_setup.return_value = {
                "resource_group": False,
                "managed_identity": False,
                "storage_account": False
            }
            
            from src.providers.azure.layers.l1_adapter import deploy_l1
            
            with pytest.raises(RuntimeError) as exc_info:
                deploy_l1(mock_context, mock_provider)
            
            # Should NOT contain detailed status
            assert "resource_group=" not in str(exc_info.value)
            assert "Run deploy_setup first" in str(exc_info.value)


# ==========================================
# TestExceptionHandling
# ==========================================

class TestExceptionHandling:
    """Tests for comprehensive exception handling."""
    
    def test_client_auth_error_propagates(self, mock_provider):
        """Should re-raise ClientAuthenticationError."""
        from src.providers.azure.layers.layer_1_iot import check_iot_hub
        from azure.core.exceptions import ClientAuthenticationError
        
        mock_provider.clients["iothub"].iot_hub_resource.get.side_effect = ClientAuthenticationError("Permission denied")
        
        with pytest.raises(ClientAuthenticationError):
            check_iot_hub(mock_provider)
    
    def test_http_error_propagates(self, mock_provider):
        """Should re-raise HttpResponseError (except 404)."""
        from src.providers.azure.layers.layer_1_iot import create_iot_hub
        from azure.core.exceptions import HttpResponseError
        
        mock_provider.clients["iothub"].iot_hub_resource.begin_create_or_update.side_effect = HttpResponseError("Server error")
        
        with pytest.raises(HttpResponseError):
            create_iot_hub(mock_provider)
    
    def test_network_error_propagates(self, mock_provider):
        """Should re-raise ServiceRequestError."""
        from src.providers.azure.layers.layer_1_iot import check_iot_hub
        from azure.core.exceptions import ServiceRequestError
        
        mock_provider.clients["iothub"].iot_hub_resource.get.side_effect = ServiceRequestError("Network error")
        
        with pytest.raises(ServiceRequestError):
            check_iot_hub(mock_provider)
    
    def test_azure_error_catchall(self, mock_provider):
        """Should catch and re-raise generic AzureError."""
        from src.providers.azure.layers.layer_1_iot import check_iot_hub
        from azure.core.exceptions import AzureError
        
        mock_provider.clients["iothub"].iot_hub_resource.get.side_effect = AzureError("Unknown Azure error")
        
        with pytest.raises(AzureError):
            check_iot_hub(mock_provider)


# ==========================================
# TestSimulatorConfig
# ==========================================

class TestSimulatorConfig:
    """Tests for simulator configuration generation."""
    
    def test_generates_correct_structure(self, mock_config):
        """Should generate JSON with all required fields."""
        from src.providers.azure.layers.layer_1_iot import _generate_simulator_config
        
        device = {"id": "sensor-001"}
        conn_str = "HostName=hub.azure-devices.net;DeviceId=sensor-001;SharedAccessKey=key123"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            _generate_simulator_config(device, conn_str, mock_config, tmpdir)
            
            config_path = os.path.join(tmpdir, "iot_device_simulator", "azure", "config_generated.json")
            
            with open(config_path, "r") as f:
                data = json.load(f)
            
            assert "connection_string" in data
            assert "device_id" in data
            assert "digital_twin_name" in data
            assert "payload_path" in data
    
    def test_creates_directory(self, mock_config):
        """Should create iot_device_simulator/azure directory if not exists."""
        from src.providers.azure.layers.layer_1_iot import _generate_simulator_config
        
        device = {"id": "sensor-001"}
        conn_str = "HostName=hub.azure-devices.net;DeviceId=sensor-001;SharedAccessKey=key123"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            _generate_simulator_config(device, conn_str, mock_config, tmpdir)
            
            sim_dir = os.path.join(tmpdir, "iot_device_simulator", "azure")
            assert os.path.isdir(sim_dir)
    
    def test_stores_connection_string(self, mock_config):
        """Should store the full connection string."""
        from src.providers.azure.layers.layer_1_iot import _generate_simulator_config
        
        device = {"id": "sensor-001"}
        expected_conn_str = "HostName=test-hub.azure-devices.net;DeviceId=sensor-001;SharedAccessKey=secret123"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            _generate_simulator_config(device, expected_conn_str, mock_config, tmpdir)
            
            config_path = os.path.join(tmpdir, "iot_device_simulator", "azure", "config_generated.json")
            
            with open(config_path, "r") as f:
                data = json.load(f)
            
            assert data["connection_string"] == expected_conn_str
    
    def test_payload_path_relative(self, mock_config):
        """Should use relative path for payloads.json."""
        from src.providers.azure.layers.layer_1_iot import _generate_simulator_config
        
        device = {"id": "sensor-001"}
        conn_str = "HostName=test.azure-devices.net;DeviceId=sensor-001;SharedAccessKey=key"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            _generate_simulator_config(device, conn_str, mock_config, tmpdir)
            
            config_path = os.path.join(tmpdir, "iot_device_simulator", "azure", "config_generated.json")
            
            with open(config_path, "r") as f:
                data = json.load(f)
            
            assert data["payload_path"] == "../payloads.json"
