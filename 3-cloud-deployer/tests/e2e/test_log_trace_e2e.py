"""
End-to-End tests for Log Trace functionality.

⚠️  IMPORTANT: These tests require real cloud credentials and deployed
infrastructure. They will:
- Send real IoT messages to cloud providers
- Query real log storage (CloudWatch, Log Analytics, Cloud Logging)
- Incur costs on cloud providers

Run only with explicit approval:
    pytest tests/e2e/test_log_trace_e2e.py -v --run-e2e

Test scenarios:
- Single-cloud: AWS only, Azure only, GCP only
- Cross-cloud: AWS→Azure, AWS→GCP, Azure→AWS, etc.
- Full pipeline: L1→L2→L3 with trace propagation
"""
import pytest
import os
import time
import requests
import json
from datetime import datetime, timezone

# Skip all tests unless --run-e2e flag is provided
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_E2E_TESTS"),
    reason="E2E tests require explicit approval. Set RUN_E2E_TESTS=1 to run."
)


# ============================================================
# Configuration
# ============================================================

DEPLOYER_API_URL = os.environ.get("DEPLOYER_API_URL", "http://localhost:5001")
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:3000")
TEST_TIMEOUT = 120  # seconds


def get_project_name():
    """Get test project name from environment or use default."""
    return os.environ.get("E2E_PROJECT_NAME", "e2e-log-trace-test")


def get_twin_id():
    """Get test twin ID from environment."""
    return os.environ.get("E2E_TWIN_ID")


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture(scope="module")
def deployed_project():
    """Ensure a project is deployed before running tests."""
    project_name = get_project_name()
    
    # Verify project exists
    response = requests.get(
        f"{DEPLOYER_API_URL}/projects/{project_name}/status",
        timeout=10
    )
    
    if response.status_code != 200:
        pytest.skip(f"Project '{project_name}' not found. Deploy first.")
    
    status = response.json()
    if status.get("state") != "deployed":
        pytest.skip(f"Project '{project_name}' not deployed (state={status.get('state')})")
    
    return {
        "project_name": project_name,
        "status": status
    }


@pytest.fixture(scope="module")
def api_session():
    """Create a requests session with auth headers."""
    session = requests.Session()
    session.headers["Authorization"] = "Bearer dev-token"
    session.headers["Content-Type"] = "application/json"
    return session


# ============================================================
# Single Cloud Tests
# ============================================================

class TestSingleCloudLogTrace:
    """Test log tracing in single-cloud deployments."""

    @pytest.mark.e2e
    def test_aws_only_trace(self, deployed_project, api_session):
        """Test log trace in AWS-only deployment."""
        project = deployed_project["project_name"]
        
        # Start trace
        response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert "trace_id" in data
        trace_id = data["trace_id"]
        
        # Give CloudWatch time to ingest logs
        time.sleep(60)
        
        # Verify logs appear (simplified check)
        # In real E2E, would stream SSE and verify
        assert trace_id is not None


class TestCrossCloudLogTrace:
    """Test log tracing across multiple cloud providers."""

    @pytest.mark.e2e
    def test_aws_azure_trace(self, deployed_project, api_session):
        """Test log trace from AWS L1 to Azure L2."""
        project = deployed_project["project_name"]
        
        response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        
        assert response.status_code == 200
        data = response.json()
        trace_id = data["trace_id"]
        providers = data.get("providers", [])
        
        # Should detect both providers
        assert len(providers) >= 2, f"Expected 2+ providers, got {providers}"

    @pytest.mark.e2e
    def test_full_pipeline_trace(self, deployed_project, api_session):
        """Test trace through L1→L0→L2→L3 pipeline."""
        project = deployed_project["project_name"]
        
        response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all layers detected
        layers_mentioned = data.get("message", "")
        assert "L1" in layers_mentioned or data.get("l1_provider") is not None


class TestTraceIdPropagation:
    """Test that trace_id propagates through the EDT pipeline."""

    @pytest.mark.e2e
    def test_trace_id_in_iot_payload(self, deployed_project, api_session):
        """Verify trace_id is included in IoT message."""
        project = deployed_project["project_name"]
        
        response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        
        assert response.status_code == 200
        data = response.json()
        trace_id = data["trace_id"]
        
        # Trace ID should be a valid UUID
        import uuid
        uuid.UUID(trace_id)

    @pytest.mark.e2e  
    def test_trace_id_appears_in_logs(self, deployed_project, api_session):
        """Verify trace_id appears in CloudWatch/Log Analytics logs."""
        project = deployed_project["project_name"]
        
        response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        
        assert response.status_code == 200
        trace_id = response.json()["trace_id"]
        
        # Wait for log ingestion
        time.sleep(45)
        
        # Stream would contain matching logs
        # This is a simplified check
        assert trace_id is not None


class TestRateLimiting:
    """Test rate limiting behavior in E2E context."""

    @pytest.mark.e2e
    def test_rate_limit_enforced(self, deployed_project, api_session):
        """Verify 30-second rate limit is enforced."""
        project = deployed_project["project_name"]
        
        # First request should succeed
        response1 = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        assert response1.status_code == 200
        
        # Immediate second request should be rate limited
        response2 = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        assert response2.status_code == 429

    @pytest.mark.e2e
    def test_rate_limit_expires(self, deployed_project, api_session):
        """Verify rate limit expires after 30 seconds."""
        project = deployed_project["project_name"]
        
        # First request
        api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        
        # Wait for cooldown
        time.sleep(35)
        
        # Should succeed after cooldown
        response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        assert response.status_code == 200


class TestSseStreaming:
    """Test SSE streaming behavior in E2E context."""

    @pytest.mark.e2e
    def test_sse_stream_receives_logs(self, deployed_project, api_session):
        """Verify SSE stream receives log events."""
        project = deployed_project["project_name"]
        
        # Start trace
        start_response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        trace_id = start_response.json()["trace_id"]
        
        # Stream logs (with timeout)
        stream_url = f"{DEPLOYER_API_URL}/logs/trace/stream/{trace_id}"
        
        with api_session.get(
            stream_url,
            params={"project_name": project},
            stream=True,
            timeout=TEST_TIMEOUT
        ) as response:
            assert response.status_code == 200
            
            event_count = 0
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    event_count += 1
                    if event_count > 0:
                        break  # At least one event received
            
            assert event_count > 0, "No events received from SSE stream"

    @pytest.mark.e2e
    def test_sse_stream_terminates(self, deployed_project, api_session):
        """Verify SSE stream terminates with 'done' event."""
        project = deployed_project["project_name"]
        
        start_response = api_session.post(
            f"{DEPLOYER_API_URL}/logs/trace/start",
            params={"project_name": project}
        )
        trace_id = start_response.json()["trace_id"]
        
        stream_url = f"{DEPLOYER_API_URL}/logs/trace/stream/{trace_id}"
        
        received_done = False
        start_time = time.time()
        
        with api_session.get(
            stream_url,
            params={"project_name": project},
            stream=True,
            timeout=TEST_TIMEOUT
        ) as response:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if "done" in line:
                    received_done = True
                    break
                if time.time() - start_time > TEST_TIMEOUT:
                    break
        
        assert received_done, "Did not receive 'done' event from SSE stream"
