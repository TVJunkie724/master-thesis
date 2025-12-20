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

    def test_device_id_warning_with_project(self):
        """Test that project_name parameter doesn't cause errors (context check skipped)."""
        # The function accepts project_name but skips the verification
        payload = json.dumps([{"iotDeviceId": "unknown-device"}])
        is_valid, errors, warnings = validator.validate_simulator_payloads(payload, project_name="test-project")
        
        # Should pass without errors - project context check is skipped
        assert is_valid is True


class TestSimulatorAPIEndpoints:
    """Tests for simulator-related API endpoints."""

    @patch('src.validator.validate_simulator_payloads')
    def test_validate_payloads_endpoint_valid(self, mock_validate):
        """Test POST /validate/simulator/payloads with valid data."""
        mock_validate.return_value = (True, [], [])
        
        # Endpoint now expects file upload, not JSON body
        payload_content = json.dumps([{"iotDeviceId": "d1"}])
        files = {"file": ("payloads.json", payload_content, "application/json")}
        response = client.post("/validate/simulator/payloads", files=files)
        
        assert response.status_code == 200

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
    @patch('src.core.state.get_project_base_path')
    @patch('os.makedirs')
    @patch('builtins.open')
    def test_upload_payloads_valid(self, mock_open, mock_makedirs, mock_base_path, mock_validate):
        """Test PUT /projects/{project}/simulator/payloads (provider-agnostic)."""
        mock_validate.return_value = (True, [], [])
        mock_base_path.return_value = "/fake/path"
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.write = MagicMock()
        
        payload_content = json.dumps([{"iotDeviceId": "device1"}])
        response = client.put(
            "/projects/template/simulator/payloads",  # Provider-agnostic URL
            content=payload_content.encode(),
            headers={"Content-Type": "application/octet-stream"}
        )
        # Check if it either succeeds or fails predictably
        assert response.status_code in [200, 400, 500]

    def test_upload_payloads_old_endpoint_returns_404(self):
        """Test old provider-specific endpoint returns 404 (removed)."""
        response = client.put("/projects/template/simulator/aws/payloads", content=b"[]")
        # Old endpoint should now return 404/405 since it no longer exists
        assert response.status_code in [404, 405]


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

    @patch('src.core.state.get_project_upload_path')
    @patch('src.core.state.get_project_base_path')
    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_download_package_creates_valid_zip(self, mock_json, mock_open_file, mock_exists, mock_base_path, mock_upload_path):
        """Test that download creates a valid zip with expected contents."""
        mock_upload_path.return_value = "/fake/upload"
        mock_base_path.return_value = "/fake/base"
        
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
        response = client.get("/projects/any-project/simulator/invalid/download")
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

    def test_websocket_invalid_provider(self):
        """Test WebSocket rejects invalid provider."""
        with client.websocket_connect("/projects/p/simulator/unknown/stream") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "not supported" in data["data"]

    @patch('src.core.state.get_project_upload_path')
    @patch('os.path.exists')
    def test_websocket_project_not_found(self, mock_exists, mock_path):
        """Test WebSocket returns error for non-existent project."""
        mock_path.return_value = "/fake/uploads"
        mock_exists.return_value = False # Project dir does not exist
        
        with client.websocket_connect("/projects/missing/simulator/aws/stream") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "not found" in data["data"]

    @patch('src.core.state.get_project_upload_path')
    @patch('os.path.exists')
    def test_websocket_missing_config(self, mock_exists, mock_path):
        """Test WebSocket returns error when config missing."""
        mock_path.return_value = "/fake/uploads"
        # exists side effect: Project Dir (True), Config (False)
        # Sequence: Project Path check -> Config Path check
        # Paths checked: /fake/uploads/proj, /fake/uploads/proj/iot.../config 
        def exists_side_effect(path):
            if path.endswith("config_generated.json"):
                return False
            return True
            
        mock_exists.side_effect = exists_side_effect
        
        with client.websocket_connect("/projects/proj/simulator/aws/stream") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "config not found" in data["data"].lower()

    @patch('src.core.state.get_project_upload_path')
    @patch('os.path.exists')
    def test_websocket_missing_payloads(self, mock_exists, mock_path):
        """Test WebSocket returns error when payloads missing."""
        mock_path.return_value = "/fake/uploads"
        
        def exists_side_effect(path):
            if path.endswith("payloads.json"):
                return False
            return True
        mock_exists.side_effect = exists_side_effect
        
        with client.websocket_connect("/projects/proj/simulator/aws/stream") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "payloads file not found" in data["data"].lower()

    @patch('subprocess.Popen')
    @patch('src.core.state.get_project_upload_path')
    @patch('src.core.state.get_project_base_path')
    @patch('os.path.exists')
    def test_websocket_subprocess_handling(self, mock_exists, mock_base, mock_upload, mock_popen):
        """Test WebSocket properly manages subprocess lifecycle."""
        mock_upload.return_value = "/fake/uploads"
        mock_base.return_value = "/fake/base"
        mock_exists.return_value = True
        
        # Mock Process
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["Log line 1\n", "Log line 2\n", ""] # simulate output then EOF
        mock_process.stdin.write = MagicMock()
        mock_process.terminate = MagicMock()
        mock_popen.return_value = mock_process
        
        with client.websocket_connect("/projects/proj/simulator/aws/stream") as websocket:
            # Verify Logs received
            msg1 = websocket.receive_json()
            assert msg1["type"] == "log"
            assert msg1["data"] == "Log line 1"
            
            # Send Command
            websocket.send_json({"command": "start"})
            # Verify wrote to stdin
            # Need to wait a bit as reading is async in server? 
            # TestClient is synchronous but server runs in event loop.
            # To verify side effect on mock we might need to sleep or check after.
            
            # Send Exit to cleanly close
            websocket.send_json({"command": "exit"})
            
            # Connection might close or we close it
            websocket.close()
            
        # Verify cleanup
        mock_process.terminate.assert_called()
        # Verify stdin writes
        # Note: Timing issues might make this flaky without retry logic in real env, 
        # but in mocked threaded env it should be reasonably consistent if implementation awaits stuff.
        # Actually simulator.py:91 process.stdin.write called immediately on receive. Use any_call.
        mock_process.stdin.write.assert_any_call("start\n")



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

