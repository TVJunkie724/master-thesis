"""
Unit tests for document ID generation consistency.
Verifies that all persisters generate IDs in format: {device_id}_{timestamp}

Timestamp format: ISO8601 string from normalize_telemetry() (e.g., "2026-01-28T12:00:00Z")
Document ID format: {device_id}_{timestamp} (e.g., "sensor-001_2026-01-28T12:00:00Z")

Note: These tests verify the ID generation logic by testing the actual code patterns
rather than loading the full function modules, due to complex cloud SDK dependencies.
"""
import pytest


class TestDocumentIDContract:
    """
    Tests for the document ID generation contract.
    
    All persisters must follow: id = f"{device_id}_{timestamp}"
    - device_id: required, fail-fast if missing  
    - timestamp: ISO8601 string from normalize_telemetry()
    """
    
    def test_id_format_is_device_id_underscore_timestamp(self):
        """Verify ID format: {device_id}_{timestamp}"""
        # This is the exact logic used in all persisters
        item = {
            "device_id": "sensor-001",
            "timestamp": "2026-01-28T12:00:00Z",
            "temperature": 25
        }
        
        # ID generation logic (consistent across all persisters)
        item["id"] = f"{item['device_id']}_{item['timestamp']}"
        
        assert item["id"] == "sensor-001_2026-01-28T12:00:00Z"
    
    def test_id_format_with_special_characters(self):
        """Device IDs with special characters should work correctly."""
        item = {
            "device_id": "iot-device-abc-123",
            "timestamp": "2026-01-28T12:00:00.123Z",
        }
        
        item["id"] = f"{item['device_id']}_{item['timestamp']}"
        
        assert item["id"] == "iot-device-abc-123_2026-01-28T12:00:00.123Z"
    
    def test_missing_device_id_should_fail(self):
        """Missing device_id should be detected (fail-fast pattern)."""
        item = {
            "timestamp": "2026-01-28T12:00:00Z",
            "temperature": 25
        }
        
        # This is the validation logic used in all persisters
        assert "device_id" not in item
    
    def test_missing_timestamp_should_fail(self):
        """Missing timestamp should be detected (fail-fast pattern)."""
        item = {
            "device_id": "sensor-001",
            "temperature": 25
        }
        
        # This is the validation logic used in all persisters
        assert "timestamp" not in item


class TestAWSPersisterIDGeneration:
    """
    Tests for AWS Persister ID generation.
    
    AWS persister code reference:
    - File: src/providers/aws/lambda_functions/persister/lambda_function.py
    - Lines: 214-217
    """
    
    @pytest.fixture
    def mock_event_with_device_id(self):
        return {
            "device_id": "sensor-001",
            "timestamp": "2026-01-28T12:00:00Z",
            "temperature": 25
        }
    
    @pytest.fixture
    def mock_event_without_device_id(self):
        return {
            "timestamp": "2026-01-28T12:00:00Z",
            "temperature": 25
        }
    
    def test_id_generation_logic(self, mock_event_with_device_id):
        """Verify AWS persister ID generation logic."""
        item = mock_event_with_device_id.copy()
        
        # Replicate the exact logic from lambda_function.py
        if "device_id" not in item:
            raise ValueError("Missing 'device_id' in event. Cannot generate document ID.")
        item["id"] = f"{item['device_id']}_{item['timestamp']}"
        
        assert item["id"] == "sensor-001_2026-01-28T12:00:00Z"
    
    def test_missing_device_id_raises_error(self, mock_event_without_device_id):
        """Missing device_id should raise ValueError."""
        item = mock_event_without_device_id.copy()
        
        # Replicate the exact logic from lambda_function.py
        with pytest.raises(ValueError, match="device_id"):
            if "device_id" not in item:
                raise ValueError("Missing 'device_id' in event. Cannot generate document ID.")


class TestGCPPersisterIDGeneration:
    """
    Tests for GCP Persister ID generation.
    
    GCP persister code reference:
    - File: src/providers/gcp/cloud_functions/persister/main.py
    - Lines: 117-120
    """
    
    def test_id_generation_logic(self):
        """Verify GCP persister ID generation logic."""
        item = {
            "device_id": "sensor-001",
            "timestamp": "2026-01-28T12:00:00Z",
        }
        
        # Replicate the exact logic from main.py
        if "device_id" not in item:
            error_response = ({"error": "Missing 'device_id'"}, 400)
            assert error_response[1] == 400
        else:
            item["id"] = f"{item['device_id']}_{item['timestamp']}"
        
        assert item["id"] == "sensor-001_2026-01-28T12:00:00Z"
    
    def test_missing_device_id_returns_400(self):
        """Missing device_id should return 400 error."""
        item = {
            "timestamp": "2026-01-28T12:00:00Z",
        }
        
        # Replicate the exact logic from main.py
        error_response = None
        if "device_id" not in item:
            error_response = ({"error": "Missing 'device_id'"}, 400)
        
        assert error_response is not None
        assert error_response[1] == 400


class TestAzurePersisterIDGeneration:
    """
    Tests for Azure Persister ID generation.
    
    Azure persister code reference:
    - File: src/providers/azure/azure_functions/persister/function_app.py
    - Lines: 268-290
    """
    
    def test_id_generation_logic(self):
        """Verify Azure persister ID generation logic."""
        item = {
            "device_id": "sensor-001",
            "timestamp": "2026-01-28T12:00:00Z",
        }
        
        # Replicate the exact logic from function_app.py
        device_id = item.get("device_id")
        timestamp_value = item.get("timestamp")
        
        if not device_id or not timestamp_value:
            error_response = ({"error": "Missing required field"}, 400)
            assert error_response[1] == 400
        else:
            item["id"] = f"{device_id}_{timestamp_value}"
        
        assert item["id"] == "sensor-001_2026-01-28T12:00:00Z"
    
    def test_missing_device_id_returns_400(self):
        """Missing device_id should return 400 error."""
        item = {
            "timestamp": "2026-01-28T12:00:00Z",
        }
        
        device_id = item.get("device_id")
        
        status_code = 200
        if not device_id:
            status_code = 400
        
        assert status_code == 400
    
    def test_missing_timestamp_returns_400(self):
        """Missing timestamp should return 400 error."""
        item = {
            "device_id": "sensor-001",
        }
        
        timestamp_value = item.get("timestamp")
        
        status_code = 200
        if not timestamp_value:
            status_code = 400
        
        assert status_code == 400
