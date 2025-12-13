"""
Azure Layer 0 (Glue) Component Edge Case Tests.

Tests for multi-cloud receiver components deployed by L0 adapter:
- Function App management
- Ingestion Function (L1→L2)
- Hot Writer Function (L2→L3)
- Cold Writer Function (L3 Hot→L3 Cold)
- Archive Writer Function (L3 Cold→L3 Archive)
- Hot Reader Endpoints (L3→L4)
- L0 Adapter provider boundary detection

These tests mirror the AWS `test_l0_glue_edge_cases.py` pattern.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from azure.core.exceptions import ResourceNotFoundError


# ==========================================
# Function App Edge Case Tests
# ==========================================

class TestFunctionAppEdgeCases:
    """Edge case tests for L0 Glue Function App."""
    
    @patch("src.providers.azure.layers.layer_0_glue._deploy_glue_functions")
    @patch("src.providers.azure.layers.layer_setup_azure.get_managed_identity_id")
    @patch("src.providers.azure.layers.layer_0_glue._configure_function_app_settings")
    def test_create_glue_function_app_success(self, mock_settings, mock_identity, mock_deploy):
        """create_glue_function_app() should create with correct config."""
        from src.providers.azure.layers.layer_0_glue import create_glue_function_app
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.location = "westeurope"
        mock_poller = MagicMock()
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        mock_identity.return_value = "/subscriptions/xxx/identity"
        mock_config = MagicMock()
        
        result = create_glue_function_app(mock_provider, mock_config)
        
        assert result == "test-twin-l0-functions"
        mock_provider.clients["web"].web_apps.begin_create_or_update.assert_called_once()
    
    @patch("src.providers.azure.layers.layer_0_glue._deploy_glue_functions")
    @patch("src.providers.azure.layers.layer_setup_azure.get_managed_identity_id")
    @patch("src.providers.azure.layers.layer_0_glue._configure_function_app_settings")
    def test_create_glue_function_app_assigns_managed_identity(self, mock_settings, mock_identity, mock_deploy):
        """create_glue_function_app() should assign managed identity."""
        from src.providers.azure.layers.layer_0_glue import create_glue_function_app
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.naming.storage_account.return_value = "testtwinstorage"
        mock_provider.location = "westeurope"
        mock_poller = MagicMock()
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].web_apps.begin_create_or_update.return_value = mock_poller
        
        mock_identity.return_value = "/subscriptions/xxx/identity"
        mock_config = MagicMock()
        
        create_glue_function_app(mock_provider, mock_config)
        
        call_args = mock_provider.clients["web"].web_apps.begin_create_or_update.call_args
        assert "identity" in call_args.kwargs["site_envelope"]
        assert call_args.kwargs["site_envelope"]["identity"]["type"] == "UserAssigned"
    
    def test_destroy_glue_function_app_success(self):
        """destroy_glue_function_app() should delete Function App."""
        from src.providers.azure.layers.layer_0_glue import destroy_glue_function_app
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.clients = {"web": MagicMock()}
        
        destroy_glue_function_app(mock_provider)
        
        mock_provider.clients["web"].web_apps.delete.assert_called_once()
    
    def test_destroy_glue_function_app_not_found_handles_gracefully(self):
        """destroy_glue_function_app() should handle NotFound gracefully."""
        from src.providers.azure.layers.layer_0_glue import destroy_glue_function_app
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].web_apps.delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_glue_function_app(mock_provider)
    
    def test_check_glue_function_app_exists_returns_true(self):
        """check_glue_function_app() should return True when exists."""
        from src.providers.azure.layers.layer_0_glue import check_glue_function_app
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.clients = {"web": MagicMock()}
        
        result = check_glue_function_app(mock_provider)
        
        assert result is True
    
    def test_check_glue_function_app_missing_returns_false(self):
        """check_glue_function_app() should return False when missing."""
        from src.providers.azure.layers.layer_0_glue import check_glue_function_app
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].web_apps.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_glue_function_app(mock_provider)
        
        assert result is False


# ==========================================
# App Service Plan Edge Case Tests
# ==========================================

class TestAppServicePlanEdgeCases:
    """Edge case tests for App Service Plan (Consumption/Y1)."""
    
    def test_create_consumption_app_service_plan_success(self):
        """create_consumption_app_service_plan() should create Y1 plan."""
        from src.providers.azure.layers.layer_0_glue import create_consumption_app_service_plan
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_app_service_plan.return_value = "test-twin-l0-plan"
        mock_provider.location = "westeurope"
        mock_provider.subscription_id = "00000000-0000-0000-0000-000000000000"
        mock_poller = MagicMock()
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.return_value = mock_poller
        
        result = create_consumption_app_service_plan(mock_provider)
        
        assert "test-twin-l0-plan" in result
        mock_provider.clients["web"].app_service_plans.begin_create_or_update.assert_called_once()
        call_args = mock_provider.clients["web"].app_service_plans.begin_create_or_update.call_args
        assert call_args.kwargs["app_service_plan"]["sku"]["name"] == "Y1"
        assert call_args.kwargs["app_service_plan"]["sku"]["tier"] == "Dynamic"
    
    def test_destroy_consumption_app_service_plan_success(self):
        """destroy_consumption_app_service_plan() should delete plan."""
        from src.providers.azure.layers.layer_0_glue import destroy_consumption_app_service_plan
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_app_service_plan.return_value = "test-twin-l0-plan"
        mock_provider.clients = {"web": MagicMock()}
        
        destroy_consumption_app_service_plan(mock_provider)
        
        mock_provider.clients["web"].app_service_plans.delete.assert_called_once()
    
    def test_destroy_consumption_app_service_plan_not_found_handles_gracefully(self):
        """destroy_consumption_app_service_plan() should handle NotFound gracefully."""
        from src.providers.azure.layers.layer_0_glue import destroy_consumption_app_service_plan
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_app_service_plan.return_value = "test-twin-l0-plan"
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].app_service_plans.delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_consumption_app_service_plan(mock_provider)
    
    def test_check_consumption_app_service_plan_exists_returns_true(self):
        """check_consumption_app_service_plan() should return True when exists."""
        from src.providers.azure.layers.layer_0_glue import check_consumption_app_service_plan
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_app_service_plan.return_value = "test-twin-l0-plan"
        mock_provider.clients = {"web": MagicMock()}
        
        result = check_consumption_app_service_plan(mock_provider)
        
        assert result is True
        mock_provider.clients["web"].app_service_plans.get.assert_called_once()
    
    def test_check_consumption_app_service_plan_missing_returns_false(self):
        """check_consumption_app_service_plan() should return False when missing."""
        from src.providers.azure.layers.layer_0_glue import check_consumption_app_service_plan
        
        mock_provider = MagicMock()
        mock_provider.naming.resource_group.return_value = "rg-test-twin"
        mock_provider.naming.glue_app_service_plan.return_value = "test-twin-l0-plan"
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].app_service_plans.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_consumption_app_service_plan(mock_provider)
        
        assert result is False


# ==========================================
# Destroy Function Edge Case Tests
# ==========================================

class TestDestroyFunctionEdgeCases:
    """Edge case tests for destroy functions that remove tokens."""
    
    @patch("src.providers.azure.layers.layer_0_glue._remove_function_app_setting")
    def test_destroy_ingestion_function_removes_token(self, mock_remove):
        """destroy_ingestion_function() should remove INTER_CLOUD_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import destroy_ingestion_function
        
        mock_provider = MagicMock()
        
        destroy_ingestion_function(mock_provider)
        
        mock_remove.assert_called_once_with(mock_provider, "INTER_CLOUD_TOKEN")
    
    @patch("src.providers.azure.layers.layer_0_glue._remove_function_app_setting")
    def test_destroy_hot_writer_function_removes_token(self, mock_remove):
        """destroy_hot_writer_function() should remove HOT_WRITER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import destroy_hot_writer_function
        
        mock_provider = MagicMock()
        
        destroy_hot_writer_function(mock_provider)
        
        mock_remove.assert_called_once_with(mock_provider, "HOT_WRITER_TOKEN")
    
    @patch("src.providers.azure.layers.layer_0_glue._remove_function_app_setting")
    def test_destroy_cold_writer_function_removes_token(self, mock_remove):
        """destroy_cold_writer_function() should remove COLD_WRITER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import destroy_cold_writer_function
        
        mock_provider = MagicMock()
        
        destroy_cold_writer_function(mock_provider)
        
        mock_remove.assert_called_once_with(mock_provider, "COLD_WRITER_TOKEN")
    
    @patch("src.providers.azure.layers.layer_0_glue._remove_function_app_setting")
    def test_destroy_archive_writer_function_removes_token(self, mock_remove):
        """destroy_archive_writer_function() should remove ARCHIVE_WRITER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import destroy_archive_writer_function
        
        mock_provider = MagicMock()
        
        destroy_archive_writer_function(mock_provider)
        
        mock_remove.assert_called_once_with(mock_provider, "ARCHIVE_WRITER_TOKEN")
    
    @patch("src.providers.azure.layers.layer_0_glue._remove_function_app_setting")
    def test_destroy_hot_reader_endpoint_removes_token(self, mock_remove):
        """destroy_hot_reader_endpoint() should remove HOT_READER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import destroy_hot_reader_endpoint
        
        mock_provider = MagicMock()
        
        destroy_hot_reader_endpoint(mock_provider)
        
        mock_remove.assert_called_once_with(mock_provider, "HOT_READER_TOKEN")
    
    def test_destroy_hot_reader_last_entry_endpoint_is_noop(self):
        """destroy_hot_reader_last_entry_endpoint() should not remove token (shared)."""
        from src.providers.azure.layers.layer_0_glue import destroy_hot_reader_last_entry_endpoint
        
        mock_provider = MagicMock()
        
        # Should not raise and not call any SDK methods
        destroy_hot_reader_last_entry_endpoint(mock_provider)


