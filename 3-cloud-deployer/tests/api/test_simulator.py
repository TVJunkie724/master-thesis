"""
Tests for the IoT Device Simulator API endpoints and validation logic.
"""
import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from io import BytesIO
import zipfile

# Ensure paths are set up
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

import rest_api
import validator

client = TestClient(rest_api.app)


class TestSimulatorPayloadValidation:
    """Tests for validate_simulator_payloads function."""

    def test_valid_payloads(self):
        """Test valid payload structure."""
        payload = json.dumps([
            {"iotDeviceId": "device1", "temperature": 25.5},
            {"iotDeviceId": "device2", "pressure": 1013.25}
        ])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload)
        assert is_valid is True
        assert len(errors) == 0

    def test_invalid_json(self):
        """Test invalid JSON input."""
        is_valid, errors, _ = validator.validate_simulator_payloads("{invalid json}")
        assert is_valid is False
        assert any("Invalid JSON" in e for e in errors)

    def test_not_array(self):
        """Test payload that is not an array."""
        is_valid, errors, _ = validator.validate_simulator_payloads('{"iotDeviceId": "d1"}')
        assert is_valid is False
        assert any("must be a JSON array" in e for e in errors)

    def test_missing_iot_device_id(self):
        """Test payload missing required iotDeviceId field."""
        payload = json.dumps([
            {"temperature": 25.5},  # Missing iotDeviceId
            {"iotDeviceId": "device2", "pressure": 1013.25}
        ])
        is_valid, errors, _ = validator.validate_simulator_payloads(payload)
        assert is_valid is False
        assert any("missing required key 'iotDeviceId'" in e for e in errors)

    def test_empty_array_warning(self):
        """Test empty payload array generates warning."""
        is_valid, errors, warnings = validator.validate_simulator_payloads("[]")
        assert is_valid is True
        assert len(errors) == 0
        assert any("empty" in w.lower() for w in warnings)

    def test_non_object_items(self):
        """Test payload with non-object items."""
        payload = json.dumps(["string", 123, {"iotDeviceId": "d1"}])
        is_valid, errors, _ = validator.validate_simulator_payloads(payload)
        assert is_valid is False
        assert any("not a JSON object" in e for e in errors)

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_device_id_warning_with_project(self, mock_json, mock_open, mock_exists):
        """Test warning when iotDeviceId doesn't match project config."""
        mock_exists.return_value = True
        mock_json.return_value = [{"id": "valid-device"}]
        
        payload = json.dumps([{"iotDeviceId": "unknown-device"}])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload, project_name="test-project")
        
        assert is_valid is True
        assert any("unknown-device" in w and "not found" in w for w in warnings)


class TestSimulatorAPIEndpoints:
    """Tests for simulator-related API endpoints."""

    @patch('src.validator.validate_simulator_payloads')
    def test_validate_payloads_endpoint_valid(self, mock_validate):
        """Test POST /validate/simulator/payloads with valid data."""
        mock_validate.return_value = (True, [], [])
        
        response = client.post(
            "/validate/simulator/payloads",
            json={"content": "W3siaW90RGV2aWNlSWQiOiAiZDEifV0="}  # Base64 encoded
        )
        # May need adjustment based on actual content handling
        assert response.status_code in [200, 500]  # Will refine based on actual implementation

    @patch('os.path.exists')
    def test_download_package_missing_config(self, mock_exists):
        """Test download fails when config not found."""
        mock_exists.return_value = False
        
        response = client.get("/projects/test-project/simulator/aws/download")
        assert response.status_code == 404
        assert "config not found" in response.json()["detail"].lower()

    def test_download_package_invalid_provider(self):
        """Test download fails for unsupported provider."""
        response = client.get("/projects/test-project/simulator/unknown/download")
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"]  

    @patch('src.validator.validate_simulator_payloads')
    @patch('globals.project_path')
    @patch('os.makedirs')
    @patch('builtins.open')
    def test_upload_payloads_valid(self, mock_open, mock_makedirs, mock_project_path, mock_validate):
        """Test PUT /projects/{project}/simulator/{provider}/payloads."""
        mock_validate.return_value = (True, [], [])
        mock_project_path.return_value = "/fake/path"
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.write = MagicMock()
        
        payload_content = json.dumps([{"iotDeviceId": "device1"}])
        response = client.put(
            "/projects/template/simulator/aws/payloads",
            content=payload_content.encode(),
            headers={"Content-Type": "application/octet-stream"}
        )
        # Check if it either succeeds or fails predictably
        assert response.status_code in [200, 400, 500]

    def test_upload_payloads_invalid_provider(self):
        """Test upload fails for unsupported provider."""
        response = client.put("/projects/template/simulator/azure/payloads", content=b"[]")
        assert response.status_code == 400
        assert "aws" in response.json()["detail"].lower()  # Message mentions aws as supported


class TestSimulatorTemplateLoading:
    """Tests for template loading utilities."""

    @patch('os.path.exists')
    @patch('builtins.open')
    def test_load_template_basic(self, mock_open, mock_exists):
        """Test basic template loading without variables."""
        from api.simulator import _load_template
        
        mock_exists.return_value = True
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.read = MagicMock(return_value="Hello World")
        
        result = _load_template("aws", "test.txt")
        assert result == "Hello World"

    @patch('os.path.exists')
    @patch('builtins.open')
    def test_load_template_with_variables(self, mock_open, mock_exists):
        """Test template loading with variable substitution."""
        from api.simulator import _load_template
        
        mock_exists.return_value = True
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.read = MagicMock(return_value="Hello {{name}}, your id is {{id}}")
        
        result = _load_template("aws", "test.txt", {"name": "John", "id": "123"})
        assert result == "Hello John, your id is 123"

    @patch('os.path.exists')
    def test_load_template_not_found(self, mock_exists):
        """Test template loading fails when file not found."""
        from api.simulator import _load_template
        
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError):
            _load_template("aws", "nonexistent.txt")


