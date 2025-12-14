"""
Unit tests for Azure L5 (Visualization) layer components.

Tests cover:
- Grafana Workspace create/destroy/check
- Hot Reader URL resolution (single-cloud and multi-cloud)
- JSON API Datasource configuration
- Pre-flight checks (L3 dependency)
- info_l5 status checks
"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch, PropertyMock
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError


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
    provider.naming.grafana_workspace.return_value = "test-twin-grafana"
    provider.naming.l3_function_app.return_value = "test-twin-l3-functions"
    provider.naming.hot_reader_function.return_value = "hot-reader"
    
    # Mock clients
    provider.clients = {
        "dashboard": MagicMock(),
        "web": MagicMock(),
    }
    
    return provider


@pytest.fixture
def mock_context():
    """Create a mock DeploymentContext."""
    context = MagicMock()
    context.config.digital_twin_name = "test-twin"
    context.config.providers = {
        "layer_3_hot_provider": "azure",
        "layer_5_provider": "azure"
    }
    context.project_path = "/app/projects/test-project"
    return context


@pytest.fixture
def mock_context_multicloud():
    """Create a mock DeploymentContext for multi-cloud scenario."""
    context = MagicMock()
    context.config.digital_twin_name = "test-twin"
    context.config.providers = {
        "layer_3_hot_provider": "aws",
        "layer_5_provider": "azure"
    }
    context.project_path = "/app/projects/test-project"
    return context


# ==========================================
# Grafana Workspace Tests
# ==========================================

class TestGrafanaWorkspace:
    """Tests for Grafana Workspace create/destroy/check."""
    
    def test_create_grafana_workspace_success(self, mock_azure_provider):
        """Happy path: Grafana workspace created successfully."""
        from src.providers.azure.layers.layer_5_grafana import create_grafana_workspace
        
        mock_poller = MagicMock()
        mock_workspace = MagicMock()
        mock_workspace.properties.endpoint = "https://test-twin-grafana.eastus.grafana.azure.com"
        mock_poller.result.return_value = mock_workspace
        mock_azure_provider.clients["dashboard"].grafana.begin_create.return_value = mock_poller
        
        with patch('time.sleep'):
            result = create_grafana_workspace(mock_azure_provider)
        
        assert result == "https://test-twin-grafana.eastus.grafana.azure.com"
        mock_azure_provider.clients["dashboard"].grafana.begin_create.assert_called_once()
    
    def test_create_grafana_workspace_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_5_grafana import create_grafana_workspace
        
        with pytest.raises(ValueError, match="provider is required"):
            create_grafana_workspace(None)
    
    def test_destroy_grafana_workspace_success(self, mock_azure_provider):
        """Happy path: Grafana workspace destroyed."""
        from src.providers.azure.layers.layer_5_grafana import destroy_grafana_workspace
        
        mock_poller = MagicMock()
        mock_azure_provider.clients["dashboard"].grafana.begin_delete.return_value = mock_poller
        
        destroy_grafana_workspace(mock_azure_provider)
        
        mock_azure_provider.clients["dashboard"].grafana.begin_delete.assert_called_once()
    
    def test_destroy_grafana_workspace_not_found(self, mock_azure_provider):
        """Destroy handles ResourceNotFoundError gracefully."""
        from src.providers.azure.layers.layer_5_grafana import destroy_grafana_workspace
        
        mock_azure_provider.clients["dashboard"].grafana.begin_delete.side_effect = ResourceNotFoundError("Not found")
        
        # Should not raise
        destroy_grafana_workspace(mock_azure_provider)
    
    def test_destroy_grafana_workspace_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_5_grafana import destroy_grafana_workspace
        
        with pytest.raises(ValueError, match="provider is required"):
            destroy_grafana_workspace(None)
    
    def test_check_grafana_workspace_exists(self, mock_azure_provider):
        """Check returns True when workspace exists."""
        from src.providers.azure.layers.layer_5_grafana import check_grafana_workspace
        
        mock_azure_provider.clients["dashboard"].grafana.get.return_value = MagicMock()
        
        result = check_grafana_workspace(mock_azure_provider)
        
        assert result is True
    
    def test_check_grafana_workspace_not_found(self, mock_azure_provider):
        """Check returns False when workspace doesn't exist."""
        from src.providers.azure.layers.layer_5_grafana import check_grafana_workspace
        
        mock_azure_provider.clients["dashboard"].grafana.get.side_effect = ResourceNotFoundError("Not found")
        
        result = check_grafana_workspace(mock_azure_provider)
        
        assert result is False
    
    def test_check_grafana_workspace_missing_provider_raises(self):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.layer_5_grafana import check_grafana_workspace
        
        with pytest.raises(ValueError, match="provider is required"):
            check_grafana_workspace(None)