# ==========================================
# Token Validation Edge Case Tests
# ==========================================

class TestTokenValidationEdgeCases:
    """Edge case tests for token validation in deploy functions."""
    
    def test_deploy_ingestion_function_empty_token_raises(self):
        """deploy_ingestion_function() should raise ValueError for empty token."""
        from src.providers.azure.layers.layer_0_glue import deploy_ingestion_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_ingestion_function(mock_provider, mock_config, "")
    
    def test_deploy_hot_writer_function_empty_token_raises(self):
        """deploy_hot_writer_function() should raise ValueError for empty token."""
        from src.providers.azure.layers.layer_0_glue import deploy_hot_writer_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_hot_writer_function(mock_provider, mock_config, "")
    
    def test_deploy_cold_writer_function_empty_token_raises(self):
        """deploy_cold_writer_function() should raise ValueError for empty token."""
        from src.providers.azure.layers.layer_0_glue import deploy_cold_writer_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_cold_writer_function(mock_provider, mock_config, "")
    
    def test_deploy_archive_writer_function_empty_token_raises(self):
        """deploy_archive_writer_function() should raise ValueError for empty token."""
        from src.providers.azure.layers.layer_0_glue import deploy_archive_writer_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_archive_writer_function(mock_provider, mock_config, "")


# ==========================================
# Function App Identity Edge Cases
# ==========================================