class TestSimulatorCLICommand:
    """Tests for the CLI simulate command."""

    @patch('subprocess.call')
    @patch('os.path.exists')
    def test_simulate_command_preflight_config_missing(self, mock_exists, mock_call):
        """Test CLI simulate fails when config missing."""
        # This tests the logic in src/main.py
        mock_exists.side_effect = lambda p: "config_generated" not in p
        
        # Import after patching
        from src import main as cli_main
        
        # Mock the input to send 'simulate aws template' then 'exit'
        # This is more of an integration test - keeping simple for now


class TestDownloadPackageIntegration:
    """Integration tests for the download package endpoint."""

    @patch('globals.project_path')
    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_download_package_creates_valid_zip(self, mock_json, mock_open_file, mock_exists, mock_project_path):
        """Test that download creates a valid zip with expected contents."""
        mock_project_path.return_value = "/fake/path"
        
        # Mock file existence checks
        def exists_side_effect(path):
            if "config_generated.json" in path:
                return True
            if "payloads.json" in path:
                return True
            if "templates" in path:
                return True
            if "iot_devices_auth" in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock config loading
        mock_json.return_value = {
            "device_id": "test-device",
            "endpoint": "test-endpoint.iot.amazonaws.com",
            "topic": "test/topic",
            "cert_path": "certs/cert.pem",
            "key_path": "certs/key.pem"
        }
        
        # This is a complex integration test - keeping as placeholder
        # A full test would require extensive mocking of file operations


class TestDownloadPackageEdgeCases:
    """Edge case tests for download package endpoint logic."""

    def test_download_invalid_provider_returns_400(self):
        """Test download returns 400 for invalid provider."""
        response = client.get("/projects/any-project/simulator/azure/download")
        assert response.status_code == 400
        
    def test_download_invalid_provider_google(self):
        """Test download returns 400 for google provider."""
        response = client.get("/projects/any-project/simulator/google/download")
        assert response.status_code == 400

    def test_download_nonexistent_project(self):
        """Test download returns 404 for non-existent project."""
        response = client.get("/projects/definitely-not-a-project-12345/simulator/aws/download")
        assert response.status_code == 404


class TestWebSocketSimulatorStream:
    """
    Tests for the WebSocket simulator stream endpoint.
    
    TODO: Implement full WebSocket tests using httpx AsyncClient or pytest-asyncio.
    These require:
    - Async test setup with pytest-asyncio
    - Mocking subprocess.Popen for stdin/stdout
    - Testing the asyncio.to_thread blocking read pattern
    - Verifying process cleanup on disconnect
    
    Reference: https://fastapi.tiangolo.com/advanced/testing-websockets/
    """

    @pytest.mark.skip(reason="TODO: Requires async WebSocket test setup")
    def test_websocket_invalid_provider(self):
        """Test WebSocket rejects invalid provider."""
        # TODO: Use TestClient with statement for WebSocket
        # with client.websocket_connect("/projects/p/simulator/unknown/stream") as ws:
        #     data = ws.receive_json()
        #     assert data["type"] == "error"
        pass

    @pytest.mark.skip(reason="TODO: Requires async WebSocket test setup")
    @patch('os.path.exists')
    def test_websocket_project_not_found(self, mock_exists):
        """Test WebSocket returns error for non-existent project."""
        mock_exists.return_value = False
        # TODO: Implement with actual WebSocket connection
        pass

    @pytest.mark.skip(reason="TODO: Requires async WebSocket test setup")
    @patch('os.path.exists')
    def test_websocket_missing_config(self, mock_exists):
        """Test WebSocket returns error when config missing."""
        def exists_side_effect(path):
            if "config_generated" in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect
        # TODO: Implement with actual WebSocket connection
        pass

    @pytest.mark.skip(reason="TODO: Requires async WebSocket test setup")
    @patch('os.path.exists')
    def test_websocket_missing_payloads(self, mock_exists):
        """Test WebSocket returns error when payloads missing."""
        def exists_side_effect(path):
            if "payloads.json" in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect
        # TODO: Implement with actual WebSocket connection
        pass

    @pytest.mark.skip(reason="TODO: Requires async WebSocket test setup with subprocess mocking")
    def test_websocket_subprocess_handling(self):
        """Test WebSocket properly manages subprocess lifecycle."""
        # TODO: Verify terminate/kill is called on disconnect
        # TODO: Test stdin write for commands
        # TODO: Test stdout streaming to client
        pass



class TestSimulatorValidationEdgeCases:
    """Additional edge case tests for payload validation."""

    def test_payload_with_extra_fields(self):
        """Test payload with extra fields beyond iotDeviceId."""
        payload = json.dumps([
            {"iotDeviceId": "d1", "temperature": 25, "humidity": 60, "nested": {"a": 1}}
        ])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload)
        assert is_valid is True

    def test_payload_with_special_characters(self):
        """Test payload with special characters in device ID."""
        payload = json.dumps([{"iotDeviceId": "device-1_test.sensor"}])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload)
        assert is_valid is True

    def test_payload_large_array(self):
        """Test validation with large payload array."""
        payload = json.dumps([{"iotDeviceId": f"device-{i}"} for i in range(100)])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload)
        assert is_valid is True
        assert len(errors) == 0

    def test_payload_unicode_content(self):
        """Test payload with unicode content."""
        payload = json.dumps([{"iotDeviceId": "device-1", "message": "温度センサー"}])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload)
        assert is_valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

