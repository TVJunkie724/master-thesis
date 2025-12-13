"""
Azure L2 (Compute/Data Processing) Unit Tests.

Comprehensive tests for all L2 components covering:
- Happy path: create, destroy, check functions work correctly
- Validation: fail-fast for missing required parameters
- Error handling: proper handling of ResourceNotFoundError and other exceptions
- Edge cases: partial deployment, duplicate resources, etc.

Test Classes:
    - TestL2AppServicePlan: App Service Plan create/destroy/check
    - TestL2FunctionApp: Function App create/destroy/check
    - TestPersisterFunction: Persister deployment
    - TestProcessorFunction: Per-device processor deployment
    - TestEventCheckerFunction: Event Checker deployment
    - TestEventFeedbackFunction: Event Feedback deployment
    - TestLogicAppWorkflow: Logic Apps create/destroy/check
    - TestEventActionFunctions: Dynamic event action deployment
    - TestL2Adapter: Adapter orchestration functions
    - TestPreDeploymentChecks: Pre-flight L1 dependency verification
    - TestExceptionHandling: Comprehensive exception handling
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
    provider.naming.resource_group.return_value = "rg-test-twin"
    provider.naming.l2_app_service_plan.return_value = "test-twin-l2-plan"
    provider.naming.l2_function_app.return_value = "test-twin-l2-functions"
    provider.naming.storage_account.return_value = "testtwinstore"
    provider.naming.managed_identity.return_value = "test-twin-identity"
    provider.naming.persister_function.return_value = "persister"
    provider.naming.event_checker_function.return_value = "event-checker"
    provider.naming.event_feedback_function.return_value = "event-feedback"
    provider.naming.logic_app_workflow.return_value = "test-twin-notification-workflow"
    provider.naming.processor_function.side_effect = lambda d: f"{d}-processor"
    
    # Mock clients
    provider.clients = {
        "web": MagicMock(),
        "storage": MagicMock(),
        "msi": MagicMock(),
        "logic": MagicMock(),
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
    config.events = []
    config.providers = {
        "layer_1_provider": "azure",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "azure",
    }
    config.is_optimization_enabled.side_effect = lambda opt: opt in ["useEventChecking"]
    return config


@pytest.fixture
def mock_context(mock_config):
    """Create a mock DeploymentContext for testing."""
    context = MagicMock()
    context.config = mock_config
    context.project_path = "/app/upload/test-project"
    return context


# ==========================================
# TestL2AppServicePlan
# ==========================================

class TestL2AppServicePlan:
    """Tests for L2 App Service Plan create/destroy/check functions."""
    
    def test_create_app_service_plan_success(self, mock_provider):
        """Should create L2 App Service Plan and return ID."""
        from src.providers.azure.layers.layer_2_compute import create_l2_app_service_plan
        
        # Setup mock
        mock_poller = MagicMock()
        mock_plan = MagicMock()
        mock_plan.id = "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Web/serverfarms/test-twin-l2-plan"
        mock_poller.result.return_value = mock_plan
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.return_value = mock_poller
        
        # Execute
        result = create_l2_app_service_plan(mock_provider)
        
        # Verify
        assert "/subscriptions" in result
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.assert_called_once()
    
    def test_create_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import create_l2_app_service_plan
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l2_app_service_plan(None)
    
    def test_destroy_app_service_plan_success(self, mock_provider):
        """Should delete L2 App Service Plan."""
        from src.providers.azure.layers.layer_2_compute import destroy_l2_app_service_plan
        
        destroy_l2_app_service_plan(mock_provider)
        
        mock_provider.clients["web"].app_service_plans.delete.assert_called_once()
    
    def test_destroy_handles_not_found(self, mock_provider):
        """Should handle ResourceNotFoundError gracefully in destroy."""
        from src.providers.azure.layers.layer_2_compute import destroy_l2_app_service_plan
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["web"].app_service_plans.delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_l2_app_service_plan(mock_provider)
    
    def test_check_plan_exists(self, mock_provider):
        """Should return True when plan exists."""
        from src.providers.azure.layers.layer_2_compute import check_l2_app_service_plan
        
        mock_provider.clients["web"].app_service_plans.get.return_value = MagicMock()
        
        result = check_l2_app_service_plan(mock_provider)
        
        assert result is True
    
    def test_check_plan_not_found(self, mock_provider):
        """Should return False when plan doesn't exist."""
        from src.providers.azure.layers.layer_2_compute import check_l2_app_service_plan
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["web"].app_service_plans.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_l2_app_service_plan(mock_provider)
        
        assert result is False