class TestFunctionAppIdentityEdgeCases:
    """Edge case tests for Function App managed identity handling."""
    
    @patch("src.providers.azure.layers.layer_setup_azure.get_managed_identity_id")
    def test_create_glue_function_app_missing_identity_raises(self, mock_get_identity):
        """create_glue_function_app() should raise ValueError if identity not found."""
        from src.providers.azure.layers.layer_0_glue import create_glue_function_app
        
        mock_get_identity.return_value = None  # Identity not found
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="Managed Identity not found"):
            create_glue_function_app(mock_provider, mock_config)


# ==========================================
# L0 Adapter Destroy Flow Edge Cases
# ==========================================

class TestDestroyL0AdapterEdgeCases:
    """Edge case tests for destroy_l0 adapter function."""
    
    @patch("src.providers.azure.layers.layer_0_glue.destroy_consumption_app_service_plan")
    @patch("src.providers.azure.layers.l0_adapter.destroy_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.destroy_hot_reader_last_entry_endpoint")
    @patch("src.providers.azure.layers.l0_adapter.destroy_hot_reader_endpoint")
    @patch("src.providers.azure.layers.l0_adapter.destroy_archive_writer_function")
    @patch("src.providers.azure.layers.l0_adapter.destroy_cold_writer_function")
    @patch("src.providers.azure.layers.l0_adapter.destroy_hot_writer_function")
    @patch("src.providers.azure.layers.l0_adapter.destroy_ingestion_function")
    def test_destroy_l0_calls_all_destroy_functions(
        self, mock_ingestion, mock_hot_writer, mock_cold_writer, 
        mock_archive_writer, mock_hot_reader, mock_hot_reader_last, 
        mock_function_app, mock_app_service_plan
    ):
        """destroy_l0() should call all destroy functions including App Service Plan."""
        from src.providers.azure.layers.l0_adapter import destroy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_provider = MagicMock()
        
        destroy_l0(mock_context, mock_provider)
        
        # Verify all destroy functions called
        mock_ingestion.assert_called_once()
        mock_hot_writer.assert_called_once()
        mock_cold_writer.assert_called_once()
        mock_archive_writer.assert_called_once()
        mock_hot_reader.assert_called_once()
        mock_hot_reader_last.assert_called_once()
        mock_function_app.assert_called_once()
        mock_app_service_plan.assert_called_once()


