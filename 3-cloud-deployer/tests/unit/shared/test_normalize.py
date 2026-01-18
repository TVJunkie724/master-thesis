"""
Unit tests for normalize_telemetry function.

Tests the field normalization for cross-cloud data consistency:
- device_id normalization from iotDeviceId, deviceId, IoTDeviceId
- timestamp normalization from time, ts
- Backward compatibility (time field preserved)
"""
import pytest
import os
import sys
import importlib.util
from datetime import datetime


def _load_normalize_module():
    """Load normalize module using importlib (handles _shared directory)."""
    # Build absolute path to normalize.py
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    normalize_path = os.path.join(
        tests_dir, "..", "..", "..", "src", "providers", "aws", "lambda_functions", "_shared", "normalize.py"
    )
    normalize_path = os.path.abspath(normalize_path)
    
    spec = importlib.util.spec_from_file_location("normalize", normalize_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNormalizeTelemetryDeviceId:
    """Tests for device_id field normalization."""

    def test_iotDeviceId_normalized_to_device_id(self):
        """iotDeviceId should be normalized to device_id."""
        normalize = _load_normalize_module()
        
        event = {"iotDeviceId": "sensor-1", "temperature": 25}
        result = normalize.normalize_telemetry(event)
        
        assert result["device_id"] == "sensor-1"
        assert "iotDeviceId" not in result  # Should be removed

    def test_deviceId_normalized_to_device_id(self):
        """deviceId should be normalized to device_id."""
        normalize = _load_normalize_module()
        
        event = {"deviceId": "sensor-2", "temperature": 25}
        result = normalize.normalize_telemetry(event)
        
        assert result["device_id"] == "sensor-2"
        assert "deviceId" not in result

    def test_IoTDeviceId_normalized_to_device_id(self):
        """IoTDeviceId (capital T) should be normalized to device_id."""
        normalize = _load_normalize_module()
        
        event = {"IoTDeviceId": "sensor-3", "temperature": 25}
        result = normalize.normalize_telemetry(event)
        
        assert result["device_id"] == "sensor-3"
        assert "IoTDeviceId" not in result

    def test_device_id_preserved_if_already_present(self):
        """Existing device_id should not be overwritten."""
        normalize = _load_normalize_module()
        
        event = {"device_id": "correct", "iotDeviceId": "wrong", "temperature": 25}
        result = normalize.normalize_telemetry(event)
        
        assert result["device_id"] == "correct"
        # iotDeviceId should still be in the event since device_id was already present
        assert result.get("iotDeviceId") == "wrong"

    def test_no_device_id_field_leaves_result_without_device_id(self):
        """If no device ID field exists, result should not have device_id."""
        normalize = _load_normalize_module()
        
        event = {"temperature": 25}
        result = normalize.normalize_telemetry(event)
        
        assert "device_id" not in result


class TestNormalizeTelemetryTimestamp:
    """Tests for timestamp field normalization."""

    def test_time_normalized_to_timestamp(self):
        """time field should be copied to timestamp."""
        normalize = _load_normalize_module()
        
        event = {"device_id": "d1", "time": "2024-01-01T00:00:00Z"}
        result = normalize.normalize_telemetry(event)
        
        assert result["timestamp"] == "2024-01-01T00:00:00Z"
        assert result["time"] == "2024-01-01T00:00:00Z"  # Original preserved

    def test_ts_normalized_to_timestamp(self):
        """ts field should be copied to timestamp."""
        normalize = _load_normalize_module()
        
        event = {"device_id": "d1", "ts": "1704067200000"}
        result = normalize.normalize_telemetry(event)
        
        assert result["timestamp"] == "1704067200000"
        assert result["ts"] == "1704067200000"  # Original preserved

    def test_timestamp_preserved_if_already_present(self):
        """Existing timestamp should not be overwritten."""
        normalize = _load_normalize_module()
        
        event = {"device_id": "d1", "timestamp": "correct", "time": "wrong"}
        result = normalize.normalize_telemetry(event)
        
        assert result["timestamp"] == "correct"
        assert result["time"] == "wrong"  # time still preserved

    def test_timestamp_generated_if_missing(self):
        """If no timestamp field exists, one should be generated."""
        normalize = _load_normalize_module()
        
        event = {"device_id": "d1", "temperature": 25}
        result = normalize.normalize_telemetry(event)
        
        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")  # ISO format with Z suffix

    def test_time_field_preserved_for_backward_compatibility(self):
        """time field should be preserved (not popped) for backward compatibility."""
        normalize = _load_normalize_module()
        
        event = {"device_id": "d1", "time": "2024-01-01T00:00:00Z", "payload": {}}
        result = normalize.normalize_telemetry(event)
        
        # Both should exist
        assert result["timestamp"] == "2024-01-01T00:00:00Z"
        assert result["time"] == "2024-01-01T00:00:00Z"


class TestNormalizeTelemetryEdgeCases:
    """Edge case tests for normalize_telemetry."""

    def test_non_dict_input_returned_unchanged(self):
        """Non-dict input should be returned unchanged."""
        normalize = _load_normalize_module()
        
        assert normalize.normalize_telemetry("string") == "string"
        assert normalize.normalize_telemetry(123) == 123
        assert normalize.normalize_telemetry(None) is None
        assert normalize.normalize_telemetry([1, 2, 3]) == [1, 2, 3]

    def test_empty_dict_returns_with_generated_timestamp(self):
        """Empty dict should get a generated timestamp."""
        normalize = _load_normalize_module()
        
        result = normalize.normalize_telemetry({})
        
        assert "timestamp" in result

    def test_original_event_not_mutated(self):
        """Original event should not be mutated."""
        normalize = _load_normalize_module()
        
        original = {"iotDeviceId": "sensor-1", "time": "2024-01-01T00:00:00Z"}
        original_copy = original.copy()
        
        result = normalize.normalize_telemetry(original)
        
        # Original should be unchanged
        assert original == original_copy
        # Result should be different
        assert result != original

    def test_full_normalization_flow(self):
        """Test complete normalization from raw IoT format."""
        normalize = _load_normalize_module()
        
        # Simulate raw IoT device payload
        raw_event = {
            "iotDeviceId": "temperature-sensor-1",
            "time": "1704067200000",
            "temperature": 23.5,
            "humidity": 60
        }
        
        result = normalize.normalize_telemetry(raw_event)
        
        # Canonical fields created
        assert result["device_id"] == "temperature-sensor-1"
        assert result["timestamp"] == "1704067200000"
        
        # Original time preserved for backward compatibility
        assert result["time"] == "1704067200000"
        
        # iotDeviceId should be removed (popped)
        assert "iotDeviceId" not in result
        
        # Other fields preserved
        assert result["temperature"] == 23.5
        assert result["humidity"] == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