# ==========================================
# TestL2FunctionApp
# ==========================================

class TestL2FunctionApp:
    """Tests for L2 Function App create/destroy/check functions."""
    
    def test_create_function_app_success(self, mock_provider, mock_config):
        """Should create L2 Function App."""
        from src.providers.azure.layers.layer_2_compute import create_l2_function_app
        
        # Mock plan lookup
        mock_plan = MagicMock()
        mock_plan.id = "/subscriptions/test/plan"
        mock_provider.clients["web"].app_service_plans.get.return_value = mock_plan
        
        # Mock web app creation
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(name="test-twin-l2-functions")
        mock_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        # Mock storage keys
        mock_keys = MagicMock()
        mock_keys.keys = [MagicMock(value="test-key")]
        mock_provider.clients["storage"].storage_accounts.list_keys.return_value = mock_keys
        
        with patch("src.providers.azure.layers.layer_setup_azure.get_managed_identity_id") as mock_get_identity:
            mock_get_identity.return_value = "/subscriptions/test/identity"
            result = create_l2_function_app(mock_provider, mock_config)
        
        assert result == "test-twin-l2-functions"
    
    def test_create_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import create_l2_function_app
        
        with pytest.raises(ValueError, match="provider is required"):
            create_l2_function_app(None, mock_config)
    
    def test_create_validates_config(self, mock_provider):
        """Should raise ValueError if config is None."""
        from src.providers.azure.layers.layer_2_compute import create_l2_function_app
        
        with pytest.raises(ValueError, match="config is required"):
            create_l2_function_app(mock_provider, None)
    
    def test_destroy_function_app_success(self, mock_provider):
        """Should delete L2 Function App."""
        from src.providers.azure.layers.layer_2_compute import destroy_l2_function_app
        
        destroy_l2_function_app(mock_provider)
        
        mock_provider.clients["web"].web_apps.delete.assert_called_once()
    
    def test_destroy_handles_not_found(self, mock_provider):
        """Should handle ResourceNotFoundError gracefully in destroy."""
        from src.providers.azure.layers.layer_2_compute import destroy_l2_function_app
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["web"].web_apps.delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_l2_function_app(mock_provider)
    
    def test_check_function_app_exists(self, mock_provider):
        """Should return True when Function App exists."""
        from src.providers.azure.layers.layer_2_compute import check_l2_function_app
        
        mock_provider.clients["web"].web_apps.get.return_value = MagicMock()
        
        result = check_l2_function_app(mock_provider)
        
        assert result is True
    
    def test_check_function_app_not_found(self, mock_provider):
        """Should return False when Function App doesn't exist."""
        from src.providers.azure.layers.layer_2_compute import check_l2_function_app
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["web"].web_apps.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_l2_function_app(mock_provider)
        
        assert result is False


# ==========================================
# TestPersisterFunction
# ==========================================

