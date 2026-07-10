"""Tests for test-only endpoint quarantine."""

import pytest

from src.config import settings
from src.api.routes import test_endpoints
from src.main import app
from src.models.user import User


def test_test_endpoints_are_not_registered_by_default(authenticated_client):
    client, headers = authenticated_client

    assert settings.ENABLE_TEST_ENDPOINTS is False
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/twins/{twin_id}/test-deploy" not in route_paths
    assert "/twins/{twin_id}/test-destroy" not in route_paths
    assert "/twins/{twin_id}/test-log-trace/start" not in route_paths
    assert "/twins/{twin_id}/simulator/test-download" not in route_paths

    response = client.post("/twins/not-a-real-twin/test-deploy", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_test_deploy_endpoint_delegates_to_orchestrator(monkeypatch, db):
    calls = []
    user = User(email="test-endpoint-orchestrator@example.test", name="Test Endpoint", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)

    class FakeOrchestrator:
        async def deploy_twin(self, **kwargs):
            calls.append(kwargs)
            return {"session_id": "test-deploy-session", "sse_url": "/sse/deploy/test-deploy-session"}

    monkeypatch.setattr(test_endpoints, "TEST_ENDPOINTS_ENABLED", True)
    monkeypatch.setattr(test_endpoints, "_deployment_orchestrator", lambda _db: FakeOrchestrator())

    result = await test_endpoints.test_deploy_twin(
        twin_id="twin-1",
        duration=7,
        should_fail=True,
        db=db,
        current_user=user,
    )

    assert result["session_id"] == "test-deploy-session"
    assert calls[0]["twin_id"] == "twin-1"
    assert calls[0]["user_id"] == user.id
    assert calls[0]["test_mode"] is True
    assert calls[0]["skip_state_validation"] is True
    assert callable(calls[0]["test_stream_runner"])


@pytest.mark.asyncio
async def test_test_destroy_endpoint_delegates_to_orchestrator(monkeypatch, db):
    calls = []
    user = User(email="test-destroy-orchestrator@example.test", name="Test Destroy", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)

    class FakeOrchestrator:
        async def destroy_twin(self, **kwargs):
            calls.append(kwargs)
            return {"session_id": "test-destroy-session", "sse_url": "/sse/deploy/test-destroy-session"}

    monkeypatch.setattr(test_endpoints, "TEST_ENDPOINTS_ENABLED", True)
    monkeypatch.setattr(test_endpoints, "_deployment_orchestrator", lambda _db: FakeOrchestrator())

    result = await test_endpoints.test_destroy_twin(
        twin_id="twin-1",
        duration=6,
        should_fail=False,
        db=db,
        current_user=user,
    )

    assert result["session_id"] == "test-destroy-session"
    assert calls[0]["twin_id"] == "twin-1"
    assert calls[0]["user_id"] == user.id
    assert calls[0]["test_mode"] is True
    assert calls[0]["skip_state_validation"] is True
    assert callable(calls[0]["test_stream_runner"])
