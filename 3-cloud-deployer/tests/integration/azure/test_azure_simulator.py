"""
Unit tests for Azure IoT Device Simulator.

Tests cover:
- globals.py: Configuration loading
- transmission.py: Message sending via azure-iot-device SDK
"""
import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock, mock_open

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))


class TestAzureSimulatorGlobals:
    """Tests for Azure simulator globals.py configuration loading."""

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_initialize_config_standalone_mode(self, mock_file, mock_exists):
        """Test config loading in standalone mode (local config.json)."""
        from src.iot_device_simulator.azure import globals as azure_globals
        
        # Reset config
        azure_globals.config = {}
        
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps({
            "connection_string": "HostName=test.azure-devices.net;DeviceId=d1;SharedAccessKey=abc",
            "device_id": "d1",
            "digital_twin_name": "test-twin",
            "payload_path": "payloads.json"
        })
        
        azure_globals.initialize_config(project_name=None)
        
        assert azure_globals.config["connection_string"] == "HostName=test.azure-devices.net;DeviceId=d1;SharedAccessKey=abc"
        assert azure_globals.config["device_id"] == "d1"
        assert azure_globals.config["digital_twin_name"] == "test-twin"

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.getcwd')
    def test_initialize_config_integrated_mode(self, mock_cwd, mock_file, mock_exists):
        """Test config loading in integrated mode (--project flag)."""
        from src.iot_device_simulator.azure import globals as azure_globals
        
        # Reset config
        azure_globals.config = {}
        
        # First call (local config) returns False, second (project config) returns True
        mock_exists.side_effect = [False, True, True]  # local, project config, payload
        mock_cwd.return_value = "/app"
        mock_file.return_value.read.return_value = json.dumps({
            "connection_string": "HostName=hub.azure-devices.net;DeviceId=sensor-1;SharedAccessKey=xyz",
            "device_id": "sensor-1",
            "payload_path": "../payloads.json"
        })
        
        azure_globals.initialize_config(project_name="my-project")
        
        assert azure_globals.config["device_id"] == "sensor-1"
        assert "hub.azure-devices.net" in azure_globals.config["connection_string"]

    @patch('os.path.exists')
    def test_initialize_config_no_config_found_raises(self, mock_exists):
        """Test that ValueError is raised when no config source available."""
        from src.iot_device_simulator.azure import globals as azure_globals
        
        mock_exists.return_value = False
        
        with pytest.raises(ValueError, match="Configuration not found"):
            azure_globals.initialize_config(project_name=None)

    @patch('os.path.exists')
    def test_initialize_config_file_not_found_raises(self, mock_exists):
        """Test that FileNotFoundError is raised when config file missing."""
        from src.iot_device_simulator.azure import globals as azure_globals
        
        # Local config exists check: False, project path exists: False
        mock_exists.side_effect = [False, False]
        
        with pytest.raises(FileNotFoundError):
            azure_globals.initialize_config(project_name="missing-project")


class TestAzureSimulatorTransmission:
    """Tests for Azure simulator transmission.py message sending."""

    @patch('src.iot_device_simulator.azure.transmission._get_client')
    def test_send_mqtt_success(self, mock_get_client):
        """Test successful message send to IoT Hub."""
        from src.iot_device_simulator.azure import transmission, globals as azure_globals
        
        # Setup config
        azure_globals.config = {
            "connection_string": "HostName=test.azure-devices.net;DeviceId=d1;SharedAccessKey=abc",
            "device_id": "test-device",
            "payload_path": "/fake/payloads.json"
        }
        
        # Mock Message class (lazy imported)
        transmission.Message = MagicMock()
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        payload = {"iotDeviceId": "test-device", "temperature": 25.5}
        transmission.send_mqtt(payload)
        
        mock_client.connect.assert_called_once()
        mock_client.send_message.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @patch('src.iot_device_simulator.azure.transmission._get_client')
    def test_send_mqtt_device_id_mismatch_warns(self, mock_get_client, capsys):
        """Test warning when payload device ID doesn't match configured device."""
        from src.iot_device_simulator.azure import transmission, globals as azure_globals
        
        azure_globals.config = {
            "connection_string": "HostName=test.azure-devices.net;DeviceId=d1;SharedAccessKey=abc",
            "device_id": "correct-device",
            "payload_path": "/fake/payloads.json"
        }
        
        # Mock Message class (lazy imported)
        transmission.Message = MagicMock()
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Payload has different device ID
        payload = {"iotDeviceId": "wrong-device", "temperature": 25.5}
        transmission.send_mqtt(payload)
        
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "wrong-device" in captured.out

    @patch('builtins.open', new_callable=mock_open)
    @patch('src.iot_device_simulator.azure.transmission.send_mqtt')
    def test_send_cycles_through_payloads(self, mock_send_mqtt, mock_file):
        """Test that send() cycles through payloads sequentially."""
        from src.iot_device_simulator.azure import transmission, globals as azure_globals
        
        azure_globals.config = {
            "device_id": "d1",
            "payload_path": "/fake/payloads.json"
        }
        
        # Reset payload index
        transmission.payload_index = 0
        
        mock_file.return_value.read.return_value = json.dumps([
            {"iotDeviceId": "d1", "temp": 20},
            {"iotDeviceId": "d1", "temp": 21},
            {"iotDeviceId": "d1", "temp": 22}
        ])
        
        transmission.send()
        assert mock_send_mqtt.call_count == 1
        
        transmission.send()
        assert mock_send_mqtt.call_count == 2
        
        transmission.send()
        assert mock_send_mqtt.call_count == 3
        
        # Should cycle back to first payload
        transmission.send()
        assert mock_send_mqtt.call_count == 4
        assert transmission.payload_index == 1  # Wrapped around

    @patch('builtins.open', new_callable=mock_open)
    @patch('src.iot_device_simulator.azure.transmission.send_mqtt')
    def test_send_adds_timestamp_if_missing(self, mock_send_mqtt, mock_file):
        """Test that send() adds timestamp when missing from payload."""
        from src.iot_device_simulator.azure import transmission, globals as azure_globals
        
        azure_globals.config = {
            "device_id": "d1",
            "payload_path": "/fake/payloads.json"
        }
        
        transmission.payload_index = 0
        
        mock_file.return_value.read.return_value = json.dumps([
            {"iotDeviceId": "d1", "temp": 20}  # No 'time' field
        ])
        
        transmission.send()
        
        # Check the payload passed to send_mqtt has 'time' field
        called_payload = mock_send_mqtt.call_args[0][0]
        assert "time" in called_payload
        assert called_payload["time"].endswith("Z")  # ISO format with Z suffix


class TestAzureSimulatorMain:
    """Tests for Azure simulator main.py CLI entry point."""

    @patch('src.iot_device_simulator.azure.globals.initialize_config')
    def test_main_initializes_config_with_project(self, mock_init):
        """Test that main() passes project name to initialize_config."""
        from src.iot_device_simulator.azure import main as azure_main
        
        # We can't easily test the full REPL loop, but we can test initialization
        # by mocking argparse and checking initialize_config is called
        mock_init.side_effect = Exception("Stop after init")  # Stop execution
        
        with patch('sys.argv', ['main.py', '--project', 'test-project']):
            try:
                azure_main.main()
            except Exception:
                pass
        
        mock_init.assert_called_once_with(project_name='test-project')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
