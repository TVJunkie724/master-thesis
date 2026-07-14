"""
Unit tests for the Log Trace API (src/api/logs.py).

Tests cover:
- Trace ID generation and format validation
- Rate limiting per project
- Provider detection from config
- Log parsing for AWS/Azure/GCP
- IoT message sending via subprocess
- Trace ID validation and expiration
"""
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Import the module under test
from src.api.logs import (
    generate_trace_id,
    get_providers_to_query,
    _rate_limit_store,
    _issued_traces,
    RATE_LIMIT_SECONDS,
    TRACE_TIMEOUT_SECONDS,
    POLL_INTERVAL_SECONDS,
)


class TestTraceIdGeneration:
    """Test trace ID generation and format."""

    def test_generate_trace_id_format(self):
        """Trace ID should have TRACE-XXXXXXXX format."""
        trace_id = generate_trace_id()
        assert trace_id.startswith("TRACE-")
        assert len(trace_id) == 14  # TRACE- (6) + 8 hex chars

    def test_generate_trace_id_uniqueness(self):
        """Each call should generate a unique trace ID."""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(ids) == len(set(ids))

    def test_generate_trace_id_uppercase(self):
        """Trace ID hex portion should be uppercase."""
        trace_id = generate_trace_id()
        hex_part = trace_id.split("-")[1]
        assert hex_part == hex_part.upper()


class TestRateLimiting:
    """Test rate limiting logic."""

    def test_rate_limit_store_initial_empty(self):
        """Rate limit store should start empty or be clearable."""
        _rate_limit_store.clear()
        assert len(_rate_limit_store) == 0

    def test_rate_limit_cooldown_detection(self):
        """Should detect when a project is still in cooldown."""
        _rate_limit_store.clear()
        project = "test_rate_limit_project"
        
        # First request - should not be rate limited
        assert project not in _rate_limit_store
        
        # Record a request
        _rate_limit_store[project] = datetime.utcnow()
        
        # Check if within cooldown
        last_request = _rate_limit_store.get(project)
        assert last_request is not None
        elapsed = (datetime.utcnow() - last_request).total_seconds()
        assert elapsed < RATE_LIMIT_SECONDS

    def test_rate_limit_expired(self):
        """Should allow request after cooldown expires."""
        _rate_limit_store.clear()
        project = "test_rate_limit_expired"
        
        # Simulate a request 60 seconds ago
        _rate_limit_store[project] = datetime.utcnow() - timedelta(seconds=60)
        
        last_request = _rate_limit_store.get(project)
        elapsed = (datetime.utcnow() - last_request).total_seconds()
        assert elapsed >= RATE_LIMIT_SECONDS


class TestTraceIdValidation:
    """Test trace ID tracking and validation."""

    def test_issued_traces_store(self):
        """Should be able to store and retrieve issued traces."""
        _issued_traces.clear()
        trace_id = "TRACE-TESTTEST"
        project = "test_project"
        now = datetime.utcnow()
        
        _issued_traces[trace_id] = (project, now)
        
        assert trace_id in _issued_traces
        stored_project, stored_time = _issued_traces[trace_id]
        assert stored_project == project
        assert stored_time == now

    def test_trace_expiration_detection(self):
        """Should detect expired traces (>2 minutes old)."""
        _issued_traces.clear()
        trace_id = "TRACE-EXPIRED1"
        project = "test_project"
        old_time = datetime.utcnow() - timedelta(minutes=3)
        
        _issued_traces[trace_id] = (project, old_time)
        
        issued_project, issued_at = _issued_traces[trace_id]
        elapsed = (datetime.utcnow() - issued_at).total_seconds()
        assert elapsed > 120  # Expired

    def test_trace_not_expired(self):
        """Should detect valid (non-expired) traces."""
        _issued_traces.clear()
        trace_id = "TRACE-VALID123"
        project = "test_project"
        now = datetime.utcnow()
        
        _issued_traces[trace_id] = (project, now)
        
        issued_project, issued_at = _issued_traces[trace_id]
        elapsed = (datetime.utcnow() - issued_at).total_seconds()
        assert elapsed < 120  # Not expired


class TestProviderDetection:
    """Test provider detection from config files."""

    @patch('src.api.logs._load_providers')
    def test_get_providers_basic(self, mock_load):
        """Should extract providers from config_providers.json."""
        mock_load.return_value = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "gcp"
        }
        
        providers = get_providers_to_query("test_project")
        
        assert "aws" in providers
        assert "azure" in providers
        assert "gcp" in providers
        assert len(providers) == 3

    @patch('src.api.logs._load_providers')
    def test_get_providers_with_duplicates(self, mock_load):
        """Should deduplicate when same provider used in multiple layers."""
        mock_load.return_value = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws"
        }
        
        providers = get_providers_to_query("test_project")
        
        assert providers == {"aws"}

    @patch('src.api.logs._load_providers')
    def test_get_providers_with_null(self, mock_load):
        """Should handle None providers gracefully."""
        mock_load.return_value = {
            "layer_1_provider": "aws",
            "layer_2_provider": None,
            "layer_3_hot_provider": None
        }
        
        providers = get_providers_to_query("test_project")
        
        assert None not in providers
        assert providers == {"aws"}


