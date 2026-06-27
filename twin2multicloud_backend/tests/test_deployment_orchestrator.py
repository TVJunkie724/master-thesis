"""Tests for the deployment orchestrator facade."""

from __future__ import annotations

import io

import pytest

from src.services.deployment_orchestrator import DeploymentOrchestrator
from src.services.simulator_service import SimulatorDownload


class FakeReadService:
    def __init__(self) -> None:
        self.calls = []

    async def can_redeploy(self, twin_id, user_id):
        self.calls.append(("can_redeploy", twin_id, user_id))
        return {"ready": True, "remaining_seconds": 0}

    async def get_status(self, twin_id, user_id, active_session_provider=None):
        self.calls.append(("get_status", twin_id, user_id, active_session_provider))
        return {"state": "configured"}

    def get_outputs(self, twin_id, user_id):
        self.calls.append(("get_outputs", twin_id, user_id))
        return {"outputs": None, "deployed_at": None}

    def get_history(self, twin_id, user_id, limit):
        self.calls.append(("get_history", twin_id, user_id, limit))
        return {"deployments": []}


class FakeOperationService:
    def __init__(self) -> None:
        self.calls = []

    async def deploy_twin(self, **kwargs):
        self.calls.append(("deploy_twin", kwargs))
        return {"session_id": "deploy-session", "sse_url": "/sse/deploy/deploy-session"}

    async def destroy_twin(self, **kwargs):
        self.calls.append(("destroy_twin", kwargs))
        return {"session_id": "destroy-session", "sse_url": "/sse/deploy/destroy-session"}


class FakeVerificationService:
    def __init__(self) -> None:
        self.calls = []

    async def verify_infrastructure(self, **kwargs):
        self.calls.append(("verify_infrastructure", kwargs))
        return {"summary": {"healthy": True}, "checks": []}

    async def start_dataflow_verification(self, **kwargs):
        self.calls.append(("start_dataflow_verification", kwargs))
        return {"session_id": "verify-session", "sse_url": "/sse/deploy/verify-session"}


class FakeSimulatorService:
    def __init__(self) -> None:
        self.calls = []

    async def download(self, **kwargs):
        self.calls.append(("download", kwargs))
        return SimulatorDownload(content=io.BytesIO(b"zip"), filename="simulator.zip")


@pytest.fixture
def orchestrator():
    read = FakeReadService()
    operation = FakeOperationService()
    verification = FakeVerificationService()
    simulator = FakeSimulatorService()
    return DeploymentOrchestrator(
        read_service=read,
        operation_service=operation,
        verification_service=verification,
        simulator_service=simulator,
    ), read, operation, verification, simulator


@pytest.mark.asyncio
async def test_orchestrator_delegates_deploy_and_destroy(orchestrator):
    facade, _read, operation, _verification, _simulator = orchestrator

    async def runner(**_kwargs):
        return None

    deploy = await facade.deploy_twin("twin-1", "user-1", test_mode=True, test_stream_runner=runner)
    destroy = await facade.destroy_twin("twin-1", "user-1", test_mode=False)

    assert deploy["session_id"] == "deploy-session"
    assert destroy["session_id"] == "destroy-session"
    assert operation.calls == [
        (
            "deploy_twin",
            {
                "twin_id": "twin-1",
                "user_id": "user-1",
                "test_mode": True,
                "test_stream_runner": runner,
            },
        ),
        (
            "destroy_twin",
            {
                "twin_id": "twin-1",
                "user_id": "user-1",
                "test_mode": False,
                "test_stream_runner": None,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_orchestrator_delegates_verification_and_simulator(orchestrator):
    facade, _read, _operation, verification, simulator = orchestrator

    infra = await facade.verify_infrastructure("twin-1", "user-1", test_mode=False)
    dataflow = await facade.start_dataflow_verification(
        "twin-1",
        "user-1",
        {"payload": {"iotDeviceId": "device-1"}},
        test_mode=True,
    )
    archive = await facade.download_simulator("twin-1", "user-1", test_mode=False)

    assert infra["summary"]["healthy"] is True
    assert dataflow["session_id"] == "verify-session"
    assert archive.filename == "simulator.zip"
    assert verification.calls == [
        (
            "verify_infrastructure",
            {"twin_id": "twin-1", "user_id": "user-1", "test_mode": False},
        ),
        (
            "start_dataflow_verification",
            {
                "twin_id": "twin-1",
                "user_id": "user-1",
                "body": {"payload": {"iotDeviceId": "device-1"}},
                "test_mode": True,
            },
        ),
    ]
    assert simulator.calls == [
        ("download", {"twin_id": "twin-1", "user_id": "user-1", "test_mode": False})
    ]


@pytest.mark.asyncio
async def test_orchestrator_delegates_read_side_workflows(orchestrator):
    facade, read, _operation, _verification, _simulator = orchestrator

    async def active_sessions(_twin_id):
        return []

    cooldown = await facade.can_redeploy("twin-1", "user-1")
    status = await facade.get_status(
        "twin-1",
        "user-1",
        active_session_provider=active_sessions,
    )
    outputs = facade.get_outputs("twin-1", "user-1")
    history = facade.get_history("twin-1", "user-1", 5)

    assert cooldown["ready"] is True
    assert status["state"] == "configured"
    assert outputs == {"outputs": None, "deployed_at": None}
    assert history == {"deployments": []}
    assert read.calls == [
        ("can_redeploy", "twin-1", "user-1"),
        ("get_status", "twin-1", "user-1", active_sessions),
        ("get_outputs", "twin-1", "user-1"),
        ("get_history", "twin-1", "user-1", 5),
    ]
