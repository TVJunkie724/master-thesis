"""
Azure Functions Inter-Cloud Module Unit Tests.

Tests cover the shared inter_cloud.py module for Azure Functions:
- build_envelope() creates correct envelope structure
- validate_token() validates X-Inter-Cloud-Token header
- post_to_remote() handles retry logic
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import os
import sys
import importlib


@pytest.fixture(scope="function", autouse=True)
def azure_inter_cloud_path():
    """
    Fixture to add Azure functions path for imports and clean up after.
    This prevents polluting sys.path for other test files.
    """
    _azure_funcs_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "src", "providers", "azure", "azure_functions"
    ))
    
    # Add to path at start
    sys.path.insert(0, _azure_funcs_dir)
    
    # Clear any cached _shared modules to ensure fresh import
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]
    
    yield _azure_funcs_dir
    
    # Cleanup: remove from path and clear cached modules
    if _azure_funcs_dir in sys.path:
        sys.path.remove(_azure_funcs_dir)
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]


class TestBuildEnvelope:
    """Tests for build_envelope function."""

    def test_build_envelope_creates_correct_structure(self):
        """Envelope should have all required fields."""
        from _shared.inter_cloud import build_envelope
        
        payload = {"iotDeviceId": "device-1", "temperature": 25}
        envelope = build_envelope(payload, target_layer="L2")
        
        assert envelope["source_cloud"] == "azure"
        assert envelope["target_layer"] == "L2"
        assert envelope["message_type"] == "telemetry"
        assert "timestamp" in envelope
        assert "trace_id" in envelope
        assert envelope["payload"] == payload

    def test_build_envelope_uses_azure_source(self):
        """Azure version should default to source_cloud='azure'."""
        from _shared.inter_cloud import build_envelope
        
        envelope = build_envelope({}, target_layer="L3")
        assert envelope["source_cloud"] == "azure"

    def test_build_envelope_custom_message_type(self):
        """Should allow custom message_type."""
        from _shared.inter_cloud import build_envelope
        
        envelope = build_envelope({}, target_layer="L3_cold", message_type="chunk")
        assert envelope["message_type"] == "chunk"


class TestValidateToken:
    """Tests for validate_token function."""

    def test_validate_token_accepts_valid_lowercase(self):
        """Should accept valid token in lowercase header."""
        from _shared.inter_cloud import validate_token
        
        headers = {"x-inter-cloud-token": "secret-token"}
        assert validate_token(headers, "secret-token") is True

    def test_validate_token_accepts_valid_mixed_case(self):
        """Should accept valid token in mixed-case header."""
        from _shared.inter_cloud import validate_token
        
        headers = {"X-Inter-Cloud-Token": "secret-token"}
        assert validate_token(headers, "secret-token") is True

    def test_validate_token_rejects_invalid(self):
        """Should reject invalid token."""
        from _shared.inter_cloud import validate_token
        
        headers = {"x-inter-cloud-token": "wrong-token"}
        assert validate_token(headers, "correct-token") is False

    def test_validate_token_rejects_missing(self):
        """Should reject missing token."""
        from _shared.inter_cloud import validate_token
        
        headers = {}
        assert validate_token(headers, "secret-token") is False

    def test_validate_token_rejects_empty_expected(self):
        """Should reject when expected token is empty."""
        from _shared.inter_cloud import validate_token
        
        headers = {"x-inter-cloud-token": "some-token"}
        assert validate_token(headers, "") is False


class TestPostToRemote:
    """Tests for post_to_remote function."""

    @patch("urllib.request.urlopen")
    def test_post_to_remote_success(self, mock_urlopen):
        """Should return success on 200 response."""
        from _shared.inter_cloud import post_to_remote
        
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = post_to_remote(
            url="https://example.com/ingestion",
            token="test-token",
            payload={"data": "test"},
            target_layer="L2"
        )
        
        assert result["statusCode"] == 200
        assert "ok" in result["body"]

    def test_post_to_remote_raises_on_empty_url(self):
        """Should raise ValueError when URL is empty."""
        from _shared.inter_cloud import post_to_remote
        
        with pytest.raises(ValueError, match="Remote URL is required"):
            post_to_remote(url="", token="token", payload={}, target_layer="L2")

    def test_post_to_remote_raises_on_empty_token(self):
        """Should raise ValueError when token is empty."""
        from _shared.inter_cloud import post_to_remote
        
        with pytest.raises(ValueError, match="Inter-cloud token is required"):
            post_to_remote(url="https://example.com", token="", payload={}, target_layer="L2")

    @patch("urllib.request.urlopen")
    def test_post_to_remote_sends_auth_header(self, mock_urlopen):
        """Should send X-Inter-Cloud-Token header."""
        from _shared.inter_cloud import post_to_remote
        
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        post_to_remote(
            url="https://example.com/ingestion",
            token="secret-token-xyz",
            payload={"data": "test"},
            target_layer="L2"
        )
        
        # Get the request that was sent
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        
        assert request.get_header("X-inter-cloud-token") == "secret-token-xyz"

    @patch("urllib.request.urlopen")
    def test_post_to_remote_sends_envelope(self, mock_urlopen):
        """Should send payload wrapped in envelope."""
        from _shared.inter_cloud import post_to_remote
        
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        original_payload = {"iotDeviceId": "sensor-1", "temperature": 25}
        post_to_remote(
            url="https://example.com/ingestion",
            token="token",
            payload=original_payload,
            target_layer="L2"
        )
        
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        sent_data = json.loads(request.data.decode('utf-8'))
        
        # Verify envelope structure
        assert sent_data["source_cloud"] == "azure"
        assert sent_data["target_layer"] == "L2"
        assert sent_data["payload"] == original_payload


class TestBuildAuthErrorResponse:
    """Tests for build_auth_error_response function."""

    def test_build_auth_error_response_structure(self):
        """Should return 401 with error message."""
        from _shared.inter_cloud import build_auth_error_response
        
        response = build_auth_error_response()
        
        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
        assert "X-Inter-Cloud-Token" in body["message"]
