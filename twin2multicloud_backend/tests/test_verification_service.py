"""Tests for deployment verification service boundary."""

from __future__ import annotations

import pytest

from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.verification_service import DeploymentVerificationService


def _create_user(db) -> User:
    user = User(email="verification-service@example.test", name="Verification Service", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.DEPLOYED) -> DigitalTwin:
    twin = DigitalTwin(name="Verification Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


async def _prepare_project(_twin, _user_id):
    return "verification-project"


def _closing_scheduler(scheduled):
    def schedule(coro):
        scheduled.append(coro)
        coro.close()

    return schedule


def _session_recorder(records):
    async def create(twin_id, session_id, operation_type):
        records.append((twin_id, session_id, operation_type))

    return create


def _service(
    db,
    *,
    project_preparer=_prepare_project,
    session_records=None,
    scheduled=None,
    infrastructure_verifier=None,
    deployer_client=None,
) -> DeploymentVerificationService:
    session_records = session_records if session_records is not None else []
    scheduled = scheduled if scheduled is not None else []
    return DeploymentVerificationService(
        db=db,
        twin_repository=TwinRepository(db),
        project_preparer=project_preparer,
        session_creator=_session_recorder(session_records),
        task_scheduler=_closing_scheduler(scheduled),
        infrastructure_verifier=infrastructure_verifier,
        deployer_client=deployer_client,
    )


class FakeDeployerClient:
    def __init__(self, result=None, exc=None):
        self.result = result or {"summary": {"healthy": True}, "checks": []}
        self.exc = exc
        self.calls = []

    async def verify_infrastructure(self, resource_name, provider):
        self.calls.append((resource_name, provider))
        if self.exc:
            raise self.exc
        return self.result


@pytest.mark.asyncio
async def test_verify_infrastructure_returns_mock_result_in_test_mode(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    result = await _service(db_session).verify_infrastructure(twin.id, user.id, test_mode=True)

    assert result["summary"]["healthy"] is True
    assert result["summary"]["total"] == 14


@pytest.mark.asyncio
async def test_verify_infrastructure_uses_optimizer_provider(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AZURE"))
    db_session.commit()
    calls = []

    async def verifier(resource_name, provider):
        calls.append((resource_name, provider))
        return {"summary": {"healthy": True}, "checks": []}

    result = await _service(db_session, infrastructure_verifier=verifier).verify_infrastructure(
        twin.id,
        user.id,
        test_mode=False,
    )

    assert result["summary"]["healthy"] is True
    assert calls == [("verification-project", "azure")]


@pytest.mark.asyncio
async def test_verify_infrastructure_normalizes_google_alias_for_deployer_api(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="Google"))
    db_session.commit()
    calls = []

    async def verifier(resource_name, provider):
        calls.append((resource_name, provider))
        return {"summary": {"healthy": True}, "checks": []}

    await _service(db_session, infrastructure_verifier=verifier).verify_infrastructure(
        twin.id,
        user.id,
        test_mode=False,
    )

    assert calls == [("verification-project", "gcp")]


@pytest.mark.asyncio
async def test_verify_infrastructure_default_path_uses_deployer_client(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    fake = FakeDeployerClient()

    result = await _service(db_session, deployer_client=fake).verify_infrastructure(
        twin.id,
        user.id,
        test_mode=False,
    )

    assert result["summary"]["healthy"] is True
    assert fake.calls == [("verification-project", "aws")]


@pytest.mark.asyncio
async def test_verify_infrastructure_maps_deployer_client_errors(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    fake = FakeDeployerClient(
        exc=ExternalServiceError(
            "Deployer API returned 500: client_secret=secret-value",
            upstream_status_code=500,
            public_detail="client_secret=secret-value",
        )
    )

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, deployer_client=fake).verify_infrastructure(
            twin.id,
            user.id,
            test_mode=False,
        )

    assert exc.value.status_code == 500
    assert "secret-value" not in exc.value.public_detail
    assert "client_secret=[REDACTED]" in exc.value.public_detail


@pytest.mark.asyncio
async def test_verify_infrastructure_maps_deployer_unavailable(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    fake = FakeDeployerClient(exc=ExternalServiceUnavailable("Deployer API timed out"))

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, deployer_client=fake).verify_infrastructure(
            twin.id,
            user.id,
            test_mode=False,
        )

    assert exc.value.status_code == 503
    assert "Deployer API unavailable" in exc.value.public_detail


@pytest.mark.asyncio
async def test_verify_infrastructure_rejects_non_deployed_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    with pytest.raises(ValidationError):
        await _service(db_session).verify_infrastructure(twin.id, user.id, test_mode=False)


@pytest.mark.asyncio
async def test_start_dataflow_verification_validates_payload(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError):
        await _service(db_session).start_dataflow_verification(
            twin.id,
            user.id,
            {"payload": {"device_id": "wrong-field"}},
            test_mode=False,
        )


@pytest.mark.asyncio
async def test_start_dataflow_verification_creates_session_and_schedules_proxy(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).start_dataflow_verification(
        twin.id,
        user.id,
        {"payload": {"iotDeviceId": "device-1"}},
        test_mode=False,
    )

    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][0] == twin.id
    assert session_records[0][2] == "verify_dataflow"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_start_dataflow_verification_test_mode_does_not_schedule_proxy(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).start_dataflow_verification(
        twin.id,
        user.id,
        {"payload": {"iotDeviceId": "device-1"}},
        test_mode=True,
    )

    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][2] == "verify_dataflow"
    assert scheduled == []


@pytest.mark.asyncio
async def test_verification_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        await _service(db_session).verify_infrastructure("missing", user.id, test_mode=False)


@pytest.mark.asyncio
async def test_verification_wraps_project_preparation_failure(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    async def failing_preparer(_twin, _user_id):
        raise RuntimeError("prepare failed")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).verify_infrastructure(
            twin.id,
            user.id,
            test_mode=False,
        )

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_verification_hides_project_preparation_failure_details(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    async def failing_preparer(_twin, _user_id):
        raise RuntimeError("Authorization: Bearer verification-secret-token")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).verify_infrastructure(
            twin.id,
            user.id,
            test_mode=False,
        )

    assert "verification-secret-token" not in exc.value.public_detail
    assert exc.value.public_detail == "Failed to prepare project"