class TestGetGrafanaWorkspaceUrl:
    """Tests for get_grafana_workspace_url."""
    
    def test_get_url_success(self, mock_azure_provider):
        """Returns URL when workspace exists."""
        from src.providers.azure.layers.layer_5_grafana import get_grafana_workspace_url
        
        mock_workspace = MagicMock()
        mock_workspace.properties.endpoint = "https://test.grafana.azure.com"
        mock_azure_provider.clients["dashboard"].grafana.get.return_value = mock_workspace
        
        result = get_grafana_workspace_url(mock_azure_provider)
        
        assert result == "https://test.grafana.azure.com"
    
    def test_get_url_not_found(self, mock_azure_provider):
        """Returns None when workspace doesn't exist."""
        from src.providers.azure.layers.layer_5_grafana import get_grafana_workspace_url
        
        mock_azure_provider.clients["dashboard"].grafana.get.side_effect = ResourceNotFoundError("Not found")
        
        result = get_grafana_workspace_url(mock_azure_provider)
        
        assert result is None


# ==========================================
# Hot Reader URL Tests
# ==========================================

class TestGetHotReaderUrl:
    """Tests for get_hot_reader_url (single and multi-cloud)."""
    
    def test_single_cloud_success(self, mock_context, mock_azure_provider):
        """Single-cloud: returns URL from L3 Function App."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        mock_app = MagicMock()
        mock_app.default_host_name = "test-twin-l3-functions.azurewebsites.net"
        mock_azure_provider.clients["web"].web_apps.get.return_value = mock_app
        
        result = get_hot_reader_url(mock_context, mock_azure_provider, "/app/project")
        
        assert result == "https://test-twin-l3-functions.azurewebsites.net/api/hot-reader"
    
    def test_single_cloud_l3_not_found(self, mock_context, mock_azure_provider):
        """Single-cloud: raises RuntimeError when L3 Function App not found."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        mock_azure_provider.clients["web"].web_apps.get.side_effect = ResourceNotFoundError("Not found")
        
        with pytest.raises(RuntimeError, match="L3 Function App not found"):
            get_hot_reader_url(mock_context, mock_azure_provider, "/app/project")
    
    def test_multi_cloud_success(self, mock_context_multicloud, mock_azure_provider, tmp_path):
        """Multi-cloud: returns URL from config_inter_cloud.json."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        # Create config_inter_cloud.json
        config = {
            "aws": {
                "l3_hot_reader_url": "https://aws-lambda-url.amazonaws.com/hot-reader"
            }
        }
        config_path = tmp_path / "config_inter_cloud.json"
        config_path.write_text(json.dumps(config))
        
        result = get_hot_reader_url(mock_context_multicloud, mock_azure_provider, str(tmp_path))
        
        assert result == "https://aws-lambda-url.amazonaws.com/hot-reader"
    
    def test_multi_cloud_config_not_found(self, mock_context_multicloud, mock_azure_provider, tmp_path):
        """Multi-cloud: raises RuntimeError when config file not found."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        with pytest.raises(RuntimeError, match="config_inter_cloud.json not found"):
            get_hot_reader_url(mock_context_multicloud, mock_azure_provider, str(tmp_path))
    
    def test_multi_cloud_url_not_in_config(self, mock_context_multicloud, mock_azure_provider, tmp_path):
        """Multi-cloud: raises RuntimeError when URL not in config."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        # Create config without hot reader URL
        config = {"aws": {"other_key": "value"}}
        config_path = tmp_path / "config_inter_cloud.json"
        config_path.write_text(json.dumps(config))
        
        with pytest.raises(RuntimeError, match="Hot Reader URL not found"):
            get_hot_reader_url(mock_context_multicloud, mock_azure_provider, str(tmp_path))


# ==========================================
# Pre-Flight Check Tests
# ==========================================

class TestPreFlightChecks:
    """Tests for L5 pre-flight checks."""
    
    @patch('src.providers.azure.layers.layer_3_storage.check_cosmos_account')
    @patch('src.providers.azure.layers.layer_3_storage.check_hot_cosmos_container')
    @patch('src.providers.azure.layers.layer_3_storage.check_l3_function_app')
    @patch('src.providers.azure.layers.layer_3_storage.check_hot_reader_function')
    def test_single_cloud_all_present(
        self, mock_hot_reader, mock_func_app, mock_container, mock_cosmos,
        mock_context, mock_azure_provider
    ):
        """Single-cloud: passes when all L3 components exist."""
        from src.providers.azure.layers.l5_adapter import _check_l3_single_cloud
        
        mock_cosmos.return_value = True
        mock_container.return_value = True
        mock_func_app.return_value = True
        mock_hot_reader.return_value = True
        
        # Should not raise
        _check_l3_single_cloud(mock_azure_provider)
    
    @patch('src.providers.azure.layers.layer_3_storage.check_cosmos_account')
    @patch('src.providers.azure.layers.layer_3_storage.check_hot_cosmos_container')
    @patch('src.providers.azure.layers.layer_3_storage.check_l3_function_app')
    @patch('src.providers.azure.layers.layer_3_storage.check_hot_reader_function')
    def test_single_cloud_missing_cosmos(
        self, mock_hot_reader, mock_func_app, mock_container, mock_cosmos,
        mock_context, mock_azure_provider
    ):
        """Single-cloud: fails when Cosmos DB missing."""
        from src.providers.azure.layers.l5_adapter import _check_l3_single_cloud
        
        mock_cosmos.return_value = False
        mock_container.return_value = False
        mock_func_app.return_value = True
        mock_hot_reader.return_value = True
        
        with pytest.raises(RuntimeError, match="Cosmos DB Account"):
            _check_l3_single_cloud(mock_azure_provider)
    
    @patch('src.providers.azure.layers.layer_3_storage.check_cosmos_account')
    @patch('src.providers.azure.layers.layer_3_storage.check_hot_cosmos_container')
    @patch('src.providers.azure.layers.layer_3_storage.check_l3_function_app')
    @patch('src.providers.azure.layers.layer_3_storage.check_hot_reader_function')
    def test_single_cloud_missing_hot_reader(
        self, mock_hot_reader, mock_func_app, mock_container, mock_cosmos,
        mock_context, mock_azure_provider
    ):
        """Single-cloud: fails when Hot Reader function missing."""
        from src.providers.azure.layers.l5_adapter import _check_l3_single_cloud
        
        mock_cosmos.return_value = True
        mock_container.return_value = True
        mock_func_app.return_value = True
        mock_hot_reader.return_value = False
        
        with pytest.raises(RuntimeError, match="Hot Reader Function"):
            _check_l3_single_cloud(mock_azure_provider)
    
    def test_multi_cloud_success(self, tmp_path):
        """Multi-cloud: passes when Hot Reader URL exists in config."""
        from src.providers.azure.layers.l5_adapter import _check_l3_multi_cloud
        
        config = {"aws": {"l3_hot_reader_url": "https://url.com"}}
        config_path = tmp_path / "config_inter_cloud.json"
        config_path.write_text(json.dumps(config))
        
        # Should not raise
        _check_l3_multi_cloud(str(tmp_path))
    
    def test_multi_cloud_config_missing(self, tmp_path):
        """Multi-cloud: fails when config file not found."""
        from src.providers.azure.layers.l5_adapter import _check_l3_multi_cloud
        
        with pytest.raises(RuntimeError, match="config_inter_cloud.json not found"):
            _check_l3_multi_cloud(str(tmp_path))
    
    def test_multi_cloud_url_missing(self, tmp_path):
        """Multi-cloud: fails when URL not in config."""
        from src.providers.azure.layers.l5_adapter import _check_l3_multi_cloud
        
        config = {"aws": {"other": "value"}}
        config_path = tmp_path / "config_inter_cloud.json"
        config_path.write_text(json.dumps(config))
        
        with pytest.raises(RuntimeError, match="Hot Reader URL not found"):
            _check_l3_multi_cloud(str(tmp_path))


class TestProviderConfigValidation:
    """Tests for fail-fast validation of provider config."""
    
    def test_check_l3_deployed_missing_l3_provider_raises(self, mock_azure_provider):
        """Fails when layer_3_hot_provider is not set."""
        from src.providers.azure.layers.l5_adapter import _check_l3_deployed
        
        context = MagicMock()
        context.config.providers = {"layer_5_provider": "azure"}
        context.project_path = "/app/project"
        
        with pytest.raises(ValueError, match="layer_3_hot_provider.*is not set"):
            _check_l3_deployed(context, mock_azure_provider)
    
    def test_check_l3_deployed_missing_l5_provider_raises(self, mock_azure_provider):
        """Fails when layer_5_provider is not set."""
        from src.providers.azure.layers.l5_adapter import _check_l3_deployed
        
        context = MagicMock()
        context.config.providers = {"layer_3_hot_provider": "azure"}
        context.project_path = "/app/project"
        
        with pytest.raises(ValueError, match="layer_5_provider.*is not set"):
            _check_l3_deployed(context, mock_azure_provider)
    
    def test_get_hot_reader_url_missing_l3_provider_raises(self, mock_azure_provider, tmp_path):
        """Fails when layer_3_hot_provider is not set in get_hot_reader_url."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        context = MagicMock()
        context.config.providers = {"layer_5_provider": "azure"}
        
        with pytest.raises(ValueError, match="layer_3_hot_provider.*is not set"):
            get_hot_reader_url(context, mock_azure_provider, str(tmp_path))
    
    def test_get_hot_reader_url_missing_l5_provider_raises(self, mock_azure_provider, tmp_path):
        """Fails when layer_5_provider is not set in get_hot_reader_url."""
        from src.providers.azure.layers.layer_5_grafana import get_hot_reader_url
        
        context = MagicMock()
        context.config.providers = {"layer_3_hot_provider": "azure"}
        
        with pytest.raises(ValueError, match="layer_5_provider.*is not set"):
            get_hot_reader_url(context, mock_azure_provider, str(tmp_path))


