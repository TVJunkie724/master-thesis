"""
Pre-Flight Check Tests for AWS Layer Adapters.

Tests cover the fail-fast pre-flight checks that verify previous layer
is deployed before starting deployment of the next layer.

Test Categories:
1. Single-cloud mode: Pre-flight check should pass (no dependency)
2. Multi-cloud mode: Pre-flight check should raise ValueError when dependency missing
3. Multi-cloud mode: Pre-flight check should pass when dependency exists
"""

import pytest
from unittest.mock import MagicMock, patch


class TestL1PreFlightCheck:
    """Tests for L1 adapter pre-flight check (_check_l0_deployed)."""
    
    def test_l1_preflight_passes_in_single_cloud_mode(self):
        """L1 pre-flight should pass when L1 == L2 (no L0 dependency needed)."""
        from src.providers.aws.layers.l1_adapter import _check_l0_deployed
        
        mock_context = MagicMock()
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws"  # Same as L1
        }
        
        mock_provider = MagicMock()
        
        # Should not raise - single cloud mode doesn't need L0
        _check_l0_deployed(mock_context, mock_provider)
    
    def test_l1_preflight_fails_when_ingestion_missing_in_multicloud(self):
        """L1 pre-flight should fail when L1 != L2 and Ingestion is missing."""
        from src.providers.aws.layers.l1_adapter import _check_l0_deployed
        
        mock_context = MagicMock()
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure"  # Different!
        }
        
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_0_glue.check_ingestion_lambda_function", return_value=False):
            with pytest.raises(ValueError, match="Pre-flight check FAILED"):
                _check_l0_deployed(mock_context, mock_provider)
    
    def test_l1_preflight_passes_when_ingestion_exists_in_multicloud(self):
        """L1 pre-flight should pass when L1 != L2 and Ingestion exists."""
        from src.providers.aws.layers.l1_adapter import _check_l0_deployed
        
        mock_context = MagicMock()
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure"  # Different!
        }
        
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_0_glue.check_ingestion_lambda_function", return_value=True):
            # Should not raise - Ingestion exists
            _check_l0_deployed(mock_context, mock_provider)


class TestL2PreFlightCheck:
    """Tests for L2 adapter pre-flight check (_check_l1_deployed)."""
    
    def test_l2_preflight_passes_when_l1_exists(self):
        """L2 pre-flight should pass when Dispatcher Lambda and IoT Rule exist."""
        from src.providers.aws.layers.l2_adapter import _check_l1_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_1_iot.check_dispatcher_lambda_function", return_value=True):
            with patch("src.providers.aws.layers.layer_1_iot.check_dispatcher_iot_rule", return_value=True):
                # Should not raise
                _check_l1_deployed(mock_context, mock_provider)
    
    def test_l2_preflight_fails_when_dispatcher_missing(self):
        """L2 pre-flight should fail when Dispatcher Lambda is missing."""
        from src.providers.aws.layers.l2_adapter import _check_l1_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_1_iot.check_dispatcher_lambda_function", return_value=False):
            with patch("src.providers.aws.layers.layer_1_iot.check_dispatcher_iot_rule", return_value=True):
                with pytest.raises(ValueError, match="Dispatcher Lambda"):
                    _check_l1_deployed(mock_context, mock_provider)
    
    def test_l2_preflight_fails_when_iot_rule_missing(self):
        """L2 pre-flight should fail when IoT Topic Rule is missing."""
        from src.providers.aws.layers.l2_adapter import _check_l1_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_1_iot.check_dispatcher_lambda_function", return_value=True):
            with patch("src.providers.aws.layers.layer_1_iot.check_dispatcher_iot_rule", return_value=False):
                with pytest.raises(ValueError, match="IoT Topic Rule"):
                    _check_l1_deployed(mock_context, mock_provider)


class TestL3PreFlightCheck:
    """Tests for L3 adapter pre-flight check (_check_l2_deployed)."""
    
    def test_l3_preflight_passes_when_persister_exists(self):
        """L3 pre-flight should pass when Persister Lambda exists."""
        from src.providers.aws.layers.l3_adapter import _check_l2_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_2_compute.check_persister_lambda_function", return_value=True):
            # Should not raise
            _check_l2_deployed(mock_context, mock_provider)
    
    def test_l3_preflight_fails_when_persister_missing(self):
        """L3 pre-flight should fail when Persister Lambda is missing."""
        from src.providers.aws.layers.l3_adapter import _check_l2_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_2_compute.check_persister_lambda_function", return_value=False):
            with pytest.raises(ValueError, match="L2 Persister is NOT deployed"):
                _check_l2_deployed(mock_context, mock_provider)


class TestL4PreFlightCheck:
    """Tests for L4 adapter pre-flight check (_check_l3_deployed)."""
    
    def test_l4_preflight_passes_when_hot_storage_exists(self):
        """L4 pre-flight should pass when DynamoDB table and Hot Reader exist."""
        from src.providers.aws.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_3_storage.check_hot_dynamodb_table", return_value=True):
            with patch("src.providers.aws.layers.layer_3_storage.check_hot_reader_lambda_function", return_value=True):
                # Should not raise
                _check_l3_deployed(mock_context, mock_provider)
    
    def test_l4_preflight_fails_when_dynamodb_missing(self):
        """L4 pre-flight should fail when DynamoDB Hot Table is missing."""
        from src.providers.aws.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_3_storage.check_hot_dynamodb_table", return_value=False):
            with patch("src.providers.aws.layers.layer_3_storage.check_hot_reader_lambda_function", return_value=True):
                with pytest.raises(ValueError, match="DynamoDB Hot Table"):
                    _check_l3_deployed(mock_context, mock_provider)
    
    def test_l4_preflight_fails_when_hot_reader_missing(self):
        """L4 pre-flight should fail when Hot Reader Lambda is missing."""
        from src.providers.aws.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_3_storage.check_hot_dynamodb_table", return_value=True):
            with patch("src.providers.aws.layers.layer_3_storage.check_hot_reader_lambda_function", return_value=False):
                with pytest.raises(ValueError, match="Hot Reader Lambda"):
                    _check_l3_deployed(mock_context, mock_provider)
    
    def test_l4_preflight_reports_both_missing_components(self):
        """L4 pre-flight should report all missing components."""
        from src.providers.aws.layers.l4_adapter import _check_l3_deployed
        
        mock_context = MagicMock()
        mock_provider = MagicMock()
        
        with patch("src.providers.aws.layers.layer_3_storage.check_hot_dynamodb_table", return_value=False):
            with patch("src.providers.aws.layers.layer_3_storage.check_hot_reader_lambda_function", return_value=False):
                with pytest.raises(ValueError) as exc_info:
                    _check_l3_deployed(mock_context, mock_provider)
                
                # Should list both missing components
                assert "DynamoDB Hot Table" in str(exc_info.value)
                assert "Hot Reader Lambda" in str(exc_info.value)

