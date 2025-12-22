"""
Unit tests for AWS Provider module.

Tests the AWSProvider class and related modules:
- clients.py: Client initialization
- naming.py: Resource naming conventions
- provider.py: Main provider interface
"""

import pytest
from unittest.mock import patch, MagicMock
from src.providers.aws.naming import AWSNaming


class TestAWSNaming:
    """Test suite for AWSNaming class."""

    def setup_method(self):
        """Create a naming instance for tests."""
        self.naming = AWSNaming("my-twin")

    # ==========================================
    # Layer 1: Data Acquisition
    # ==========================================

    def test_dispatcher_iam_role(self):
        """Test dispatcher IAM role name generation."""
        assert self.naming.dispatcher_iam_role() == "my-twin-dispatcher"

    def test_dispatcher_lambda_function(self):
        """Test dispatcher Lambda function name generation."""
        assert self.naming.dispatcher_lambda_function() == "my-twin-dispatcher"

    def test_dispatcher_iot_rule_replaces_hyphens(self):
        """Test that IoT rule name replaces hyphens with underscores."""
        assert self.naming.dispatcher_iot_rule() == "my_twin_trigger_dispatcher"

    def test_connector_lambda_function_with_device_id(self):
        """Test connector Lambda name includes device ID."""
        result = self.naming.connector_lambda_function("sensor-001")
        assert result == "my-twin-sensor-001-connector"

    def test_ingestion_lambda_function(self):
        """Test ingestion Lambda name."""
        assert self.naming.ingestion_lambda_function() == "my-twin-ingestion"

    # ==========================================
    # Layer 2: Data Processing
    # ==========================================

    def test_persister_names(self):
        """Test persister role and function names."""
        assert self.naming.persister_iam_role() == "my-twin-persister"
        assert self.naming.persister_lambda_function() == "my-twin-persister"

    def test_event_checker_names(self):
        """Test event checker role and function names."""
        assert self.naming.event_checker_iam_role() == "my-twin-event-checker"
        assert self.naming.event_checker_lambda_function() == "my-twin-event-checker"

    def test_lambda_chain_names(self):
        """Test Lambda chain (Step Functions) names."""
        assert self.naming.lambda_chain_iam_role() == "my-twin-lambda-chain"
        assert self.naming.lambda_chain_step_function() == "my-twin-lambda-chain"

    def test_event_feedback_names(self):
        """Test event feedback role and function names."""
        assert self.naming.event_feedback_iam_role() == "my-twin-event-feedback"
        assert self.naming.event_feedback_lambda_function() == "my-twin-event-feedback"

    # ==========================================
    # Layer 3: Storage
    # ==========================================

    def test_hot_dynamodb_table(self):
        """Test hot storage DynamoDB table name."""
        assert self.naming.hot_dynamodb_table() == "my-twin-hot-iot-data"

    def test_s3_bucket_names_are_lowercase(self):
        """Test that S3 bucket names are always lowercase."""
        naming = AWSNaming("My-Factory-Twin")
        assert naming.cold_s3_bucket() == "my-factory-twin-cold-iot-data"
        assert naming.archive_s3_bucket() == "my-factory-twin-archive-iot-data"
        assert naming.twinmaker_s3_bucket() == "my-factory-twin-twinmaker"

    def test_mover_names(self):
        """Test hot-cold and cold-archive mover names."""
        assert self.naming.hot_cold_mover_iam_role() == "my-twin-hot-to-cold-mover"
        assert self.naming.hot_cold_mover_lambda_function() == "my-twin-hot-to-cold-mover"
        assert self.naming.hot_cold_mover_event_rule() == "my-twin-hot-to-cold-mover"
        
        assert self.naming.cold_archive_mover_iam_role() == "my-twin-cold-to-archive-mover"
        assert self.naming.cold_archive_mover_lambda_function() == "my-twin-cold-to-archive-mover"
        assert self.naming.cold_archive_mover_event_rule() == "my-twin-cold-to-archive-mover"

    def test_hot_reader_names(self):
        """Test hot reader Lambda names."""
        assert self.naming.hot_reader_iam_role() == "my-twin-hot-reader"
        assert self.naming.hot_reader_lambda_function() == "my-twin-hot-reader"
        assert self.naming.hot_reader_last_entry_iam_role() == "my-twin-hot-reader-last-entry"
        assert self.naming.hot_reader_last_entry_lambda_function() == "my-twin-hot-reader-last-entry"

    def test_hot_writer_lambda_function(self):
        """Test hot writer Lambda name for multi-cloud."""
        assert self.naming.hot_writer_lambda_function() == "my-twin-hot-writer"

    # ==========================================
    # Layer 4 & 5
    # ==========================================

    def test_twinmaker_names(self):
        """Test TwinMaker workspace and role names."""
        assert self.naming.twinmaker_iam_role() == "my-twin-twinmaker"
        assert self.naming.twinmaker_workspace() == "my-twin-twinmaker"

    def test_twinmaker_component_type_with_device(self):
        """Test TwinMaker component type includes device ID."""
        result = self.naming.twinmaker_component_type("temperature-sensor")
        assert result == "my-twin-temperature-sensor"

    def test_grafana_names(self):
        """Test Grafana workspace and role names."""
        assert self.naming.grafana_workspace() == "my-twin-grafana"
        assert self.naming.grafana_iam_role() == "my-twin-grafana"

    # ==========================================
    # IoT Device Resources
    # ==========================================

    def test_iot_thing_names(self):
        """Test IoT thing and policy names."""
        assert self.naming.iot_thing("sensor-001") == "my-twin-sensor-001"
        assert self.naming.iot_thing_policy("sensor-001") == "my-twin-sensor-001"

    def test_processor_names_with_device(self):
        """Test processor role and function names include device ID."""
        assert self.naming.processor_iam_role("sensor-001") == "my-twin-sensor-001-processor"
        assert self.naming.processor_lambda_function("sensor-001") == "my-twin-sensor-001-processor"


