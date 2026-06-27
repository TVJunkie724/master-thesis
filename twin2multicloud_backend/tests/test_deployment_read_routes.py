"""Route regression tests for deployment read endpoints."""

import io
from datetime import datetime, timedelta

from src.models.deployment import Deployment
from src.models.twin import TwinState
from src.services.simulator_service import SimulatorDownload


def test_deployment_status_route_returns_current_twin_state(auth_client, test_twin):
    response = auth_client.get(f"/twins/{test_twin.id}/deployment-status")

    assert response.status_code == 200
    assert response.json()["state"] == TwinState.DRAFT.value
    assert response.json()["active_session"] is None


def test_outputs_route_returns_empty_payload_without_successful_deployment(auth_client, test_twin):
    response = auth_client.get(f"/twins/{test_twin.id}/outputs")

    assert response.status_code == 200
    assert response.json() == {"outputs": None, "deployed_at": None}


def test_outputs_route_returns_latest_successful_deployment(auth_client, db, test_twin):
    older = Deployment(
        twin_id=test_twin.id,
        session_id="route-older",
        operation_type="deploy",
        status="success",
        completed_at=datetime.utcnow() - timedelta(minutes=5),
        terraform_outputs={"endpoint": "old"},
    )
    newer = Deployment(
        twin_id=test_twin.id,
        session_id="route-newer",
        operation_type="test",
        status="success",
        completed_at=datetime.utcnow(),
        terraform_outputs={"endpoint": "new"},
    )
    db.add_all([older, newer])
    db.commit()

    response = auth_client.get(f"/twins/{test_twin.id}/outputs")

    assert response.status_code == 200
    assert response.json()["outputs"] == {"endpoint": "new"}


def test_deployments_route_returns_limited_history(auth_client, db, test_twin):
    first = Deployment(
        twin_id=test_twin.id,
        session_id="route-first",
        operation_type="deploy",
        status="success",
        started_at=datetime.utcnow() - timedelta(minutes=2),
    )
    second = Deployment(
        twin_id=test_twin.id,
        session_id="route-second",
        operation_type="destroy",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add_all([first, second])
    db.commit()

    response = auth_client.get(f"/twins/{test_twin.id}/deployments?limit=1")

    assert response.status_code == 200
    assert [item["session_id"] for item in response.json()["deployments"]] == ["route-second"]


def test_deployment_command_route_delegates_to_orchestrator(auth_client, test_twin, monkeypatch):
    calls = []

    class FakeOrchestrator:
        async def deploy_twin(self, **kwargs):
            calls.append(kwargs)
            return {"session_id": "route-deploy", "sse_url": "/sse/deploy/route-deploy"}

    monkeypatch.setattr(
        "src.api.routes.twins._deployment_orchestrator",
        lambda _db: FakeOrchestrator(),
    )

    response = auth_client.post(f"/twins/{test_twin.id}/deploy")

    assert response.status_code == 200
    assert response.json()["session_id"] == "route-deploy"
    assert calls[0]["twin_id"] == test_twin.id
    assert calls[0]["test_mode"] is False
    assert "test_stream_runner" not in calls[0]


def test_deployment_verification_route_delegates_to_orchestrator(auth_client, test_twin, monkeypatch):
    calls = []

    class FakeOrchestrator:
        async def verify_infrastructure(self, **kwargs):
            calls.append(kwargs)
            return {"summary": {"healthy": True}, "checks": []}

    monkeypatch.setattr(
        "src.api.routes.twins._deployment_orchestrator",
        lambda _db: FakeOrchestrator(),
    )

    response = auth_client.post(f"/twins/{test_twin.id}/verify/infrastructure")

    assert response.status_code == 200
    assert response.json()["summary"]["healthy"] is True
    assert calls == [{"twin_id": test_twin.id, "user_id": test_twin.user_id, "test_mode": False}]


def test_simulator_route_streams_archive_from_orchestrator(auth_client, test_twin, monkeypatch):
    calls = []

    class FakeOrchestrator:
        async def download_simulator(self, **kwargs):
            calls.append(kwargs)
            return SimulatorDownload(content=io.BytesIO(b"zip"), filename="simulator.zip")

    monkeypatch.setattr(
        "src.api.routes.twins._deployment_orchestrator",
        lambda _db: FakeOrchestrator(),
    )

    response = auth_client.get(f"/twins/{test_twin.id}/simulator/download")

    assert response.status_code == 200
    assert response.content == b"zip"
    assert response.headers["content-disposition"] == "attachment; filename=simulator.zip"
    assert calls == [{"twin_id": test_twin.id, "user_id": test_twin.user_id, "test_mode": False}]
