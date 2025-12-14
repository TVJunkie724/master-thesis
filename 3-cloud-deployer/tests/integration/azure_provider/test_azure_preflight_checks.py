"""
Pre-Flight Check Tests for Azure Layer Adapters.

Tests cover the fail-fast pre-flight checks that verify previous layer
is deployed before starting deployment of the next layer.

Test Categories:
1. Setup check passes when all components exist
2. Setup check raises when components missing
3. L0 check for L1 (multi-cloud only)
4. L1 check for L2
5. L2 check for L3
6. L3 check for L4
"""

import pytest
from unittest.mock import MagicMock, patch


class TestL0PreFlightCheck:
    """Tests for L0 adapter pre-flight check (_check_setup_deployed)."""
    
    def test_l0_preflight_passes_when_setup_complete(self):
        """L0 pre-flight should pass when all Setup components exist."""
        from src.providers.azure.layers.l0_adapter import _check_setup_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_info:
            mock_info.return_value = {
                "resource_group": True,
                "managed_identity": True,
                "storage_account": True
            }
            # Should not raise
            _check_setup_deployed(mock_context, mock_provider)
    
    def test_l0_preflight_fails_when_rg_missing(self):
        """L0 pre-flight should fail when Resource Group is missing."""
        from src.providers.azure.layers.l0_adapter import _check_setup_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_info:
            mock_info.return_value = {
                "resource_group": False,
                "managed_identity": True,
                "storage_account": True
            }
            with pytest.raises(RuntimeError, match="Resource Group"):
                _check_setup_deployed(mock_context, mock_provider)
    
    def test_l0_preflight_fails_when_identity_missing(self):
        """L0 pre-flight should fail when Managed Identity is missing."""
        from src.providers.azure.layers.l0_adapter import _check_setup_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_info:
            mock_info.return_value = {
                "resource_group": True,
                "managed_identity": False,
                "storage_account": True
            }
            with pytest.raises(RuntimeError, match="Managed Identity"):
                _check_setup_deployed(mock_context, mock_provider)


class TestL1PreFlightCheck:
    """Tests for L1 adapter pre-flight checks."""
    
    def test_l1_setup_preflight_passes_when_complete(self):
        """L1 pre-flight should pass when Setup is fully deployed."""
        from src.providers.azure.layers.l1_adapter import _check_setup_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_info:
            mock_info.return_value = {
                "resource_group": True,
                "managed_identity": True,
                "storage_account": True
            }
            # Should not raise
            _check_setup_deployed(mock_context, mock_provider)
    
    def test_l1_setup_preflight_fails_when_storage_missing(self):
        """L1 pre-flight should fail when Storage Account is missing."""
        from src.providers.azure.layers.l1_adapter import _check_setup_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l_setup_adapter.info_setup") as mock_info:
            mock_info.return_value = {
                "resource_group": True,
                "managed_identity": True,
                "storage_account": False
            }
            with pytest.raises(RuntimeError, match="Storage Account"):
                _check_setup_deployed(mock_context, mock_provider)
    
    def test_l1_l0_preflight_passes_in_single_cloud(self):
        """L1 L0 check should pass when L1 == L2 (no L0 dependency)."""
        from src.providers.azure.layers.l1_adapter import _check_l0_deployed
        
        mock_context = MagicMock()
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure"  # Same as L1
        }
        mock_provider = MagicMock()
        
        # Should not raise
        _check_l0_deployed(mock_context, mock_provider)
    
    def test_l1_l0_preflight_passes_when_azure_is_l1(self):
        """L1 L0 check should pass when Azure is L1 (not L2 receiver)."""
        from src.providers.azure.layers.l1_adapter import _check_l0_deployed
        
        mock_context = MagicMock()
        mock_context.config.providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws"  # Azure sends, doesn't receive
        }
        mock_provider = MagicMock()
        
        # Should not raise
        _check_l0_deployed(mock_context, mock_provider)
    
    def test_l1_l0_preflight_fails_when_l0_missing_multicloud(self):
        """L1 L0 check should fail when Azure is L2 and L0 not deployed."""
        from src.providers.azure.layers.l1_adapter import _check_l0_deployed
        
        mock_context = MagicMock()
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure"  # Azure is L2 receiver
        }
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l0_adapter.info_l0") as mock_info:
            mock_info.return_value = {"function_app": False}
            with pytest.raises(RuntimeError, match="L0 Glue Layer not deployed"):
                _check_l0_deployed(mock_context, mock_provider)


