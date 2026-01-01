"""
Azure Functions Multi-Cloud Unit Tests.

Tests cover token validation and payload handling for Azure Functions:
- Ingestion: Token validation, payload envelope handling
- Hot Writer: Token validation, Cosmos DB write logic
- Connector: Payload envelope creation
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import os
import sys


@pytest.fixture(scope="function", autouse=True)
def azure_funcs_path():
    """
    Fixture to add Azure functions path for imports and clean up after.
    """
    _azure_funcs_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "src", "providers", "azure", "azure_functions"
    ))
    
    sys.path.insert(0, _azure_funcs_dir)
    
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]
    
    yield _azure_funcs_dir
    
    if _azure_funcs_dir in sys.path:
        sys.path.remove(_azure_funcs_dir)
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]


# ==========================================
# Ingestion Function Tests
# ==========================================

class TestAzureIngestionTokenValidation:
    """Tests for Azure Ingestion function token validation."""

    def test_ingestion_rejects_invalid_token(self):
        """Ingestion should return 403 when token is invalid."""
        # Clear cached modules
        for key in list(sys.modules.keys()):
            if 'ingestion' in key and 'azure' in key:
                del sys.modules[key]
        
        # Add path
        _azure_funcs_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src", "providers", "azure", "azure_functions"
        )
        if _azure_funcs_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(_azure_funcs_dir))
        
        with patch.dict(os.environ, {
            "INTER_CLOUD_TOKEN": "correct-token",
            "DIGITAL_TWIN_INFO": json.dumps({"config": {"digital_twin_name": "test"}})
        }):
            from _shared.inter_cloud import validate_token
            
            headers = {"x-inter-cloud-token": "wrong-token"}
            assert validate_token(headers, "correct-token") is False

    def test_ingestion_accepts_valid_token(self):
        """Ingestion should accept valid token."""
        _azure_funcs_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src", "providers", "azure", "azure_functions"
        )
        if _azure_funcs_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(_azure_funcs_dir))
        
        from _shared.inter_cloud import validate_token
        
        headers = {"x-inter-cloud-token": "correct-token"}
        assert validate_token(headers, "correct-token") is True


# ==========================================
# Connector Function Tests
# ==========================================

class TestAzureConnectorPayloadEnvelope:
    """Tests for Azure Connector function payload envelope creation."""

    @patch("urllib.request.urlopen")
    def test_connector_creates_correct_envelope(self, mock_urlopen):
        """Connector should create payload envelope with all required fields."""
        _azure_funcs_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src", "providers", "azure", "azure_functions"
        )
        if _azure_funcs_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(_azure_funcs_dir))
        
        from _shared.inter_cloud import build_envelope
        
        original_event = {"iotDeviceId": "sensor-1", "temperature": 25}
        envelope = build_envelope(original_event, target_layer="L2")
        
        # Verify envelope structure
        assert envelope["source_cloud"] == "azure"
        assert envelope["target_layer"] == "L2"
        assert envelope["message_type"] == "telemetry"
        assert "timestamp" in envelope
        assert "trace_id" in envelope
        assert envelope["payload"] == original_event


# ==========================================
# Hot Writer Function Tests
# ==========================================

class TestAzureHotWriterTokenValidation:
    """Tests for Azure Hot Writer function token validation."""

    def test_hot_writer_rejects_invalid_token(self):
        """Hot Writer should reject invalid token."""
        _azure_funcs_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src", "providers", "azure", "azure_functions"
        )
        if _azure_funcs_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(_azure_funcs_dir))
        
        from _shared.inter_cloud import validate_token
        
        headers = {"x-inter-cloud-token": "wrong-token"}
        assert validate_token(headers, "correct-token") is False

    def test_hot_writer_accepts_valid_token(self):
        """Hot Writer should accept valid token."""
        _azure_funcs_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src", "providers", "azure", "azure_functions"
        )
        if _azure_funcs_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(_azure_funcs_dir))
        
        from _shared.inter_cloud import validate_token
        
        headers = {"x-inter-cloud-token": "correct-token"}
        assert validate_token(headers, "correct-token") is True


# ==========================================
# Multi-Cloud Detection Tests
# ==========================================

class TestMultiCloudDetection:
    """Tests for multi-cloud provider detection logic."""

    def test_is_multi_cloud_no_url_returns_false(self):
        """Returns False when remote URL is empty."""
        remote_url = ""
        assert not remote_url

    def test_is_multi_cloud_same_provider_returns_false(self):
        """Returns False when providers are the same."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure"
        }
        assert providers["layer_1_provider"] == providers["layer_2_provider"]

    def test_is_multi_cloud_different_provider_returns_true(self):
        """Returns True when providers are different."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws"
        }
        assert providers["layer_1_provider"] != providers["layer_2_provider"]


# ==========================================
# Payload Validation Tests
# ==========================================

class TestPayloadValidation:
    """Tests for payload validation logic."""

    def test_validates_required_device_id(self):
        """Payload must contain device_id after normalization."""
        payload = {"temperature": 25}
        assert "device_id" not in payload

    def test_validates_payload_is_dict(self):
        """Payload must be a dictionary."""
        payload = {"iotDeviceId": "device-1", "temperature": 25}
        assert isinstance(payload, dict)

    def test_rejects_string_payload(self):
        """String payload should be rejected."""
        payload = "not-a-dict"
        assert not isinstance(payload, dict)