class TestAWSProviderNaming:
    """Test AWSProvider integration with naming module."""

    @patch('src.providers.aws.clients.boto3')
    def test_provider_naming_property(self, mock_boto3):
        """Test that provider.naming returns AWSNaming instance."""
        from src.providers.aws.provider import AWSProvider
        
        provider = AWSProvider()
        provider.initialize_clients({
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_region": "us-east-1"
        }, twin_name="test-twin")
        
        assert provider.naming.twin_name == "test-twin"
        assert provider.naming.dispatcher_iam_role() == "test-twin-dispatcher"

    def test_provider_naming_raises_before_init(self):
        """Test that accessing naming before init raises error."""
        from src.providers.aws.provider import AWSProvider
        
        provider = AWSProvider()
        
        with pytest.raises(RuntimeError) as exc_info:
            _ = provider.naming
        
        assert "not initialized" in str(exc_info.value)


class TestAWSClients:
    """Test AWS client initialization module."""

    @patch('src.providers.aws.clients.boto3')
    def test_create_aws_clients_creates_all_clients(self, mock_boto3):
        """Test that all required clients are created."""
        from src.providers.aws.clients import create_aws_clients
        
        mock_boto3.client.return_value = MagicMock()
        
        clients = create_aws_clients(
            access_key_id="test",
            secret_access_key="test",
            region="us-east-1"
        )
        
        # Check all expected clients are present
        expected_clients = [
            "iam", "iot", "iot_data", "lambda", "sfn",
            "dynamodb", "s3", "events", "apigateway",
            "twinmaker", "grafana", "sts", "logs"
        ]
        for client_name in expected_clients:
            assert client_name in clients, f"Missing client: {client_name}"
    
    @patch('src.providers.aws.clients.boto3')
    def test_create_aws_clients_passes_credentials(self, mock_boto3):
        """Test that credentials are passed correctly to boto3."""
        from src.providers.aws.clients import create_aws_clients
        
        mock_boto3.client.return_value = MagicMock()
        
        create_aws_clients(
            access_key_id="my-key",
            secret_access_key="my-secret",
            region="eu-central-1"
        )
        
        # Check first call to verify credentials
        first_call = mock_boto3.client.call_args_list[0]
        _, kwargs = first_call
        assert kwargs["aws_access_key_id"] == "my-key"
        assert kwargs["aws_secret_access_key"] == "my-secret"
        assert kwargs["region_name"] == "eu-central-1"