class TestL2PreFlightCheck:
    """Tests for L2 adapter pre-flight check (_check_l1_deployed)."""
    
    def test_l2_preflight_passes_when_l1_complete(self):
        """L2 pre-flight should pass when IoT Hub and Function App exist."""
        from src.providers.azure.layers.l2_adapter import _check_l1_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l1_adapter.info_l1") as mock_info:
            mock_info.return_value = {
                "iot_hub": True,
                "function_app": True
            }
            # Should not raise
            _check_l1_deployed(mock_context, mock_provider)
    
    def test_l2_preflight_fails_when_iot_hub_missing(self):
        """L2 pre-flight should fail when IoT Hub is missing."""
        from src.providers.azure.layers.l2_adapter import _check_l1_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l1_adapter.info_l1") as mock_info:
            mock_info.return_value = {
                "iot_hub": False,
                "function_app": True
            }
            with pytest.raises(RuntimeError, match="IoT Hub"):
                _check_l1_deployed(mock_context, mock_provider)
    
    def test_l2_preflight_fails_when_function_app_missing(self):
        """L2 pre-flight should fail when Function App is missing."""
        from src.providers.azure.layers.l2_adapter import _check_l1_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l1_adapter.info_l1") as mock_info:
            mock_info.return_value = {
                "iot_hub": True,
                "function_app": False
            }
            with pytest.raises(RuntimeError, match="Function App"):
                _check_l1_deployed(mock_context, mock_provider)


class TestL3PreFlightCheck:
    """Tests for L3 adapter pre-flight check (_check_l2_deployed)."""
    
    def test_l3_preflight_passes_when_l2_deployed(self):
        """L3 pre-flight should pass when L2 Function App exists."""
        from src.providers.azure.layers.l3_adapter import _check_l2_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        # Mock L2 Function App get to succeed
        mock_provider.naming.resource_group.return_value = "rg-test"
        mock_provider.naming.l2_function_app.return_value = "test-l2-functions"
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].web_apps.get.return_value = MagicMock()
        
        # Should not raise
        _check_l2_deployed(mock_context, mock_provider)
    
    def test_l3_preflight_fails_when_l2_missing(self):
        """L3 pre-flight should fail when L2 Function App is missing."""
        from src.providers.azure.layers.l3_adapter import _check_l2_deployed
        from azure.core.exceptions import ResourceNotFoundError
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        mock_provider.naming.resource_group.return_value = "rg-test"
        mock_provider.naming.l2_function_app.return_value = "test-l2-functions"
        mock_provider.clients = {"web": MagicMock()}
        mock_provider.clients["web"].web_apps.get.side_effect = ResourceNotFoundError("Not found")
        
        with pytest.raises(RuntimeError, match="L2 Function App not deployed"):
            _check_l2_deployed(mock_context, mock_provider)


class TestL4PreFlightCheck:
    """Tests for L4 adapter pre-flight check (_check_l3_deployed)."""
    
    def test_l4_preflight_passes_when_l3_hot_deployed(self):
        """L4 pre-flight should pass when Cosmos and Hot Container exist."""
        from src.providers.azure.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l3_adapter.info_l3") as mock_info:
            mock_info.return_value = {
                "hot_storage": {
                    "cosmos_account": {"exists": True},
                    "hot_container": {"exists": True}
                }
            }
            # Should not raise
            _check_l3_deployed(mock_context, mock_provider)
    
    def test_l4_preflight_fails_when_cosmos_missing(self):
        """L4 pre-flight should fail when Cosmos DB Account is missing."""
        from src.providers.azure.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l3_adapter.info_l3") as mock_info:
            mock_info.return_value = {
                "hot_storage": {
                    "cosmos_account": {"exists": False},
                    "hot_container": {"exists": True}
                }
            }
            with pytest.raises(RuntimeError, match="Cosmos DB Account"):
                _check_l3_deployed(mock_context, mock_provider)
    
    def test_l4_preflight_fails_when_container_missing(self):
        """L4 pre-flight should fail when Hot Container is missing."""
        from src.providers.azure.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l3_adapter.info_l3") as mock_info:
            mock_info.return_value = {
                "hot_storage": {
                    "cosmos_account": {"exists": True},
                    "hot_container": {"exists": False}
                }
            }
            with pytest.raises(RuntimeError, match="Hot Container"):
                _check_l3_deployed(mock_context, mock_provider)
    
    def test_l4_preflight_reports_all_missing(self):
        """L4 pre-flight should report all missing components."""
        from src.providers.azure.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.azure.layers.l3_adapter.info_l3") as mock_info:
            mock_info.return_value = {
                "hot_storage": {
                    "cosmos_account": {"exists": False},
                    "hot_container": {"exists": False}
                }
            }
            with pytest.raises(RuntimeError) as exc_info:
                _check_l3_deployed(mock_context, mock_provider)
            
            assert "Cosmos DB Account" in str(exc_info.value)
            assert "Hot Container" in str(exc_info.value)
