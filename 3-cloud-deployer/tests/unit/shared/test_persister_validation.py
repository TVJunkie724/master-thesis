"""
Unit tests for persister timestamp validation.

Tests that persisters correctly:
- Require timestamp field after normalization
- Use timestamp as sort key (AWS DynamoDB) or document ID (Azure Cosmos, GCP Firestore)
- Remove time field to avoid duplication
"""
import pytest
import os
import sys
import importlib.util
from unittest.mock import patch, MagicMock
import json


def _get_project_root():
    """Get project root path."""
    # From tests/unit/shared/ go up 3 levels to project root
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(tests_dir, "..", "..", ".."))


def _load_normalize_module():
    """Load normalize module using importlib."""
    project_root = _get_project_root()
    normalize_path = os.path.join(
        project_root, "src", "providers", "aws", "lambda_functions", "_shared", "normalize.py"
    )
    
    spec = importlib.util.spec_from_file_location("normalize", normalize_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAWSPersisterTimestampValidation:
    """Tests for AWS Persister timestamp handling."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup mocks for AWS persister tests."""
        self.boto3_patch = patch('boto3.resource')
        self.client_patch = patch('boto3.client')
        self.mock_boto3 = self.boto3_patch.start()
        self.mock_client = self.client_patch.start()
        
        # Setup mock table
        self.mock_table = MagicMock()
        self.mock_dynamodb = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.mock_boto3.return_value = self.mock_dynamodb
        
        yield
        
        self.boto3_patch.stop()
        self.client_patch.stop()
    
    def _load_persister(self, extra_env=None):
        """Load persister module with environment."""
        # Clear cached modules
        for key in list(sys.modules.keys()):
            if 'persister' in key or 'lambda_function' in key:
                del sys.modules[key]
        
        env = {
            "DIGITAL_TWIN_INFO": json.dumps({"config": {"digital_twin_name": "test"}}),
            "DYNAMODB_TABLE_NAME": "test-table",
            "EVENT_CHECKER_LAMBDA_NAME": "test-checker",
            "USE_EVENT_CHECKING": "false"
        }
        if extra_env:
            env.update(extra_env)
        
        project_root = _get_project_root()
        persister_path = os.path.join(
            project_root, "src", "providers", "aws", "lambda_functions", "persister", "lambda_function.py"
        )
        
        with patch.dict(os.environ, env):
            spec = importlib.util.spec_from_file_location("lambda_function", persister_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    def test_persister_requires_timestamp_field(self):
        """Persister should raise ValueError if timestamp is missing."""
        module = self._load_persister()
        
        # Event without timestamp (before normalization)
        event = {"device_id": "d1", "temperature": 25}
        
        with pytest.raises(ValueError, match="timestamp"):
            module.lambda_handler(event, None)

    def test_persister_accepts_event_with_timestamp(self):
        """Persister should accept event with timestamp field."""
        module = self._load_persister()
        
        event = {
            "device_id": "device1",
            "timestamp": "2024-01-01T00:00:00Z",
            "temperature": 25
        }
        
        # Should not raise - success is indicated by no exception
        module.lambda_handler(event, None)
        # Persister returns None on success

    def test_persister_removes_time_field_to_avoid_duplication(self):
        """Persister should remove time field since timestamp is canonical."""
        module = self._load_persister()
        
        event = {
            "device_id": "device1",
            "timestamp": "2024-01-01T00:00:00Z",
            "time": "2024-01-01T00:00:00Z",  # Duplicate from normalization
            "temperature": 25
        }
        
        module.lambda_handler(event, None)
        
        # Verify put_item was called
        self.mock_table.put_item.assert_called_once()
        
        # Get the item that was put
        call_args = self.mock_table.put_item.call_args
        item = call_args.kwargs.get("Item") or call_args[1].get("Item")
        
        # time should NOT be in the stored item
        assert "time" not in item
        # timestamp should be in the stored item
        assert "timestamp" in item


class TestFieldStandardizationEndToEnd:
    """End-to-end tests for field standardization flow."""

    def test_normalize_then_persist_flow(self):
        """Test complete flow: raw IoT → normalize → persister-ready format."""
        normalize = _load_normalize_module()
        
        # Step 1: Raw IoT payload (what device sends)
        raw_iot_payload = {
            "iotDeviceId": "temperature-sensor-1",
            "time": "1704067200000",
            "temperature": 23.5
        }
        
        # Step 2: Normalize (what entry points do)
        normalized = normalize.normalize_telemetry(raw_iot_payload)
        
        # Step 3: Verify persister-ready format
        assert "device_id" in normalized, "device_id required for partition key"
        assert "timestamp" in normalized, "timestamp required for sort key"
        assert normalized["device_id"] == "temperature-sensor-1"
        assert normalized["timestamp"] == "1704067200000"
        
        # Step 4: time should still exist for backward compatibility
        # (persister will remove it during storage)
        assert normalized["time"] == "1704067200000"

    def test_already_normalized_payload_unchanged(self):
        """Pre-normalized payload should pass through unchanged."""
        normalize = _load_normalize_module()
        
        # Already has canonical format
        pre_normalized = {
            "device_id": "sensor-1",
            "timestamp": "2024-01-01T00:00:00Z",
            "temperature": 25
        }
        
        result = normalize.normalize_telemetry(pre_normalized)
        
        assert result["device_id"] == "sensor-1"
        assert result["timestamp"] == "2024-01-01T00:00:00Z"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