class TestPersisterFunction:
    """Tests for Persister function deployment."""
    
    def test_deploy_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_persister_function
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_persister_function(None, "/test/path")
    
    def test_deploy_validates_path(self, mock_provider):
        """Should raise ValueError if project_path is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_persister_function
        
        with pytest.raises(ValueError, match="project_path is required"):
            deploy_persister_function(mock_provider, None)
    
    def test_destroy_no_error(self, mock_provider):
        """Should complete without error."""
        from src.providers.azure.layers.layer_2_compute import destroy_persister_function
        
        # Should not raise
        destroy_persister_function(mock_provider)
    
    def test_check_persister_exists(self, mock_provider):
        """Should return True when persister function exists."""
        from src.providers.azure.layers.layer_2_compute import check_persister_function
        
        mock_function = MagicMock()
        mock_function.name = "test-twin-l2-functions/persister"
        mock_provider.clients["web"].web_apps.list_functions.return_value = [mock_function]
        
        result = check_persister_function(mock_provider)
        
        assert result is True
    
    def test_check_persister_not_found(self, mock_provider):
        """Should return False when persister not in function list."""
        from src.providers.azure.layers.layer_2_compute import check_persister_function
        
        mock_function = MagicMock()
        mock_function.name = "test-twin-l2-functions/other-function"
        mock_provider.clients["web"].web_apps.list_functions.return_value = [mock_function]
        
        result = check_persister_function(mock_provider)
        
        assert result is False


# ==========================================
# TestProcessorFunction
# ==========================================

class TestProcessorFunction:
    """Tests for per-device Processor function deployment."""
    
    def test_deploy_validates_device(self, mock_provider, mock_config):
        """Should raise ValueError if iot_device is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_processor_function
        
        with pytest.raises(ValueError, match="iot_device is required"):
            deploy_processor_function(None, mock_provider, mock_config, "/test")
    
    def test_deploy_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_processor_function
        
        device = {"id": "sensor-001"}
        with pytest.raises(ValueError, match="provider is required"):
            deploy_processor_function(device, None, mock_config, "/test")
    
    def test_destroy_validates_device(self, mock_provider):
        """Should raise ValueError if iot_device is None."""
        from src.providers.azure.layers.layer_2_compute import destroy_processor_function
        
        with pytest.raises(ValueError, match="iot_device is required"):
            destroy_processor_function(None, mock_provider)
    
    def test_check_processor_validates_device(self, mock_provider):
        """Should raise ValueError if iot_device is None."""
        from src.providers.azure.layers.layer_2_compute import check_processor_function
        
        with pytest.raises(ValueError, match="iot_device is required"):
            check_processor_function(None, mock_provider)
    
    def test_check_processor_exists(self, mock_provider):
        """Should return True when processor function exists for device."""
        from src.providers.azure.layers.layer_2_compute import check_processor_function
        
        device = {"id": "sensor-001"}
        mock_function = MagicMock()
        mock_function.name = "test-twin-l2-functions/sensor-001-processor"
        mock_provider.clients["web"].web_apps.list_functions.return_value = [mock_function]
        
        result = check_processor_function(device, mock_provider)
        
        assert result is True


# ==========================================
# TestEventCheckerFunction
# ==========================================

class TestEventCheckerFunction:
    """Tests for Event Checker function deployment."""
    
    def test_deploy_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_event_checker_function
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_event_checker_function(None, mock_config, "/test")
    
    def test_deploy_validates_config(self, mock_provider):
        """Should raise ValueError if config is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_event_checker_function
        
        with pytest.raises(ValueError, match="config is required"):
            deploy_event_checker_function(mock_provider, None, "/test")
    
    def test_destroy_no_error(self, mock_provider):
        """Should complete without error."""
        from src.providers.azure.layers.layer_2_compute import destroy_event_checker_function
        
        # Should not raise
        destroy_event_checker_function(mock_provider)
    
    def test_check_event_checker_exists(self, mock_provider):
        """Should return True when event-checker function exists."""
        from src.providers.azure.layers.layer_2_compute import check_event_checker_function
        
        mock_function = MagicMock()
        mock_function.name = "test-twin-l2-functions/event-checker"
        mock_provider.clients["web"].web_apps.list_functions.return_value = [mock_function]
        
        result = check_event_checker_function(mock_provider)
        
        assert result is True


# ==========================================
# TestEventFeedbackFunction
# ==========================================

class TestEventFeedbackFunction:
    """Tests for Event Feedback function deployment."""
    
    def test_deploy_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_event_feedback_function
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_event_feedback_function(None, mock_config, "/test")
    
    def test_deploy_validates_config(self, mock_provider):
        """Should raise ValueError if config is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_event_feedback_function
        
        with pytest.raises(ValueError, match="config is required"):
            deploy_event_feedback_function(mock_provider, None, "/test")
    
    def test_destroy_no_error(self, mock_provider):
        """Should complete without error."""
        from src.providers.azure.layers.layer_2_compute import destroy_event_feedback_function
        
        # Should not raise
        destroy_event_feedback_function(mock_provider)