# ==========================================
# L5 Adapter Tests
# ==========================================

class TestL5Adapter:
    """Tests for L5 adapter orchestration functions."""
    
    def test_deploy_l5_missing_context_raises(self, mock_azure_provider):
        """Validation: None context raises ValueError."""
        from src.providers.azure.layers.l5_adapter import deploy_l5
        
        with pytest.raises(ValueError, match="context is required"):
            deploy_l5(None, mock_azure_provider)
    
    def test_deploy_l5_missing_provider_raises(self, mock_context):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.l5_adapter import deploy_l5
        
        with pytest.raises(ValueError, match="provider is required"):
            deploy_l5(mock_context, None)
    
    def test_destroy_l5_missing_context_raises(self, mock_azure_provider):
        """Validation: None context raises ValueError."""
        from src.providers.azure.layers.l5_adapter import destroy_l5
        
        with pytest.raises(ValueError, match="context is required"):
            destroy_l5(None, mock_azure_provider)
    
    def test_destroy_l5_missing_provider_raises(self, mock_context):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.l5_adapter import destroy_l5
        
        with pytest.raises(ValueError, match="provider is required"):
            destroy_l5(mock_context, None)
    
    def test_info_l5_missing_context_raises(self, mock_azure_provider):
        """Validation: None context raises ValueError."""
        from src.providers.azure.layers.l5_adapter import info_l5
        
        with pytest.raises(ValueError, match="context is required"):
            info_l5(None, mock_azure_provider)
    
    def test_info_l5_missing_provider_raises(self, mock_context):
        """Validation: None provider raises ValueError."""
        from src.providers.azure.layers.l5_adapter import info_l5
        
        with pytest.raises(ValueError, match="provider is required"):
            info_l5(mock_context, None)


# ==========================================
# Info L5 Tests
# ==========================================

class TestInfoL5:
    """Tests for info_l5 status checks."""
    
    def test_info_l5_workspace_exists(self, mock_context, mock_azure_provider):
        """Returns workspace status when it exists."""
        from src.providers.azure.layers.layer_5_grafana import info_l5
        
        mock_workspace = MagicMock()
        mock_workspace.properties.endpoint = "https://test.grafana.azure.com"
        mock_azure_provider.clients["dashboard"].grafana.get.return_value = mock_workspace
        
        result = info_l5(mock_context, mock_azure_provider)
        
        assert result["grafana_workspace"]["exists"] is True
        assert result["grafana_workspace"]["url"] == "https://test.grafana.azure.com"
    
    def test_info_l5_workspace_not_exists(self, mock_context, mock_azure_provider):
        """Returns workspace status when it doesn't exist."""
        from src.providers.azure.layers.layer_5_grafana import info_l5
        
        mock_azure_provider.clients["dashboard"].grafana.get.side_effect = ResourceNotFoundError("Not found")
        
        result = info_l5(mock_context, mock_azure_provider)
        
        assert result["grafana_workspace"]["exists"] is False
        assert result["grafana_workspace"]["url"] is None
