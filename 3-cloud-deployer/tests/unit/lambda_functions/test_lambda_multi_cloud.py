"""
Lambda Function Runtime Multi-Cloud Tests.

Tests cover:
- Ingestion: Token validation, payload envelope handling  
- Writer: Token validation, DynamoDB write logic
- Connector: Payload envelope creation
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import os


# ==========================================
# Ingestion Lambda Tests
# ==========================================

class TestIngestionTokenValidation:
    """Tests for Ingestion Lambda token validation."""

    def test_ingestion_rejects_invalid_token(self):
        """Ingestion should return 403 when token is invalid."""
        # Import fresh module with mocked environment
        import sys
        if "src.providers.aws.lambda_functions.ingestion.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.ingestion.lambda_function"]
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DIGITAL_TWIN_INFO": json.dumps({"config": {"digital_twin_name": "test"}})
        }):
            from src.providers.aws.lambda_functions.ingestion import lambda_function as ingestion
            
            event = {
                "headers": {"x-inter-cloud-token": "wrong-token"},
                "body": json.dumps({"payload": {"iotDeviceId": "dev1"}})
            }
            
            result = ingestion.lambda_handler(event, None)
            
            assert result["statusCode"] == 403
            assert "Unauthorized" in result["body"]

    def test_ingestion_rejects_missing_payload(self):
        """Ingestion should return 400 when payload is missing."""
        import sys
        if "src.providers.aws.lambda_functions.ingestion.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.ingestion.lambda_function"]
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DIGITAL_TWIN_INFO": json.dumps({"config": {"digital_twin_name": "test"}})
        }):
            from src.providers.aws.lambda_functions.ingestion import lambda_function as ingestion
            
            event = {
                "headers": {"x-inter-cloud-token": "correct-token"},
                "body": json.dumps({})  # Missing payload
            }
            
            result = ingestion.lambda_handler(event, None)
            
            assert result["statusCode"] == 400
            assert "payload" in result["body"].lower()

    def test_ingestion_rejects_missing_device_id(self):
        """Ingestion should return 400 when iotDeviceId is missing."""
        import sys
        if "src.providers.aws.lambda_functions.ingestion.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.ingestion.lambda_function"]
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DIGITAL_TWIN_INFO": json.dumps({"config": {"digital_twin_name": "test"}})
        }):
            from src.providers.aws.lambda_functions.ingestion import lambda_function as ingestion
            
            event = {
                "headers": {"x-inter-cloud-token": "correct-token"},
                "body": json.dumps({"payload": {"temperature": 25}})  # Missing iotDeviceId
            }
            
            result = ingestion.lambda_handler(event, None)
            
            assert result["statusCode"] == 400
            assert "iotDeviceId" in result["body"]


# ==========================================
# Writer Lambda Tests
# ==========================================

class TestWriterTokenValidation:
    """Tests for Writer Lambda token validation."""

    @patch("boto3.resource")
    def test_writer_rejects_invalid_token(self, mock_boto):
        """Writer should return 403 when token is invalid."""
        import sys
        if "src.providers.aws.lambda_functions.writer.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.writer.lambda_function"]
        
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto.return_value = mock_dynamodb
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DYNAMODB_TABLE_NAME": "test-table"
        }):
            from src.providers.aws.lambda_functions.writer import lambda_function as writer
            
            event = {
                "headers": {"x-inter-cloud-token": "wrong-token"},
                "body": json.dumps({"payload": {"id": "123"}})
            }
            
            result = writer.lambda_handler(event, None)
            
            assert result["statusCode"] == 403
            assert "Unauthorized" in result["body"]

    @patch("boto3.resource")
    def test_writer_accepts_valid_token_and_writes(self, mock_boto):
        """Writer should accept valid token and write to DynamoDB."""
        import sys
        if "src.providers.aws.lambda_functions.writer.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.writer.lambda_function"]
        
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto.return_value = mock_dynamodb
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DYNAMODB_TABLE_NAME": "test-table"
        }):
            from src.providers.aws.lambda_functions.writer import lambda_function as writer
            
            # Patch the table directly in the module
            writer.table = mock_table
            
            event = {
                "headers": {"x-inter-cloud-token": "correct-token"},
                "body": json.dumps({
                    "source_cloud": "azure",
                    "payload": {"id": "123", "temperature": 25}
                })
            }
            
            result = writer.lambda_handler(event, None)
            
            assert result["statusCode"] == 200
            mock_table.put_item.assert_called_once()

    @patch("boto3.resource")
    def test_writer_validates_payload_is_dict(self, mock_boto):
        """Writer should return 400 when payload is not a dict."""
        import sys
        if "src.providers.aws.lambda_functions.writer.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.writer.lambda_function"]
        
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto.return_value = mock_dynamodb
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DYNAMODB_TABLE_NAME": "test-table"
        }):
            from src.providers.aws.lambda_functions.writer import lambda_function as writer
            
            event = {
                "headers": {"x-inter-cloud-token": "correct-token"},
                "body": json.dumps({
                    "payload": "not-a-dict"  # Invalid: should be object
                })
            }
            
            result = writer.lambda_handler(event, None)
            
            assert result["statusCode"] == 400
            assert "must be a JSON object" in result["body"]


# ==========================================
# Connector Lambda Tests
# ==========================================

class TestConnectorPayloadEnvelope:
    """Tests for Connector Lambda payload envelope creation."""

    def test_connector_raises_on_missing_config(self):
        """Connector should raise when REMOTE_INGESTION_URL or token is missing."""
        import sys
        if "src.providers.aws.lambda_functions.connector.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.connector.lambda_function"]
        
        with patch.dict(os.environ, {"REMOTE_INGESTION_URL": "", "INTER_CLOUD_TOKEN": ""}, clear=True):
            from src.providers.aws.lambda_functions.connector import lambda_function as connector
            
            with pytest.raises(ValueError, match="Missing configuration"):
                connector.lambda_handler({"data": "test"}, None)

    @patch("urllib.request.urlopen")
    def test_connector_creates_correct_envelope(self, mock_urlopen):
        """Connector should create payload envelope with all required fields."""
        import sys
        if "src.providers.aws.lambda_functions.connector.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.connector.lambda_function"]
        
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        with patch.dict(os.environ, {
            "REMOTE_INGESTION_URL": "https://example.com/ingestion",
            "INTER_CLOUD_TOKEN": "test-token"
        }):
            from src.providers.aws.lambda_functions.connector import lambda_function as connector
            
            original_event = {"iotDeviceId": "sensor-1", "temperature": 25}
            connector.lambda_handler(original_event, None)
            
            # Get the request that was sent
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            
            # Parse the payload
            sent_data = json.loads(request.data.decode('utf-8'))
            
            # Verify envelope structure
            assert sent_data["source_cloud"] == "aws"
            assert sent_data["target_layer"] == "L2"
            assert sent_data["message_type"] == "telemetry"
            assert "timestamp" in sent_data
            assert "trace_id" in sent_data
            assert sent_data["payload"] == original_event

    @patch("urllib.request.urlopen")
    def test_connector_sends_auth_header(self, mock_urlopen):
        """Connector should send X-Inter-Cloud-Token header."""
        import sys
        if "src.providers.aws.lambda_functions.connector.lambda_function" in sys.modules:
            del sys.modules["src.providers.aws.lambda_functions.connector.lambda_function"]
        
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        with patch.dict(os.environ, {
            "REMOTE_INGESTION_URL": "https://example.com/ingestion",
            "INTER_CLOUD_TOKEN": "secret-token-xyz"
        }):
            from src.providers.aws.lambda_functions.connector import lambda_function as connector
            
            connector.lambda_handler({"data": "test"}, None)
            
            request = mock_urlopen.call_args[0][0]
            assert request.get_header("X-inter-cloud-token") == "secret-token-xyz"
