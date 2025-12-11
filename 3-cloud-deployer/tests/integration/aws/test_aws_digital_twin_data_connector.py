"""
Tests for Digital Twin Data Connector deployer functions.

Tests cover:
- NAM naming functions for dt-data-connector
- IAM role creation for dt-data-connector
- Lambda function creation for dt-data-connector
"""

import pytest
from unittest.mock import MagicMock, patch


class TestDigitalTwinDataConnectorNaming:
    """Tests for naming functions."""
    
    def test_digital_twin_data_connector_lambda_function_naming(self):
        """Verify naming convention for Digital Twin Data Connector Lambda."""
        from src.providers.aws.naming import AWSNaming
        
        naming = AWSNaming("my-twin")
        assert naming.digital_twin_data_connector_lambda_function() == "my-twin-dt-data-connector"
    
    def test_digital_twin_data_connector_iam_role_naming(self):
        """Verify naming convention for Digital Twin Data Connector IAM role."""
        from src.providers.aws.naming import AWSNaming
        
        naming = AWSNaming("my-twin")
        assert naming.digital_twin_data_connector_iam_role() == "my-twin-dt-data-connector"
    
    def test_digital_twin_data_connector_last_entry_lambda_function_naming(self):
        """Verify naming convention for Digital Twin Data Connector Last Entry Lambda."""
        from src.providers.aws.naming import AWSNaming
        
        naming = AWSNaming("my-twin")
        assert naming.digital_twin_data_connector_last_entry_lambda_function() == "my-twin-dt-data-connector-last-entry"
    
    def test_digital_twin_data_connector_last_entry_iam_role_naming(self):
        """Verify naming convention for Digital Twin Data Connector Last Entry IAM role."""
        from src.providers.aws.naming import AWSNaming
        
        naming = AWSNaming("my-twin")
        assert naming.digital_twin_data_connector_last_entry_iam_role() == "my-twin-dt-data-connector-last-entry"


class TestDigitalTwinDataConnectorDeployer:
    """Tests for deployer functions."""
    
    def test_create_digital_twin_data_connector_iam_role_creates_role(self):
        """Verify create_digital_twin_data_connector_iam_role creates correct role."""
        from src.providers.aws.layers.layer_3_storage import create_digital_twin_data_connector_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.digital_twin_data_connector_iam_role.return_value = "test-dt-data-connector"
        mock_provider.clients = {"iam": MagicMock()}
        
        with patch("time.sleep"):
            create_digital_twin_data_connector_iam_role(mock_provider)
        
        mock_provider.clients["iam"].create_role.assert_called_once()
        call_args = mock_provider.clients["iam"].create_role.call_args
        assert call_args[1]["RoleName"] == "test-dt-data-connector"
    
    def test_destroy_digital_twin_data_connector_iam_role_deletes_role(self):
        """Verify destroy_digital_twin_data_connector_iam_role cleans up role."""
        from src.providers.aws.layers.layer_3_storage import destroy_digital_twin_data_connector_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.digital_twin_data_connector_iam_role.return_value = "test-dt-data-connector"
        mock_provider.clients = {"iam": MagicMock()}
        mock_provider.clients["iam"].list_attached_role_policies.return_value = {"AttachedPolicies": []}
        mock_provider.clients["iam"].list_role_policies.return_value = {"PolicyNames": []}
        mock_provider.clients["iam"].list_instance_profiles_for_role.return_value = {"InstanceProfiles": []}
        
        destroy_digital_twin_data_connector_iam_role(mock_provider)
        
        mock_provider.clients["iam"].delete_role.assert_called_once_with(RoleName="test-dt-data-connector")
    
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    @patch("time.sleep")
    def test_create_digital_twin_data_connector_lambda_function_single_cloud(self, mock_sleep, mock_compile):
        """Verify Lambda creation for single-cloud mode (LOCAL_HOT_READER_NAME set)."""
        from src.providers.aws.layers.layer_3_storage import create_digital_twin_data_connector_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.digital_twin_data_connector_lambda_function.return_value = "test-dt-data-connector"
        mock_provider.naming.digital_twin_data_connector_iam_role.return_value = "test-dt-data-connector"
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-hot-reader"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.events = []
        mock_config.providers = {}
        
        # Single-cloud mode: no remote_reader_url
        create_digital_twin_data_connector_lambda_function(
            mock_provider, mock_config, "/mock/path"
        )
        
        mock_provider.clients["lambda"].create_function.assert_called_once()
        call_args = mock_provider.clients["lambda"].create_function.call_args
        env_vars = call_args[1]["Environment"]["Variables"]
        
        # Should have LOCAL_HOT_READER_NAME, not REMOTE_READER_URL
        assert "LOCAL_HOT_READER_NAME" in env_vars
        assert env_vars["LOCAL_HOT_READER_NAME"] == "test-hot-reader"
        assert "REMOTE_READER_URL" not in env_vars
    
    @patch("src.util.compile_lambda_function", return_value=b"mock-zip")
    @patch("time.sleep")
    def test_create_digital_twin_data_connector_lambda_function_multi_cloud(self, mock_sleep, mock_compile):
        """Verify Lambda creation for multi-cloud mode (REMOTE_READER_URL set)."""
        from src.providers.aws.layers.layer_3_storage import create_digital_twin_data_connector_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.digital_twin_data_connector_lambda_function.return_value = "test-dt-data-connector"
        mock_provider.naming.digital_twin_data_connector_iam_role.return_value = "test-dt-data-connector"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.events = []
        mock_config.providers = {}
        
        # Multi-cloud mode: with remote_reader_url
        create_digital_twin_data_connector_lambda_function(
            mock_provider, mock_config, "/mock/path",
            remote_reader_url="https://remote.example.com/hot-reader",
            inter_cloud_token="test-token-123"
        )
        
        mock_provider.clients["lambda"].create_function.assert_called_once()
        call_args = mock_provider.clients["lambda"].create_function.call_args
        env_vars = call_args[1]["Environment"]["Variables"]
        
        # Should have REMOTE_READER_URL and INTER_CLOUD_TOKEN
        assert "REMOTE_READER_URL" in env_vars
        assert env_vars["REMOTE_READER_URL"] == "https://remote.example.com/hot-reader"
        assert "INTER_CLOUD_TOKEN" in env_vars
        assert env_vars["INTER_CLOUD_TOKEN"] == "test-token-123"
        # Should NOT have LOCAL_HOT_READER_NAME
        assert "LOCAL_HOT_READER_NAME" not in env_vars


class TestHotReaderFunctionUrl:
    """Tests for Hot Reader Function URL functions."""
    
    def test_create_hot_reader_function_url_creates_url(self):
        """Verify create_hot_reader_function_url creates Function URL."""
        from src.providers.aws.layers.layer_3_storage import create_hot_reader_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-hot-reader"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_configuration.return_value = {
            "Environment": {"Variables": {"DYNAMODB_TABLE_NAME": "test-table"}}
        }
        mock_provider.clients["lambda"].create_function_url_config.return_value = {
            "FunctionUrl": "https://abc123.lambda-url.us-east-1.on.aws/"
        }
        
        result = create_hot_reader_function_url(mock_provider, "test-token")
        
        assert result == "https://abc123.lambda-url.us-east-1.on.aws/"
        mock_provider.clients["lambda"].update_function_configuration.assert_called_once()
        mock_provider.clients["lambda"].create_function_url_config.assert_called_once()
        mock_provider.clients["lambda"].add_permission.assert_called_once()