# ==========================================
# TestLogicAppWorkflow
# ==========================================

class TestLogicAppWorkflow:
    """Tests for Logic Apps Workflow create/destroy/check functions."""
    
    def test_create_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import create_logic_app_workflow
        
        with pytest.raises(ValueError, match="provider is required"):
            create_logic_app_workflow(None, mock_config)
    
    def test_create_validates_config(self, mock_provider):
        """Should raise ValueError if config is None."""
        from src.providers.azure.layers.layer_2_compute import create_logic_app_workflow
        
        with pytest.raises(ValueError, match="config is required"):
            create_logic_app_workflow(mock_provider, None)
    
    def test_destroy_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import destroy_logic_app_workflow
        
        with pytest.raises(ValueError, match="provider is required"):
            destroy_logic_app_workflow(None)
    
    def test_check_validates_provider(self):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import check_logic_app_workflow
        
        with pytest.raises(ValueError, match="provider is required"):
            check_logic_app_workflow(None)
    
    def test_check_workflow_not_found(self, mock_provider):
        """Should return False when workflow not found."""
        from src.providers.azure.layers.layer_2_compute import check_logic_app_workflow
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_provider.clients["logic"].workflows.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_logic_app_workflow(mock_provider)
        
        assert result is False


# ==========================================
# TestEventActionFunctions
# ==========================================

class TestEventActionFunctions:
    """Tests for dynamic Event Action function deployment."""
    
    def test_deploy_validates_provider(self, mock_config):
        """Should raise ValueError if provider is None."""
        from src.providers.azure.layers.layer_2_compute import deploy_event_action_functions
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_event_action_functions(None, mock_config, "/test")
    
    def test_deploy_skips_when_no_events(self, mock_provider, mock_config):
        """Should skip deployment when no events configured."""
        from src.providers.azure.layers.layer_2_compute import deploy_event_action_functions
        
        mock_config.events = []
        
        # Should not raise, should complete without any deployment
        deploy_event_action_functions(mock_provider, mock_config, "/test")
    
    def test_check_returns_empty_when_no_events(self, mock_provider, mock_config):
        """Should return empty dict when no events configured."""
        from src.providers.azure.layers.layer_2_compute import check_event_action_functions
        
        mock_config.events = []
        
        result = check_event_action_functions(mock_provider, mock_config)
        
        assert result == {}


# ==========================================
# TestL2Adapter
# ==========================================

class TestL2Adapter:
    """Tests for L2 adapter orchestration functions."""
    
    def test_deploy_fails_without_l1(self, mock_context, mock_provider):
        """Should raise RuntimeError if L1 layer not deployed."""
        with patch("src.providers.azure.layers.l1_adapter.info_l1") as mock_l1_info:
            mock_l1_info.return_value = {
                "iot_hub": False,
                "function_app": False,
            }
            
            from src.providers.azure.layers.l2_adapter import deploy_l2
            
            with pytest.raises(RuntimeError, match="L1 Layer not fully deployed"):
                deploy_l2(mock_context, mock_provider)
    
    def test_info_returns_dict(self, mock_context, mock_provider):
        """Should return dictionary with component status."""
        with patch("src.providers.azure.layers.layer_2_compute.check_l2_app_service_plan", return_value=True), \
             patch("src.providers.azure.layers.layer_2_compute.check_l2_function_app", return_value=True), \
             patch("src.providers.azure.layers.layer_2_compute.check_persister_function", return_value=False), \
             patch("src.providers.azure.layers.layer_2_compute.check_processor_function", return_value=False), \
             patch("src.providers.azure.layers.layer_2_compute.check_event_checker_function", return_value=False), \
             patch("src.providers.azure.layers.layer_2_compute.check_event_feedback_function", return_value=False), \
             patch("src.providers.azure.layers.layer_2_compute.check_logic_app_workflow", return_value=False), \
             patch("src.providers.azure.layers.layer_2_compute.check_event_action_functions", return_value={}):
            
            from src.providers.azure.layers.layer_2_compute import info_l2
            result = info_l2(mock_context, mock_provider)
            
            assert isinstance(result, dict)
            assert "app_service_plan" in result
            assert "function_app" in result