# ==========================================
# Info L0 App Service Plan Edge Cases
# ==========================================

class TestInfoL0AppServicePlanEdgeCases:
    """Edge case tests for info_l0 App Service Plan checking."""
    
    @patch("src.providers.azure.layers.l0_adapter.check_consumption_app_service_plan")
    @patch("src.providers.azure.layers.l0_adapter.check_glue_function_app")
    def test_info_l0_checks_app_service_plan(self, mock_check_app, mock_check_plan):
        """info_l0() should check App Service Plan status."""
        from src.providers.azure.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_provider = MagicMock()
        mock_check_plan.return_value = True
        mock_check_app.return_value = True
        
        result = info_l0(mock_context, mock_provider)
        
        mock_check_plan.assert_called_once_with(mock_provider)
        assert result["app_service_plan"] is True


# ==========================================
# Ingestion Function Edge Case Tests
# ==========================================

class TestIngestionEdgeCases:
    """Edge case tests for Ingestion Function (L1→L2 boundary)."""
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_ingestion_function_success(self, mock_add_setting):
        """deploy_ingestion_function() should deploy function."""
        from src.providers.azure.layers.layer_0_glue import deploy_ingestion_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0-functions"
        mock_provider.naming.ingestion_function.return_value = "ingestion"
        mock_config = MagicMock()
        
        result = deploy_ingestion_function(mock_provider, mock_config, "test-token")
        
        assert "https://test-twin-l0-functions.azurewebsites.net/api/ingestion" in result
    
    def test_deploy_ingestion_function_missing_token_fails(self):
        """deploy_ingestion_function() should fail when token is missing."""
        from src.providers.azure.layers.layer_0_glue import deploy_ingestion_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_ingestion_function(mock_provider, mock_config, None)
    
    def test_deploy_ingestion_function_empty_token_fails(self):
        """deploy_ingestion_function() should fail when token is empty."""
        from src.providers.azure.layers.layer_0_glue import deploy_ingestion_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_ingestion_function(mock_provider, mock_config, "")
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_ingestion_function_sets_env_vars(self, mock_add_setting):
        """deploy_ingestion_function() should set INTER_CLOUD_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import deploy_ingestion_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.ingestion_function.return_value = "ingestion"
        mock_config = MagicMock()
        
        deploy_ingestion_function(mock_provider, mock_config, "secret-token")
        
        mock_add_setting.assert_called_with(mock_provider, "INTER_CLOUD_TOKEN", "secret-token")
    
    @patch("src.providers.azure.layers.layer_0_glue.check_glue_function_app")
    def test_check_ingestion_function_exists_returns_true(self, mock_check_app):
        """check_ingestion_function() should return True when exists."""
        from src.providers.azure.layers.layer_0_glue import check_ingestion_function
        
        mock_check_app.return_value = True
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_function.return_value = "ingestion"
        
        result = check_ingestion_function(mock_provider)
        
        assert result is True
    
    @patch("src.providers.azure.layers.layer_0_glue.check_glue_function_app")
    def test_check_ingestion_function_missing_returns_false(self, mock_check_app):
        """check_ingestion_function() should return False when app missing."""
        from src.providers.azure.layers.layer_0_glue import check_ingestion_function
        
        mock_check_app.return_value = False
        mock_provider = MagicMock()
        
        result = check_ingestion_function(mock_provider)
        
        assert result is False


# ==========================================
# Hot Writer Function Edge Case Tests
# ==========================================

class TestHotWriterEdgeCases:
    """Edge case tests for Hot Writer Function (L2→L3 boundary)."""
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_hot_writer_success(self, mock_add_setting):
        """deploy_hot_writer_function() should deploy with Cosmos DB config."""
        from src.providers.azure.layers.layer_0_glue import deploy_hot_writer_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.hot_writer_function.return_value = "hot-writer"
        mock_config = MagicMock()
        
        result = deploy_hot_writer_function(mock_provider, mock_config, "test-token")
        
        assert "hot-writer" in result
    
    def test_deploy_hot_writer_missing_token_fails(self):
        """deploy_hot_writer_function() should fail when token is missing."""
        from src.providers.azure.layers.layer_0_glue import deploy_hot_writer_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_hot_writer_function(mock_provider, mock_config, None)
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_hot_writer_sets_token_setting(self, mock_add_setting):
        """deploy_hot_writer_function() should set HOT_WRITER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import deploy_hot_writer_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.hot_writer_function.return_value = "hot-writer"
        mock_config = MagicMock()
        
        deploy_hot_writer_function(mock_provider, mock_config, "hw-token")
        
        mock_add_setting.assert_called_with(mock_provider, "HOT_WRITER_TOKEN", "hw-token")
    
    @patch("src.providers.azure.layers.layer_0_glue.check_glue_function_app")
    def test_check_hot_writer_exists_returns_true(self, mock_check_app):
        """check_hot_writer_function() should return True when exists."""
        from src.providers.azure.layers.layer_0_glue import check_hot_writer_function
        
        mock_check_app.return_value = True
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_function.return_value = "hot-writer"
        
        result = check_hot_writer_function(mock_provider)
        
        assert result is True


