"""Tests for deployment verification service boundary."""

from __future__ import annotations

import json

import pytest

from src.models.deployment import Deployment
from src.models.telemetry_verification import TelemetryVerification
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_service import PreparedDeploymentProject
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.service_errors import (
    DownstreamServiceError,
    EntityNotFoundError,
    ValidationError,
)
from src.services.verification_service import DeploymentVerificationService


def _create_user(db) -> User:
    user = User(
        email="verification-service@example.test",
        name="Verification Service",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.DEPLOYED) -> DigitalTwin:
    twin = DigitalTwin(name="Verification Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    if state == TwinState.DEPLOYED:
        db.add(
            Deployment(
                twin_id=twin.id,
                session_id=f"successful-deploy-{twin.id}",
                operation_type="deploy",
                status="success",
            )
        )
        db.commit()
    return twin


async def _prepare_project(_twin, _user_id):
    return PreparedDeploymentProject("verification-project", "operation-token")


def _project_preparer(provider):
    async def prepare(_twin, _user_id):
        return PreparedDeploymentProject(
            "verification-project",
            "operation-token",
            provider=provider,
        )

    return prepare


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
    session_getter=None,
) -> DeploymentVerificationService:
    session_records = session_records if session_records is not None else []
    scheduled = scheduled if scheduled is not None else []
    kwargs = {}
    if session_getter is not None:
        kwargs["session_getter"] = session_getter
    return DeploymentVerificationService(
        db=db,
        twin_repository=TwinRepository(db),
        project_preparer=project_preparer,
        session_creator=_session_recorder(session_records),
        task_scheduler=_closing_scheduler(scheduled),
        infrastructure_verifier=infrastructure_verifier,
        deployer_client=deployer_client,
        **kwargs,
    )


class FakeDeployerClient:
    def __init__(self, result=None, exc=None):
        self.result = result or {"summary": {"healthy": True}, "checks": []}
        self.exc = exc
        self.calls = []

    async def verify_infrastructure(self, resource_name, provider, operation_token):
        self.calls.append((resource_name, provider, operation_token))
        if self.exc:
            raise self.exc
        return self.result


