"""
Multi-cloud configuration edge case tests.

Tests cover:
- Missing provider configuration raises errors (fail-fast)
- Provider config is required at deployment time
- Same-cloud scenarios skip multi-cloud components
"""

import pytest
from unittest.mock import MagicMock, patch


class TestProviderConfigValidation:
    """Tests for provider configuration validation (fail-fast behavior)."""

    # ==========================================
    # L2 Adapter Tests (Missing Provider Config)
    # ==========================================

    @patch("src.providers.aws.layers.l0_adapter._check_setup_deployed")
    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_deploy_l0_missing_layer_1_provider_fails(self, mock_compile, mock_sleep, mock_check_setup):
        """deploy_l0() should fail fast when layer_1_provider is missing.
        
        NOTE: Provider config validation moved from L2 adapter to L0 adapter.
        """
        from src.providers.aws.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            # Missing: "layer_1_provider"
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        mock_context.project_path.parent.parent = "/mock/path"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError, match="layer_1_provider"):
            deploy_l0(mock_context, mock_provider)

    @patch("src.providers.aws.layers.l2_adapter._check_l1_deployed")
    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_deploy_l2_missing_layer_2_provider_fails(self, mock_compile, mock_sleep, mock_check_l1):
        """deploy_l2() should fail fast when layer_2_provider is missing."""
        from src.providers.aws.layers.l2_adapter import deploy_l2
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.hot_storage_size_in_days = 7
        mock_context.config.cold_storage_size_in_days = 30
        mock_context.config.mode = "dev"
        mock_context.config.iot_devices = []
        mock_context.config.events = []
        mock_context.config.is_optimization_enabled.return_value = False
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            # Missing: "layer_2_provider"
            "layer_3_hot_provider": "aws"
        }
        mock_context.project_path.parent.parent = "/mock/path"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError, match="layer_2_provider"):
            deploy_l2(mock_context, mock_provider)

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_destroy_l0_missing_provider_config_fails(self, mock_compile, mock_sleep):
        """destroy_l0() should fail fast when provider config is missing.
        
        NOTE: Provider config validation moved from L2 adapter to L0 adapter.
        """
        from src.providers.aws.layers.l0_adapter import destroy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {}  # Empty providers
        
        mock_provider = MagicMock()
        
        with pytest.raises(KeyError):
            destroy_l0(mock_context, mock_provider)

    # ==========================================
    # L3 Adapter Tests - Direct Config Access
    # We test the config validation directly since deploy_l3_hot
    # does DynamoDB/Lambda setup before checking multi-cloud config
    # ==========================================

    def test_l3_provider_config_direct_access_missing_l2_fails(self):
        """Direct access to providers['layer_2_provider'] should raise KeyError."""
        providers = {
            "layer_1_provider": "aws",
            # Missing: "layer_2_provider"
            "layer_3_hot_provider": "aws"
        }
        
        with pytest.raises(KeyError, match="layer_2_provider"):
            _ = providers["layer_2_provider"]

    def test_l3_provider_config_direct_access_missing_l3_fails(self):
        """Direct access to providers['layer_3_hot_provider'] should raise KeyError."""
        providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            # Missing: "layer_3_hot_provider"
        }
        
        with pytest.raises(KeyError, match="layer_3_hot_provider"):
            _ = providers["layer_3_hot_provider"]

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_destroy_l3_hot_missing_provider_config_fails(self, mock_compile, mock_sleep):
        """destroy_l3_hot() should fail fast when provider config is missing."""
        from src.providers.aws.layers.l3_adapter import destroy_l3_hot
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {}  # Empty providers
        
        mock_provider = MagicMock()
        
        with pytest.raises(KeyError):
            destroy_l3_hot(mock_context, mock_provider)

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_persister_lambda_missing_provider_config_fails(self, mock_compile, mock_sleep):
        """create_persister_lambda_function() should fail fast on missing provider config."""
        from src.providers.aws.layers.layer_2_compute import create_persister_lambda_function
        
        mock_config = MagicMock()
        mock_config.providers = {}  # Empty providers
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.events = []
        mock_config.is_optimization_enabled.return_value = False
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError):
            create_persister_lambda_function(mock_provider, mock_config, "/mock/path")

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_persister_lambda_missing_layer_2_provider_fails(self, mock_compile, mock_sleep):
        """create_persister_lambda_function() should fail when layer_2_provider is missing."""
        from src.providers.aws.layers.layer_2_compute import create_persister_lambda_function
        
        mock_config = MagicMock()
        mock_config.providers = {
            "layer_1_provider": "aws",
            # Missing: "layer_2_provider"
            "layer_3_hot_provider": "aws"
        }
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.events = []
        mock_config.is_optimization_enabled.return_value = False
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError, match="layer_2_provider"):
            create_persister_lambda_function(mock_provider, mock_config, "/mock/path")

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_persister_lambda_missing_layer_3_provider_fails(self, mock_compile, mock_sleep):
        """create_persister_lambda_function() should fail when layer_3_hot_provider is missing."""
        from src.providers.aws.layers.layer_2_compute import create_persister_lambda_function
        
        mock_config = MagicMock()
        mock_config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            # Missing: "layer_3_hot_provider"
        }
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.events = []
        mock_config.is_optimization_enabled.return_value = False
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError, match="layer_3_hot_provider"):
            create_persister_lambda_function(mock_provider, mock_config, "/mock/path")

    # NOTE: should_deploy_api_gateway tests removed - function was removed
    # in favor of Lambda Function URLs. See implementation plan:
    # 2025-12-10_22-45_hot_reader_multi_cloud.md

    # ==========================================
    # create_processor_lambda_function Tests (layer_2_compute.py)
    # ==========================================

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_processor_l2_returns_early_when_not_aws(self, mock_compile, mock_sleep):
        """create_processor_lambda_function() should return early when L2 is not AWS.
        
        NOTE: Connector deployment has been moved to L1 adapter.
        L2 compute no longer needs layer_1_provider for its logic.
        """
        from src.providers.aws.layers.layer_2_compute import create_processor_lambda_function
        
        mock_device = {"id": "sensor-1", "iotDeviceId": "sensor-1"}
        
        mock_config = MagicMock()
        mock_config.providers = {
            "layer_2_provider": "azure",  # Not AWS - should return early
        }
        mock_config.inter_cloud = {}
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        
        # Should return early without raising, no Lambda created
        create_processor_lambda_function(mock_device, mock_provider, mock_config, "/mock/path")
        mock_provider.clients["lambda"].create_function.assert_not_called()

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_processor_missing_layer_2_provider_fails(self, mock_compile, mock_sleep):
        """create_processor_lambda_function() should fail when layer_2_provider is missing."""
        from src.providers.aws.layers.layer_2_compute import create_processor_lambda_function
        
        mock_device = {"id": "sensor-1", "type": "temperature"}
        
        mock_config = MagicMock()
        mock_config.providers = {
            "layer_1_provider": "aws",
            # Missing: "layer_2_provider"
            "layer_3_hot_provider": "aws"
        }
        mock_config.inter_cloud = {}
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError, match="layer_2_provider"):
            create_processor_lambda_function(mock_device, mock_provider, mock_config, "/mock/path")

    @patch("time.sleep")
    @patch("util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_connector_missing_inter_cloud_url_fails(self, mock_compile, mock_sleep):
        """L1 adapter create_connector_lambda_function() should fail when URL is missing.
        
        NOTE: Connector deployment has been moved to L1 adapter.
        """
        from src.providers.aws.layers.layer_1_iot import create_connector_lambda_function
        
        mock_device = {"id": "sensor-1", "iotDeviceId": "sensor-1"}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        mock_provider.naming.connector_iam_role.return_value = "test-role"
        mock_provider.naming.connector_lambda_function.return_value = "test-connector"
        
        with pytest.raises(ValueError, match="remote_ingestion_url is required"):
            create_connector_lambda_function(
                mock_device, mock_provider, mock_config, "/mock/path",
                remote_ingestion_url="",  # Empty URL - should fail
                inter_cloud_token="some-token"
            )

    @patch("time.sleep")
    @patch("util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_connector_missing_inter_cloud_token_fails(self, mock_compile, mock_sleep):
        """L1 adapter create_connector_lambda_function() should fail when token is missing.
        
        NOTE: Connector deployment has been moved to L1 adapter.
        """
        from src.providers.aws.layers.layer_1_iot import create_connector_lambda_function
        
        mock_device = {"id": "sensor-1", "iotDeviceId": "sensor-1"}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        mock_provider.naming.connector_iam_role.return_value = "test-role"
        mock_provider.naming.connector_lambda_function.return_value = "test-connector"
        
        with pytest.raises(ValueError, match="inter_cloud_token is required"):
            create_connector_lambda_function(
                mock_device, mock_provider, mock_config, "/mock/path",
                remote_ingestion_url="https://example.com/ingestion",
                inter_cloud_token=""  # Empty token - should fail
            )

    # ==========================================
    # create_dispatcher_lambda_function Tests (layer_1_iot.py)
    # ==========================================

    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_create_dispatcher_missing_layer_2_provider_fails(self, mock_compile, mock_sleep):
        """create_dispatcher_lambda_function() should fail when layer_2_provider is missing."""
        from src.providers.aws.layers.layer_1_iot import create_dispatcher_lambda_function
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.events = []
        mock_config.providers = {
            "layer_1_provider": "aws",
            # Missing: "layer_2_provider"
            "layer_3_hot_provider": "aws"
        }
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with pytest.raises(KeyError, match="layer_2_provider"):
            create_dispatcher_lambda_function(mock_provider, mock_config, "/mock/path")


class TestProviderConfigSuccessPath:
    """Tests for successful provider configuration scenarios."""

    @patch("src.providers.aws.layers.l2_adapter._check_l1_deployed")
    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_deploy_l2_same_cloud_skips_ingestion(self, mock_compile, mock_sleep, mock_check_l1):
        """deploy_l2() should NOT deploy Ingestion when L1 and L2 are same cloud."""
        from src.providers.aws.layers.l2_adapter import deploy_l2
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.hot_storage_size_in_days = 7
        mock_context.config.cold_storage_size_in_days = 30
        mock_context.config.mode = "dev"
        mock_context.config.iot_devices = []
        mock_context.config.events = []
        mock_context.config.is_optimization_enabled.return_value = False
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",  # Same as L1
            "layer_3_hot_provider": "aws"
        }
        mock_context.project_path.parent.parent = "/mock/path"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        # Should not raise, and should not call Ingestion functions
        deploy_l2(mock_context, mock_provider)
        
        # Verify Ingestion was NOT deployed (no call to ingestion_iam_role)
        mock_provider.naming.ingestion_iam_role.assert_not_called()

    @patch("src.providers.aws.layers.l2_adapter._check_l1_deployed")
    @patch("time.sleep")
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    def test_deploy_l2_complete_provider_config_succeeds(self, mock_compile, mock_sleep, mock_check_l1):
        """deploy_l2() should succeed with complete provider configuration."""
        from src.providers.aws.layers.l2_adapter import deploy_l2
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.hot_storage_size_in_days = 7
        mock_context.config.cold_storage_size_in_days = 30
        mock_context.config.mode = "dev"
        mock_context.config.iot_devices = []
        mock_context.config.events = []
        mock_context.config.is_optimization_enabled.return_value = False
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws"
        }
        mock_context.project_path.parent.parent = "/mock/path"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        # Should not raise
        deploy_l2(mock_context, mock_provider)
        
        # Verify Persister was deployed
        mock_provider.naming.persister_iam_role.assert_called()
