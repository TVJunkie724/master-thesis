"""Tests for the deployment orchestrator facade."""

from __future__ import annotations

import io

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_operation_service import DeploymentOperationService
from src.services.deployment_service import PreparedDeploymentProject
from src.services.deployment_orchestrator import DeploymentOrchestrator
from src.services.service_errors import ConflictError, DownstreamServiceError
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
        return {
            "session_id": "destroy-session",
            "sse_url": "/sse/deploy/destroy-session",
        }


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


def _create_user(db, email: str = "deployment-orchestrator@example.test") -> User:
    user = User(email=email, name="Deployment Orchestrator", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState) -> DigitalTwin:
    twin = DigitalTwin(name=f"Orchestrator Twin {id(db)}", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


async def _no_active_sessions(_twin_id):
    return []


async def _active_sessions(_twin_id):
    return [object()]


def _closing_scheduler(scheduled):
    def schedule(coro):
        scheduled.append(coro)
        coro.close()

    return schedule


def _session_recorder(records):
    async def create(twin_id, session_id, operation_type):
        records.append((twin_id, session_id, operation_type))

    return create


def _operation_backed_orchestrator(
    db,
    *,
    active_session_provider=_no_active_sessions,
    project_preparer=None,
    session_records=None,
    scheduled=None,
) -> DeploymentOrchestrator:
    session_records = session_records if session_records is not None else []
    scheduled = scheduled if scheduled is not None else []

    async def default_preparer(_twin, _user_id):
        return PreparedDeploymentProject("orchestrator-resource", "operation-token")

    operation_service = DeploymentOperationService(
        db=db,
        twin_repository=TwinRepository(db),
        active_session_provider=active_session_provider,
        session_creator=_session_recorder(session_records),
        task_scheduler=_closing_scheduler(scheduled),
        project_preparer=project_preparer or default_preparer,
    )
    return DeploymentOrchestrator(
        read_service=FakeReadService(),
        operation_service=operation_service,
        verification_service=FakeVerificationService(),
        simulator_service=FakeSimulatorService(),
    )


@pytest.fixture
def orchestrator():
    read = FakeReadService()
    operation = FakeOperationService()
    verification = FakeVerificationService()
    simulator = FakeSimulatorService()
    return (
        DeploymentOrchestrator(
            read_service=read,
            operation_service=operation,
            verification_service=verification,
            simulator_service=simulator,
        ),
        read,
        operation,
        verification,
        simulator,
    )


@pytest.mark.asyncio
async def test_orchestrator_delegates_deploy_and_destroy(orchestrator):
    facade, _read, operation, _verification, _simulator = orchestrator

    async def runner(**_kwargs):
        return None

    deploy = await facade.deploy_twin(
        "twin-1", "user-1", test_mode=True, test_stream_runner=runner
    )
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
                "skip_state_validation": False,
            },
        ),
        (
            "destroy_twin",
            {
                "twin_id": "twin-1",
                "user_id": "user-1",
                "test_mode": False,
                "test_stream_runner": None,
                "skip_state_validation": False,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_orchestrator_deploy_success_updates_lifecycle_and_schedules_stream(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    session_records = []
    scheduled = []

    result = await _operation_backed_orchestrator(
        db_session,
        session_records=session_records,
        scheduled=scheduled,
    ).deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=False,
    )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYING
    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][2] == "deploy"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_orchestrator_deploy_rolls_back_when_session_is_active(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    with pytest.raises(ConflictError):
        await _operation_backed_orchestrator(
            db_session,
            active_session_provider=_active_sessions,
        ).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED


@pytest.mark.asyncio
async def test_orchestrator_deploy_wraps_package_or_upstream_failure_and_rolls_back(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    async def failing_preparer(_twin, _user_id):
        raise DownstreamServiceError(
            status_code=502,
            public_detail="client_secret=LEAKED-ORCHESTRATOR-SECRET",
        )

    with pytest.raises(DownstreamServiceError) as exc:
        await _operation_backed_orchestrator(
            db_session,
            project_preparer=failing_preparer,
        ).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED
    assert exc.value.status_code == 502
    assert "LEAKED-ORCHESTRATOR-SECRET" not in exc.value.public_detail
    assert "client_secret=[REDACTED]" in exc.value.public_detail


@pytest.mark.asyncio
async def test_orchestrator_uses_configured_test_runners_when_route_does_not_override():
    operation = FakeOperationService()

    async def deploy_runner(**_kwargs):
        return None

    async def destroy_runner(**_kwargs):
        return None

    facade = DeploymentOrchestrator(
        read_service=FakeReadService(),
        operation_service=operation,
        verification_service=FakeVerificationService(),
        simulator_service=FakeSimulatorService(),
        test_deploy_stream_runner=deploy_runner,
        test_destroy_stream_runner=destroy_runner,
    )

    await facade.deploy_twin(
        "twin-1", "user-1", test_mode=True, skip_state_validation=True
    )
    await facade.destroy_twin(
        "twin-1", "user-1", test_mode=True, skip_state_validation=True
    )

    assert operation.calls == [
        (
            "deploy_twin",
            {
                "twin_id": "twin-1",
                "user_id": "user-1",
                "test_mode": True,
                "test_stream_runner": deploy_runner,
                "skip_state_validation": True,
            },
        ),
        (
            "destroy_twin",
            {
                "twin_id": "twin-1",
                "user_id": "user-1",
                "test_mode": True,
                "test_stream_runner": destroy_runner,
                "skip_state_validation": True,
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