@pytest.mark.asyncio
async def test_verify_infrastructure_returns_mock_result_in_test_mode(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    result = await _service(db_session).verify_infrastructure(
        twin.id, user.id, test_mode=True
    )

    assert result["summary"]["healthy"] is True
    assert result["summary"]["total"] == 14


@pytest.mark.asyncio
async def test_verify_infrastructure_uses_architecture_provider(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    calls = []

    async def verifier(prepared_project, provider):
        calls.append((prepared_project.resource_name, provider))
        return {"summary": {"healthy": True}, "checks": []}

    result = await _service(
        db_session,
        project_preparer=_project_preparer("azure"),
        infrastructure_verifier=verifier,
    ).verify_infrastructure(
        twin.id,
        user.id,
        test_mode=False,
    )

    assert result["summary"]["healthy"] is True
    assert calls == [("verification-project", "azure")]


@pytest.mark.asyncio
async def test_verify_infrastructure_normalizes_google_alias_for_deployer_api(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    calls = []

    async def verifier(prepared_project, provider):
        calls.append((prepared_project.resource_name, provider))
        return {"summary": {"healthy": True}, "checks": []}

    await _service(
        db_session,
        project_preparer=_project_preparer("gcp"),
        infrastructure_verifier=verifier,
    ).verify_infrastructure(
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
    assert fake.calls == [("verification-project", "aws", "operation-token")]


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
        await _service(db_session).verify_infrastructure(
            twin.id, user.id, test_mode=False
        )


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
async def test_start_dataflow_verification_creates_session_and_schedules_proxy(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    session_records = []
    scheduled = []

    result = await _service(
        db_session, session_records=session_records, scheduled=scheduled
    ).start_dataflow_verification(
        twin.id,
        user.id,
        {"payload": {"iotDeviceId": "device-1"}},
        test_mode=False,
    )

    assert result["sse_url"].startswith("/sse/deploy/")
    assert result["status"] == "running"
    assert result["verification_id"]
    assert session_records[0][0] == twin.id
    assert session_records[0][2] == "verify_dataflow"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_start_dataflow_verification_test_mode_does_not_schedule_proxy(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    session_records = []
    scheduled = []

    result = await _service(
        db_session, session_records=session_records, scheduled=scheduled
    ).start_dataflow_verification(
        twin.id,
        user.id,
        {"payload": {"iotDeviceId": "device-1"}},
        test_mode=True,
    )

    assert result["sse_url"].startswith("/sse/deploy/")
    assert result["status"] == "not_run"
    assert session_records[0][2] == "verify_dataflow"
    assert scheduled == []
    record = db_session.get(TelemetryVerification, result["verification_id"])
    assert record.status == "not_run"
    assert record.error_code == "TEST_MODE_NOT_RUN"


@pytest.mark.asyncio
async def test_start_dataflow_verification_does_not_create_session_when_prepare_fails(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    session_records = []
    scheduled = []

    async def failing_preparer(_twin, _user_id):
        raise DownstreamServiceError(
            status_code=503, public_detail="Deployer unavailable"
        )

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            project_preparer=failing_preparer,
            session_records=session_records,
            scheduled=scheduled,
        ).start_dataflow_verification(
            twin.id,
            user.id,
            {"payload": {"iotDeviceId": "device-1"}},
            test_mode=False,
        )

    assert exc_info.value.status_code == 503
    assert session_records == []
    assert scheduled == []


@pytest.mark.asyncio
async def test_verification_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        await _service(db_session).verify_infrastructure(
            "missing", user.id, test_mode=False
        )


@pytest.mark.asyncio
async def test_verification_wraps_project_preparation_failure(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    async def failing_preparer(_twin, _user_id):
        raise RuntimeError("prepare failed")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(
            db_session, project_preparer=failing_preparer
        ).verify_infrastructure(
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
        await _service(
            db_session, project_preparer=failing_preparer
        ).verify_infrastructure(
            twin.id,
            user.id,
            test_mode=False,
        )

    assert "verification-secret-token" not in exc.value.public_detail
    assert exc.value.public_detail == "Failed to prepare project"


@pytest.mark.asyncio
async def test_verification_preserves_safe_downstream_preparation_status(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    async def failing_preparer(_twin, _user_id):
        raise DownstreamServiceError(
            status_code=503,
            public_detail="client_secret=verification-secret",
        )

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            project_preparer=failing_preparer,
        ).verify_infrastructure(twin.id, user.id, test_mode=False)

    assert exc_info.value.status_code == 503
    assert exc_info.value.public_detail == "client_secret=[REDACTED]"


class _VerificationSession:
    def __init__(self):
        self.logs = []
        self.completion = None

    async def push_log(self, message):
        self.logs.append(message)

    def on_complete(self, **kwargs):
        self.completion = kwargs


class _DataflowClient:
    def __init__(self, lines):
        self.lines = lines

    async def verify_dataflow(self, *_args):
        for line in self.lines:
            yield line


def _terminal_evidence(**overrides):
    value = {
        "schema_version": "telemetry-verification.v1",
        "trace_id": "VERIFY-1234ABCD",
        "status": "pass",
        "pass_count": 3,
        "fail_count": 0,
        "skip_count": 0,
        "total_time": 4.2,
        "failed_phase": None,
        "evidence": [
            {
                "phase": 1,
                "kind": "message_accepted",
                "provider": "aws",
            },
            {
                "phase": 2,
                "kind": "trace_correlated_hot_record",
                "provider": "azure",
                "record_count": 1,
            },
            {
                "phase": 3,
                "kind": "gcp_twin_projection",
                "provider": "gcp",
                "correlation": "source_sequence",
            },
        ],
    }
    value.update(overrides)
    return value


def _running_verification(db, twin):
    deployment = db.query(Deployment).filter(Deployment.twin_id == twin.id).first()
    record = TelemetryVerification(
        twin_id=twin.id,
        deployment_id=deployment.id,
        session_id=f"verification-{twin.id}",
        device_id="device-1",
        status="running",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.mark.asyncio
async def test_proxy_persists_closed_trace_correlated_terminal_evidence(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    record = _running_verification(db_session, twin)
    session = _VerificationSession()
    terminal = _terminal_evidence()

    async def get_verification_session(_session_id):
        return session

    service = _service(
        db_session,
        deployer_client=_DataflowClient(
            ["event: done", f"data: {json.dumps(terminal)}", ""]
        ),
        session_getter=get_verification_session,
    )

    await service.proxy_dataflow_sse(
        verification_id=record.id,
        session_id=record.session_id,
        prepared_project=PreparedDeploymentProject("project", "token"),
        payload={"iotDeviceId": "device-1"},
    )

    db_session.refresh(record)
    assert record.status == "pass"
    assert record.trace_id == "VERIFY-1234ABCD"
    assert record.result["schema_version"] == "telemetry-verification.v1"
    assert record.result["evidence"] == terminal["evidence"]
    assert "failed_phase" not in record.result
    assert session.completion["success"] is True


@pytest.mark.asyncio
async def test_proxy_rejects_untyped_terminal_without_persisting_secret(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    record = _running_verification(db_session, twin)
    session = _VerificationSession()
    terminal = _terminal_evidence(client_secret="must-not-persist")

    async def get_verification_session(_session_id):
        return session

    service = _service(
        db_session,
        deployer_client=_DataflowClient(
            ["event: done", f"data: {json.dumps(terminal)}", ""]
        ),
        session_getter=get_verification_session,
    )

    await service.proxy_dataflow_sse(
        verification_id=record.id,
        session_id=record.session_id,
        prepared_project=PreparedDeploymentProject("project", "token"),
        payload={"iotDeviceId": "device-1"},
    )

    db_session.refresh(record)
    assert record.status == "fail"
    assert record.result is None
    assert record.error_code == "INVALID_VERIFICATION_EVIDENCE"
    assert "must-not-persist" not in (record.error_message or "")
    assert all("must-not-persist" not in message for message in session.logs)


def test_verification_history_is_owner_scoped_and_typed(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    record = _running_verification(db_session, twin)

    result = _service(db_session).list_dataflow_verifications(
        twin.id,
        user.id,
        limit=25,
    )

    assert result.schema_version == "telemetry-verification-history.v1"
    assert [item.id for item in result.verifications] == [record.id]