# ==========================================
# TestPreDeploymentChecks
# ==========================================

class TestPreDeploymentChecks:
    """Tests for pre-flight L1 dependency verification."""
    
    def test_deploy_passes_with_l1(self, mock_context, mock_provider):
        """Should proceed when L1 layer is deployed."""
        with patch("src.providers.azure.layers.l1_adapter.info_l1") as mock_l1_info, \
             patch("src.providers.azure.layers.layer_2_compute.create_l2_app_service_plan"), \
             patch("src.providers.azure.layers.layer_2_compute.create_l2_function_app"), \
             patch("src.providers.azure.layers.layer_2_compute.deploy_persister_function"), \
             patch("src.providers.azure.layers.layer_2_compute.deploy_processor_function"), \
             patch("src.providers.azure.layers.layer_2_compute.deploy_event_checker_function"):
            
            mock_l1_info.return_value = {
                "iot_hub": True,
                "function_app": True,
            }
            
            from src.providers.azure.layers.l2_adapter import deploy_l2
            
            # Should not raise
            deploy_l2(mock_context, mock_provider)


# ==========================================
# TestExceptionHandling
# ==========================================

class TestExceptionHandling:
    """Tests for comprehensive exception handling."""
    
    def test_create_plan_handles_auth_error(self, mock_provider):
        """Should propagate ClientAuthenticationError."""
        from src.providers.azure.layers.layer_2_compute import create_l2_app_service_plan
        from azure.core.exceptions import ClientAuthenticationError
        
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.side_effect = \
            ClientAuthenticationError("Permission denied")
        
        with pytest.raises(ClientAuthenticationError):
            create_l2_app_service_plan(mock_provider)
    
    def test_create_plan_handles_http_error(self, mock_provider):
        """Should propagate HttpResponseError."""
        from src.providers.azure.layers.layer_2_compute import create_l2_app_service_plan
        from azure.core.exceptions import HttpResponseError
        
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.side_effect = \
            HttpResponseError("Request failed")
        
        with pytest.raises(HttpResponseError):
            create_l2_app_service_plan(mock_provider)
    
    def test_destroy_plan_handles_auth_error(self, mock_provider):
        """Should propagate ClientAuthenticationError on destroy."""
        from src.providers.azure.layers.layer_2_compute import destroy_l2_app_service_plan
        from azure.core.exceptions import ClientAuthenticationError
        
        mock_provider.clients["web"].app_service_plans.delete.side_effect = \
            ClientAuthenticationError("Permission denied")
        
        with pytest.raises(ClientAuthenticationError):
            destroy_l2_app_service_plan(mock_provider)


# ==========================================
# TestNamingIntegration
# ==========================================

class TestNamingIntegration:
    """Tests for naming integration with new L2 functions."""
    
    def test_l2_app_service_plan_naming(self):
        """Should generate correct L2 App Service Plan name."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("my-twin")
        
        assert naming.l2_app_service_plan() == "my-twin-l2-plan"
    
    def test_logic_app_workflow_naming(self):
        """Should generate correct Logic App Workflow name."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("my-twin")
        
        assert naming.logic_app_workflow() == "my-twin-notification-workflow"
    
    def test_l2_function_app_naming(self):
        """Should generate correct L2 Function App name."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("my-twin")
        
        assert naming.l2_function_app() == "my-twin-l2-functions"
    
    def test_processor_function_naming(self):
        """Should generate correct processor function name."""
        from src.providers.azure.naming import AzureNaming
        
        naming = AzureNaming("my-twin")
        
        assert naming.processor_function("sensor-001") == "sensor-001-processor"