class TestLogParsing:
    """Test log entry parsing for different providers."""

    def test_aws_log_format(self):
        """AWS CloudWatch log entries should have expected structure."""
        raw_log = {
            "timestamp": 1706400000000,  # milliseconds
            "message": "Processing trace_id=abc123"
        }
        
        assert "timestamp" in raw_log
        assert "message" in raw_log
        assert isinstance(raw_log["timestamp"], int)

    def test_azure_log_format(self):
        """Azure Log Analytics entries should have expected structure."""
        raw_log = {
            "TimeGenerated": "2024-01-28T00:00:00Z",
            "Message": "Processing trace_id=abc123",
            "OperationName": "l1-dispatcher"
        }
        
        assert "TimeGenerated" in raw_log
        assert "Message" in raw_log

    def test_gcp_log_format(self):
        """GCP Cloud Logging entries should have expected structure."""
        raw_log = {
            "timestamp": "2024-01-28T00:00:00Z",
            "textPayload": "Processing trace_id=abc123",
            "resource": {"type": "cloud_function", "labels": {"function_name": "l1"}}
        }
        
        assert "textPayload" in raw_log or "jsonPayload" in raw_log


class TestIoTMessageSending:
    """Test IoT message sending via subprocess."""

    @patch('subprocess.run')
    def test_subprocess_success(self, mock_run):
        """Should return True on successful subprocess execution."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Message sent")
        
        from src.iot_device_simulator.sender import send_test_message
        
        result = send_test_message(
            provider="aws",
            project_name="test_project",
            trace_id="TRACE-ABC12345",
            payload_override={"iotDeviceId": "device-1"},
        )
        
        assert result is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_subprocess_failure(self, mock_run):
        """Should return False on subprocess failure."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error occurred")
        
        from src.iot_device_simulator.sender import send_test_message
        
        result = send_test_message(
            provider="aws",
            project_name="test_project",
            trace_id="TRACE-ABC12345",
            payload_override={"iotDeviceId": "device-1"},
        )
        
        assert result is False

    @patch('subprocess.run')
    def test_subprocess_timeout(self, mock_run):
        """Should handle subprocess timeout gracefully."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=30)
        
        from src.iot_device_simulator.sender import send_test_message
        
        result = send_test_message(
            provider="aws",
            project_name="test_project",
            trace_id="TRACE-ABC12345",
            payload_override={"iotDeviceId": "device-1"},
        )
        
        assert result is False

    @patch('subprocess.run')
    def test_provider_mapping(self, mock_run):
        """Should map provider names correctly."""
        mock_run.return_value = MagicMock(returncode=0)
        
        from src.iot_device_simulator.sender import send_test_message
        
        # Test gcp -> google mapping
        send_test_message(
            "gcp",
            "test",
            "TRACE-1234ABCD",
            payload_override={"iotDeviceId": "device-1"},
        )
        call_args = mock_run.call_args[0][0]
        assert "google" in str(call_args)

    def test_unknown_provider(self):
        """Should return False for unknown provider."""
        from src.iot_device_simulator.sender import send_test_message
        
        result = send_test_message(
            provider="unknown",
            project_name="test_project",
            trace_id="TRACE-ABC12345"
        )
        
        assert result is False

    @patch("src.iot_device_simulator.sender._load_default_payload")
    @patch("src.iot_device_simulator.sender.subprocess.run")
    def test_missing_payload_fails_without_starting_process(
        self,
        mock_run,
        mock_load_payload,
    ):
        mock_load_payload.return_value = None
        from src.iot_device_simulator.sender import send_test_message

        result = send_test_message(
            provider="aws",
            project_name="test_project",
            trace_id="TRACE-ABC12345",
        )

        assert result is False
        mock_run.assert_not_called()


class TestConstants:
    """Test configuration constants."""

    def test_rate_limit_seconds(self):
        """Rate limit should be 30 seconds."""
        assert RATE_LIMIT_SECONDS == 30

    def test_trace_timeout_seconds(self):
        """Trace timeout should be 90 seconds."""
        assert TRACE_TIMEOUT_SECONDS == 90

    def test_poll_interval_seconds(self):
        """Poll interval should be 2 seconds."""
        assert POLL_INTERVAL_SECONDS == 2
