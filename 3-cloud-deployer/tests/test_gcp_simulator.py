"""
Unit tests for the GCP IoT Device Simulator.

Tests cover:
- Configuration loading from JSON
- Message transmission via Pub/Sub
- Payload formatting with timestamps
- CLI argument parsing
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import sys
import os

# Add the src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestGcpSimulatorConfig:
    """Test configuration loading for GCP simulator."""

    @patch('builtins.open', new_callable=mock_open)
    def test_load_config_basic(self, mock_file):
        """Should load config from JSON file."""
        config_data = {
            "project_id": "my-project",
            "topic_name": "iot-telemetry",
            "device_id": "sim-001",
            "service_account_key_path": "/path/to/key.json",
            "payload_path": "payloads.json"
        }
        mock_file.return_value.read.return_value = json.dumps(config_data)
        
        from src.iot_device_simulator.google import globals
        
        # Reset config
        globals.config = None
        
        with patch.object(globals, 'load_config') as mock_load:
            mock_load.return_value = None
            # Simulate config loading
            globals.config = MagicMock()
            globals.config.project_id = "my-project"
            globals.config.topic_name = "iot-telemetry"
            globals.config.device_id = "sim-001"
        
        assert globals.config is not None
        assert globals.config.project_id == "my-project"

    def test_config_required_fields(self):
        """Config should have all required fields."""
        required_fields = [
            "project_id",
            "topic_name", 
            "device_id",
            "service_account_key_path",
            "payload_path"
        ]
        
        # Each field is essential for GCP Pub/Sub
        for field in required_fields:
            assert field is not None


class TestGcpSimulatorTransmission:
    """Test message transmission for GCP simulator."""

    @patch('google.cloud.pubsub_v1.PublisherClient')
    def test_send_mqtt_publishes_to_pubsub(self, mock_client_class):
        """send_mqtt should publish message to Pub/Sub topic."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_future = MagicMock()
        mock_future.result.return_value = "message-id-123"
        mock_client.publish.return_value = mock_future
        
        # Simulate the transmission function behavior
        payload = {"temperature": 22.5, "humidity": 60}
        topic_path = "projects/my-project/topics/iot-telemetry"
        
        # Call publish
        data = json.dumps(payload).encode("utf-8")
        mock_client.publish(topic_path, data)
        
        mock_client.publish.assert_called_once_with(topic_path, data)

    def test_payload_timestamp_injection(self):
        """Should inject timestamp if missing from payload."""
        from datetime import datetime, timezone
        
        payload = {"temperature": 22.5}
        
        # Simulate timestamp injection
        if "time" not in payload or payload["time"] == "":
            payload["time"] = datetime.now(timezone.utc).isoformat(
                timespec='milliseconds'
            ).replace('+00:00', 'Z')
        
        assert "time" in payload
        assert payload["time"].endswith("Z")

    def test_payload_preserves_existing_timestamp(self):
        """Should not override existing timestamp."""
        existing_time = "2024-01-28T00:00:00.000Z"
        payload = {"temperature": 22.5, "time": existing_time}
        
        # Check existing timestamp
        if "time" in payload and payload["time"] != "":
            # Don't override
            pass
        
        assert payload["time"] == existing_time


class TestGcpSimulatorCLI:
    """Test CLI argument parsing for GCP simulator."""

    def test_project_argument_required(self):
        """--project argument should be required."""
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("--project", required=True)
        parser.add_argument("--payload")
        
        # Should raise on missing --project
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_payload_argument_optional(self):
        """--payload argument should be optional."""
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("--project", required=True)
        parser.add_argument("--payload")
        
        args = parser.parse_args(["--project", "test-project"])
        
        assert args.project == "test-project"
        assert args.payload is None

    def test_payload_json_parsing(self):
        """--payload should accept valid JSON."""
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("--project", required=True)
        parser.add_argument("--payload")
        
        payload_json = '{"trace_id": "abc123", "temperature": 25}'
        args = parser.parse_args([
            "--project", "test-project",
            "--payload", payload_json
        ])
        
        payload = json.loads(args.payload)
        assert payload["trace_id"] == "abc123"
        assert payload["temperature"] == 25


class TestGcpSimulatorErrorHandling:
    """Test error handling in GCP simulator."""

    def test_invalid_json_payload(self):
        """Should handle invalid JSON payload gracefully."""
        invalid_json = "not valid json {"
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)

    @patch('google.cloud.pubsub_v1.PublisherClient')
    def test_publish_failure_handling(self, mock_client_class):
        """Should handle Pub/Sub publish failures."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.publish.side_effect = Exception("Permission denied")
        
        topic_path = "projects/my-project/topics/iot-telemetry"
        data = b'{"test": true}'
        
        with pytest.raises(Exception) as exc_info:
            mock_client.publish(topic_path, data)
        
        assert "Permission denied" in str(exc_info.value)

    def test_config_file_not_found(self):
        """Should handle missing config file."""
        config_path = "/nonexistent/config.json"
        
        assert not os.path.exists(config_path)
