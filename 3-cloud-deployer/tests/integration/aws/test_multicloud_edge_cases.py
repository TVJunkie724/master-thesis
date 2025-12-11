"""
Edge Case Tests for Multi-Cloud L3→L4 Integration.

This module tests the critical L3→L4 multi-cloud integration paths:
- L3 Hot creates Function URLs when L3≠L4
- L4 deploys Digital Twin Data Connector when L3≠L4
- Config inter-cloud persistence
- Hot Reader HTTP handling
- Digital Twin Data Connector runtime behavior

Categories covered:
1. L3→L4 Multi-Cloud Integration
2. Config Validation
3. Hot Reader HTTP Handling  
4. Digital Twin Data Connector Runtime
5. Deployer Integration
6. Security Edge Cases
"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch, PropertyMock
from botocore.exceptions import ClientError


# ===========================================
# Category 1: L3→L4 Multi-Cloud Integration
# ===========================================

class TestL3ToL4MultiCloudIntegration:
    """Tests for L3→L4 multi-cloud deployment flow."""
    
    @patch("time.sleep")
    @patch("secrets.token_urlsafe", return_value="test-token-abc123")
    def test_deploy_l0_creates_function_urls_when_l4_different(
        self, mock_token, mock_sleep
    ):
        """l0_adapter.deploy_l0() creates Hot Reader Function URLs when L3≠L4.
        
        NOTE: Function URL creation moved from L3 adapter to L0 adapter.
        """
        from src.providers.aws.layers.l0_adapter import deploy_l0
        
        # Mock context with different L3 and L4 providers
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "azure"  # Different!
        }
        mock_context.project_path = MagicMock()
        mock_context.project_path.parent.parent = "/mock/project"
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-hot-reader"
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-hot-reader-last"
        mock_provider.clients = {"lambda": MagicMock(), "iam": MagicMock(), "dynamodb": MagicMock()}
        
        # Setup Lambda client mock for Function URL creation
        mock_provider.clients["lambda"].create_function_url_config.return_value = {
            "FunctionUrl": "https://test-function-url.lambda-url.us-east-1.on.aws/"
        }
        mock_provider.clients["lambda"].get_function_configuration.return_value = {
            "Environment": {"Variables": {"TABLE_NAME": "test-table"}}
        }
        
        with patch("src.core.config_loader.save_inter_cloud_connection") as mock_save:
            deploy_l0(mock_context, mock_provider)
        
        # Verify Function URL was created
        assert mock_provider.clients["lambda"].create_function_url_config.called
        
        # Verify inter-cloud connection saved
        mock_save.assert_called()
    
    @patch("time.sleep")
    def test_deploy_l4_creates_dt_data_connector_when_l3_different(self, mock_sleep):
        """l4_adapter.deploy_l4() creates Digital Twin Data Connector when L3≠L4."""
        from src.providers.aws.layers.l4_adapter import deploy_l4
        
        # Mock context with different L3 and L4 providers
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_3_hot_provider": "azure",  # Different!
            "layer_4_provider": "aws"
        }
        mock_context.config.iot_devices = []
        mock_context.config.twinmaker_hierarchy = None
        mock_context.project_path = MagicMock()
        mock_context.project_path.parent.parent = "/mock/project"
        
        # Create mock inter_cloud config file
        inter_cloud_config = {
            "connections": {
                "azure_l3_to_aws_l4": {
                    "url": "https://azure-hot-reader.azurewebsites.net/api/hot-reader",
                    "token": "secret-token-abc"
                },
                "azure_l3_to_aws_l4_last_entry": {
                    "url": "https://azure-hot-reader.azurewebsites.net/api/hot-reader-last",
                    "token": "secret-token-abc"
                }
            }
        }
        
        mock_provider = MagicMock()
        mock_provider.clients = {"s3": MagicMock(), "iam": MagicMock(), "iottwinmaker": MagicMock(), "lambda": MagicMock()}
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value=inter_cloud_config):
                    with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_s3_bucket"):
                        with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_iam_role"):
                            with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_workspace"):
                                with patch("src.providers.aws.layers.layer_3_storage.create_digital_twin_data_connector_iam_role") as mock_role:
                                    with patch("src.providers.aws.layers.layer_3_storage.create_digital_twin_data_connector_lambda_function") as mock_func:
                                        with patch("src.providers.aws.layers.layer_3_storage.create_digital_twin_data_connector_last_entry_iam_role"):
                                            with patch("src.providers.aws.layers.layer_3_storage.create_digital_twin_data_connector_last_entry_lambda_function"):
                                                deploy_l4(mock_context, mock_provider)
        
        # Verify DT Data Connector was created
        mock_role.assert_called_once()
        mock_func.assert_called_once()
    
    @patch("time.sleep")
    def test_deploy_l4_skips_dt_connector_when_same_cloud(self, mock_sleep):
        """l4_adapter.deploy_l4() skips DT Data Connector when L3==L4."""
        from src.providers.aws.layers.l4_adapter import deploy_l4
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_3_hot_provider": "aws",  # Same!
            "layer_4_provider": "aws"
        }
        mock_context.config.iot_devices = []
        mock_context.config.twinmaker_hierarchy = None
        
        mock_provider = MagicMock()
        mock_provider.clients = {"s3": MagicMock(), "iam": MagicMock(), "iottwinmaker": MagicMock()}
        
        with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_s3_bucket"):
            with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_iam_role"):
                with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_workspace"):
                    with patch("src.providers.aws.layers.layer_3_storage.create_digital_twin_data_connector_iam_role") as mock_role:
                        deploy_l4(mock_context, mock_provider)
        
        # Verify DT Data Connector was NOT created
        mock_role.assert_not_called()
    
    def test_deploy_l4_fails_when_l3_url_missing(self):
        """deploy_l4 raises ValueError when L3≠L4 but Hot Reader URL not configured."""
        from src.providers.aws.layers.l4_adapter import deploy_l4
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "aws"
        }
        mock_context.config.iot_devices = []
        mock_context.config.twinmaker_hierarchy = None
        mock_context.project_path = "/mock/project"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"s3": MagicMock(), "iam": MagicMock(), "iottwinmaker": MagicMock()}
        
        # Empty inter-cloud config
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value={"connections": {}}):
                    with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_s3_bucket"):
                        with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_iam_role"):
                            with patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_workspace"):
                                with pytest.raises(ValueError, match="Multi-cloud config incomplete"):
                                    deploy_l4(mock_context, mock_provider)


# ===========================================
# Category 2: Config Validation Edge Cases
# ===========================================

class TestConfigValidationEdgeCases:
    """Tests for config validation edge cases."""
    
    def test_config_providers_requires_layer_4_provider(self):
        """CONFIG_PROVIDERS_FILE schema requires layer_4_provider."""
        import constants as CONSTANTS
        
        schema = CONSTANTS.CONFIG_SCHEMAS[CONSTANTS.CONFIG_PROVIDERS_FILE]
        assert "layer_4_provider" in schema
    
    def test_config_providers_missing_layer_4_raises_error(self):
        """Validation fails when layer_4_provider is missing."""
        import validator
        import constants as CONSTANTS
        
        invalid_providers = json.dumps({
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws"
            # Missing layer_4_provider
        })
        
        with pytest.raises(ValueError, match="layer_4_provider"):
            validator.validate_config_content(CONSTANTS.CONFIG_PROVIDERS_FILE, invalid_providers)


# ===========================================
# Category 3: Deployer Integration Tests
# ===========================================

class TestDeployerIntegration:
    """Tests for deployer adapter integration."""
    
    @patch("time.sleep")
    def test_destroy_l3_hot_removes_function_url_when_l4_different(self, mock_sleep):
        """destroy_l3_hot() removes Function URLs when L3≠L4."""
        from src.providers.aws.layers.l3_adapter import destroy_l3_hot
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "azure"  # Different!
        }
        
        mock_provider = MagicMock()
        mock_provider.clients = {"lambda": MagicMock(), "iam": MagicMock(), "dynamodb": MagicMock()}
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-hot-reader"
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-hot-reader-last"
        
        with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_dynamodb_table"):
            with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_reader_lambda_function"):
                with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_reader_iam_role"):
                    with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_reader_last_entry_lambda_function"):
                        with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_reader_last_entry_iam_role"):
                            with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_reader_function_url") as mock_destroy_url:
                                with patch("src.providers.aws.layers.layer_3_storage.destroy_hot_reader_last_entry_function_url"):
                                    destroy_l3_hot(mock_context, mock_provider)
        
        # Verify Function URL was destroyed
        mock_destroy_url.assert_called_once()
    
    @patch("time.sleep")
    def test_destroy_l4_removes_dt_connector_when_l3_different(self, mock_sleep):
        """destroy_l4() removes DT Data Connector when L3≠L4."""
        from src.providers.aws.layers.l4_adapter import destroy_l4
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_3_hot_provider": "azure",  # Different!
            "layer_4_provider": "aws"
        }
        mock_context.config.iot_devices = []
        mock_context.config.twinmaker_hierarchy = None
        
        mock_provider = MagicMock()
        mock_provider.clients = {"s3": MagicMock(), "iam": MagicMock(), "iottwinmaker": MagicMock(), "lambda": MagicMock()}
        
        with patch("src.providers.aws.layers.layer_4_twinmaker.destroy_twinmaker_workspace"):
            with patch("src.providers.aws.layers.layer_4_twinmaker.destroy_twinmaker_iam_role"):
                with patch("src.providers.aws.layers.layer_4_twinmaker.destroy_twinmaker_s3_bucket"):
                    with patch("src.providers.aws.layers.layer_3_storage.destroy_digital_twin_data_connector_lambda_function") as mock_destroy:
                        with patch("src.providers.aws.layers.layer_3_storage.destroy_digital_twin_data_connector_iam_role"):
                            with patch("src.providers.aws.layers.layer_3_storage.destroy_digital_twin_data_connector_last_entry_lambda_function"):
                                with patch("src.providers.aws.layers.layer_3_storage.destroy_digital_twin_data_connector_last_entry_iam_role"):
                                    destroy_l4(mock_context, mock_provider)
        
        # Verify DT Data Connector was destroyed
        mock_destroy.assert_called_once()
    
    @patch("time.sleep")
    def test_l1_adapter_deploys_connector_when_l2_different(self, mock_sleep):
        """l1_adapter.deploy_l1() deploys Connector when L1≠L2."""
        from src.providers.aws.layers.l1_adapter import deploy_l1
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure"  # Different!
        }
        mock_context.config.iot_devices = [{"id": "device-1", "iotDeviceId": "device-1"}]
        mock_context.project_path = MagicMock()
        mock_context.project_path.parent.parent = "/mock/project"
        
        inter_cloud_config = {
            "connections": {
                "aws_l1_to_azure_l2": {
                    "url": "https://azure-ingestion.azurewebsites.net/api/ingest",
                    "token": "secret-token"
                }
            }
        }
        
        mock_provider = MagicMock()
        mock_provider.clients = {"lambda": MagicMock(), "iam": MagicMock(), "iot": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value=inter_cloud_config):
                    with patch("src.providers.aws.layers.layer_1_iot.create_dispatcher_iam_role"):
                        with patch("src.providers.aws.layers.layer_1_iot.create_dispatcher_lambda_function"):
                            with patch("src.providers.aws.layers.layer_1_iot.create_dispatcher_iot_rule"):
                                with patch("src.providers.aws.layers.layer_1_iot.create_iot_thing"):
                                    with patch("src.providers.aws.layers.layer_1_iot.post_init_values_to_iot_core"):
                                        with patch("src.providers.aws.layers.layer_1_iot.create_connector_iam_role") as mock_role:
                                            with patch("src.providers.aws.layers.layer_1_iot.create_connector_lambda_function") as mock_func:
                                                deploy_l1(mock_context, mock_provider)
        
        # Verify Connector was created
        mock_role.assert_called()
        mock_func.assert_called()


# ===========================================
# Category 4: Security Edge Cases
# ===========================================

class TestSecurityEdgeCases:
    """Tests for security edge cases."""
    
    def test_inter_cloud_token_is_secure_length(self):
        """Generated tokens are sufficiently long for security."""
        import secrets
        
        # Using secrets.token_urlsafe(32) should produce 43+ char token
        token = secrets.token_urlsafe(32)
        assert len(token) >= 32, "Token must be at least 32 characters"
    
    @patch("time.sleep")
    def test_connector_validates_url_and_token_before_creation(self, mock_sleep):
        """Connector creation fails fast when URL or token is empty."""
        from src.providers.aws.layers.layer_1_iot import create_connector_lambda_function
        
        mock_device = {"id": "device-1", "iotDeviceId": "device-1"}
        mock_provider = MagicMock()
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        
        with pytest.raises(ValueError, match="remote_ingestion_url is required"):
            create_connector_lambda_function(
                mock_device, mock_provider, mock_config, "/mock/path",
                remote_ingestion_url="",  # Empty!
                inter_cloud_token="valid-token"
            )
        
        with pytest.raises(ValueError, match="inter_cloud_token is required"):
            create_connector_lambda_function(
                mock_device, mock_provider, mock_config, "/mock/path",
                remote_ingestion_url="https://valid-url.com",
                inter_cloud_token=""  # Empty!
            )


# ===========================================
# Category 5: Provider Combinations
# ===========================================

class TestProviderCombinations:
    """Tests for various provider combination scenarios."""
    
    @patch("time.sleep")
    def test_all_layers_same_provider_skips_multicloud(self, mock_sleep):
        """Single-cloud deployment skips all multi-cloud components."""
        from src.providers.aws.layers.l3_adapter import deploy_l3_hot
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"  # All same
        }
        mock_context.project_path = MagicMock()
        mock_context.project_path.parent.parent = "/mock/project"
        
        mock_provider = MagicMock()
        mock_provider.clients = {"lambda": MagicMock(), "iam": MagicMock(), "dynamodb": MagicMock()}
        
        with patch("src.providers.aws.layers.layer_3_storage.create_hot_dynamodb_table"):
            with patch("src.providers.aws.layers.layer_3_storage.create_hot_reader_iam_role"):
                with patch("src.providers.aws.layers.layer_3_storage.create_hot_reader_lambda_function"):
                    with patch("src.providers.aws.layers.layer_3_storage.create_hot_reader_last_entry_iam_role"):
                        with patch("src.providers.aws.layers.layer_3_storage.create_hot_reader_last_entry_lambda_function"):
                            with patch("src.providers.aws.layers.layer_3_storage.create_hot_reader_function_url") as mock_url:
                                deploy_l3_hot(mock_context, mock_provider)
        
        # Verify Function URL was NOT created
        mock_url.assert_not_called()


# ===========================================
# Category 6: Boundary Conditions
# ===========================================

class TestBoundaryConditions:
    """Tests for boundary conditions and edge cases."""
    
    def test_empty_iot_devices_list_deploys_core_only(self):
        """Deployment with no IoT devices only creates core components."""
        from src.providers.aws.layers.l1_adapter import deploy_l1
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws"
        }
        mock_context.config.iot_devices = []  # Empty!
        
        mock_provider = MagicMock()
        mock_provider.clients = {"lambda": MagicMock(), "iam": MagicMock(), "iot": MagicMock()}
        
        with patch("src.providers.aws.layers.layer_1_iot.create_dispatcher_iam_role"):
            with patch("src.providers.aws.layers.layer_1_iot.create_dispatcher_lambda_function"):
                with patch("src.providers.aws.layers.layer_1_iot.create_dispatcher_iot_rule"):
                    with patch("src.providers.aws.layers.layer_1_iot.create_iot_thing") as mock_thing:
                        with patch("src.providers.aws.layers.layer_1_iot.post_init_values_to_iot_core") as mock_post:
                            deploy_l1(mock_context, mock_provider)
        
        # No IoT things created, no values posted
        mock_thing.assert_not_called()
        mock_post.assert_not_called()
    
    def test_special_characters_in_device_id_handled(self):
        """Device IDs with hyphens and underscores work correctly."""
        from src.providers.aws.naming import AWSNaming
        
        naming = AWSNaming("test-twin")
        
        # These should work without error
        assert naming.connector_lambda_function("device-1") == "test-twin-device-1-connector"
        assert naming.connector_lambda_function("device_2") == "test-twin-device_2-connector"
        assert naming.processor_lambda_function("temp-sensor-01") == "test-twin-temp-sensor-01-processor"