# ==========================================
# Cold Writer Function Edge Case Tests
# ==========================================

class TestColdWriterEdgeCases:
    """Edge case tests for Cold Writer Function (L3 Hot→Cold boundary)."""
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_cold_writer_success(self, mock_add_setting):
        """deploy_cold_writer_function() should deploy with Blob config."""
        from src.providers.azure.layers.layer_0_glue import deploy_cold_writer_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.cold_writer_function.return_value = "cold-writer"
        mock_config = MagicMock()
        
        result = deploy_cold_writer_function(mock_provider, mock_config, "test-token")
        
        assert "cold-writer" in result
    
    def test_deploy_cold_writer_missing_token_fails(self):
        """deploy_cold_writer_function() should fail when token is missing."""
        from src.providers.azure.layers.layer_0_glue import deploy_cold_writer_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_cold_writer_function(mock_provider, mock_config, "")
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_cold_writer_sets_token_setting(self, mock_add_setting):
        """deploy_cold_writer_function() should set COLD_WRITER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import deploy_cold_writer_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.cold_writer_function.return_value = "cold-writer"
        mock_config = MagicMock()
        
        deploy_cold_writer_function(mock_provider, mock_config, "cw-token")
        
        mock_add_setting.assert_called_with(mock_provider, "COLD_WRITER_TOKEN", "cw-token")


# ==========================================
# Archive Writer Function Edge Case Tests
# ==========================================

class TestArchiveWriterEdgeCases:
    """Edge case tests for Archive Writer Function (L3 Cold→Archive boundary)."""
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_deploy_archive_writer_success(self, mock_add_setting):
        """deploy_archive_writer_function() should deploy function."""
        from src.providers.azure.layers.layer_0_glue import deploy_archive_writer_function
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.archive_writer_function.return_value = "archive-writer"
        mock_config = MagicMock()
        
        result = deploy_archive_writer_function(mock_provider, mock_config, "test-token")
        
        assert "archive-writer" in result
    
    def test_deploy_archive_writer_missing_token_fails(self):
        """deploy_archive_writer_function() should fail when token is missing."""
        from src.providers.azure.layers.layer_0_glue import deploy_archive_writer_function
        
        mock_provider = MagicMock()
        mock_config = MagicMock()
        
        with pytest.raises(ValueError, match="expected_token not set"):
            deploy_archive_writer_function(mock_provider, mock_config, None)


# ==========================================
# Hot Reader Endpoint Edge Case Tests
# ==========================================

class TestHotReaderEndpointEdgeCases:
    """Edge case tests for Hot Reader endpoints (L3→L4 boundary)."""
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_create_hot_reader_endpoint_returns_url(self, mock_add_setting):
        """create_hot_reader_endpoint() should return HTTPS URL."""
        from src.providers.azure.layers.layer_0_glue import create_hot_reader_endpoint
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.hot_reader_function.return_value = "hot-reader"
        
        result = create_hot_reader_endpoint(mock_provider, "test-token")
        
        assert result.startswith("https://")
        assert "hot-reader" in result
    
    @patch("src.providers.azure.layers.layer_0_glue._add_function_app_setting")
    def test_create_hot_reader_endpoint_sets_token(self, mock_add_setting):
        """create_hot_reader_endpoint() should set HOT_READER_TOKEN."""
        from src.providers.azure.layers.layer_0_glue import create_hot_reader_endpoint
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.hot_reader_function.return_value = "hot-reader"
        
        create_hot_reader_endpoint(mock_provider, "hr-token")
        
        mock_add_setting.assert_called_with(mock_provider, "HOT_READER_TOKEN", "hr-token")
    
    def test_create_hot_reader_last_entry_endpoint_works(self):
        """create_hot_reader_last_entry_endpoint() should return URL."""
        from src.providers.azure.layers.layer_0_glue import create_hot_reader_last_entry_endpoint
        
        mock_provider = MagicMock()
        mock_provider.naming.glue_function_app.return_value = "test-twin-l0"
        mock_provider.naming.hot_reader_last_entry_function.return_value = "hot-reader-last-entry"
        
        result = create_hot_reader_last_entry_endpoint(mock_provider, "test-token")
        
        assert "hot-reader-last-entry" in result
    
    @patch("src.providers.azure.layers.layer_0_glue.check_glue_function_app")
    def test_check_hot_reader_endpoint_exists_returns_true(self, mock_check_app):
        """check_hot_reader_endpoint() should return True when exists."""
        from src.providers.azure.layers.layer_0_glue import check_hot_reader_endpoint
        
        mock_check_app.return_value = True
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_function.return_value = "hot-reader"
        
        result = check_hot_reader_endpoint(mock_provider)
        
        assert result is True
    
    @patch("src.providers.azure.layers.layer_0_glue.check_glue_function_app")
    def test_check_hot_reader_endpoint_missing_returns_false(self, mock_check_app):
        """check_hot_reader_endpoint() should return False when app missing."""
        from src.providers.azure.layers.layer_0_glue import check_hot_reader_endpoint
        
        mock_check_app.return_value = False
        mock_provider = MagicMock()
        
        result = check_hot_reader_endpoint(mock_provider)
        
        assert result is False


# ==========================================
# L0 Adapter Provider Boundary Tests
# ==========================================

class TestL0ProviderBoundaryDetection:
    """Tests for L0 adapter provider boundary detection."""
    
    @patch("src.providers.azure.layers.l0_adapter.create_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.save_inter_cloud_connection")
    def test_deploy_l0_same_cloud_skips_ingestion(self, mock_save, mock_create_app):
        """deploy_l0() should NOT deploy Ingestion when L1 == L2."""
        from src.providers.azure.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",  # Same!
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_context.project_path = "/app/projects/test"
        mock_provider = MagicMock()
        
        deploy_l0(mock_context, mock_provider)
        
        # No Function App should be created (all same cloud)
        mock_create_app.assert_not_called()
    
    @patch("src.providers.azure.layers.l0_adapter.create_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.deploy_ingestion_function")
    @patch("src.providers.azure.layers.l0_adapter.save_inter_cloud_connection")
    def test_deploy_l0_different_l1_l2_deploys_ingestion(
        self, mock_save, mock_deploy_ingestion, mock_create_app
    ):
        """deploy_l0() should deploy Ingestion when L1 ≠ L2."""
        from src.providers.azure.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",  # Different!
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_context.project_path = "/app/projects/test"
        mock_provider = MagicMock()
        mock_deploy_ingestion.return_value = "https://ingestion-url"
        
        deploy_l0(mock_context, mock_provider)
        
        mock_create_app.assert_called_once()
        mock_deploy_ingestion.assert_called_once()
    
    @patch("src.providers.azure.layers.l0_adapter.create_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.deploy_hot_writer_function")
    @patch("src.providers.azure.layers.l0_adapter.save_inter_cloud_connection")
    def test_deploy_l0_different_l2_l3_deploys_hot_writer(
        self, mock_save, mock_deploy_hw, mock_create_app
    ):
        """deploy_l0() should deploy Hot Writer when L2 ≠ L3."""
        from src.providers.azure.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws",  # Different from L3!
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_context.project_path = "/app/projects/test"
        mock_provider = MagicMock()
        mock_deploy_hw.return_value = "https://hw-url"
        
        deploy_l0(mock_context, mock_provider)
        
        mock_create_app.assert_called_once()
        mock_deploy_hw.assert_called_once()
    
    @patch("src.providers.azure.layers.l0_adapter.create_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.create_hot_reader_endpoint")
    @patch("src.providers.azure.layers.l0_adapter.create_hot_reader_last_entry_endpoint")
    @patch("src.providers.azure.layers.l0_adapter.save_inter_cloud_connection")
    def test_deploy_l0_different_l3_l4_deploys_hot_reader(
        self, mock_save, mock_last_entry, mock_hot_reader, mock_create_app
    ):
        """deploy_l0() should create Hot Reader endpoint when L3 ≠ L4."""
        from src.providers.azure.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "aws"  # Different!
        }
        mock_context.project_path = "/app/projects/test"
        mock_provider = MagicMock()
        mock_hot_reader.return_value = "https://hr-url"
        mock_last_entry.return_value = "https://hrle-url"
        
        deploy_l0(mock_context, mock_provider)
        
        mock_create_app.assert_called_once()
        mock_hot_reader.assert_called_once()
        mock_last_entry.assert_called_once()
    
    @patch("src.providers.azure.layers.l0_adapter.create_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.deploy_ingestion_function")
    @patch("src.providers.azure.layers.l0_adapter.save_inter_cloud_connection")
    def test_deploy_l0_saves_connection_details(
        self, mock_save, mock_deploy_ingestion, mock_create_app
    ):
        """deploy_l0() should save inter-cloud connection details."""
        from src.providers.azure.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",  # Different!
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_context.project_path = "/app/projects/test"
        mock_provider = MagicMock()
        mock_deploy_ingestion.return_value = "https://ingestion-url"
        
        deploy_l0(mock_context, mock_provider)
        
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args.args[0] == "/app/projects/test"
        assert call_args.args[1] == "azure"


# ==========================================
# Info L0 Adapter Tests
# ==========================================

class TestInfoL0AdapterFunction:
    """Edge case tests for info_l0 adapter function."""
    
    @patch("src.providers.azure.layers.l0_adapter.check_glue_function_app")
    def test_info_l0_no_boundaries_logs_no_components_needed(self, mock_check_app):
        """info_l0() should only check app when all same cloud."""
        from src.providers.azure.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_provider = MagicMock()
        mock_check_app.return_value = False
        
        result = info_l0(mock_context, mock_provider)
        
        assert "function_app" in result
        assert "app_service_plan" in result
        # Only base infrastructure checked, no boundary components
        assert len(result) == 2
    
    @patch("src.providers.azure.layers.l0_adapter.check_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.check_ingestion_function")
    def test_info_l0_l1_l2_boundary_checks_ingestion(
        self, mock_check_ingestion, mock_check_app
    ):
        """info_l0() should check Ingestion when L1 ≠ L2."""
        from src.providers.azure.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",  # Different!
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure"
        }
        mock_provider = MagicMock()
        mock_check_app.return_value = True
        mock_check_ingestion.return_value = True
        
        result = info_l0(mock_context, mock_provider)
        
        assert result["ingestion"] is True
        mock_check_ingestion.assert_called_once()
    
    @patch("src.providers.azure.layers.l0_adapter.check_glue_function_app")
    @patch("src.providers.azure.layers.l0_adapter.check_hot_reader_endpoint")
    @patch("src.providers.azure.layers.l0_adapter.check_hot_reader_last_entry_endpoint")
    def test_info_l0_l3_l4_boundary_checks_hot_reader(
        self, mock_check_last, mock_check_hr, mock_check_app
    ):
        """info_l0() should check Hot Reader when L3 ≠ L4."""
        from src.providers.azure.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "aws"  # Different!
        }
        mock_provider = MagicMock()
        mock_check_app.return_value = True
        mock_check_hr.return_value = True
        mock_check_last.return_value = True
        
        result = info_l0(mock_context, mock_provider)
        
        assert result["hot_reader"] is True
        assert result["hot_reader_last_entry"] is True
