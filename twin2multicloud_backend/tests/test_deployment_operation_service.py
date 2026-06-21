"""Tests for deployment command service boundaries."""

from __future__ import annotations

from fastapi import HTTPException
import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_operation_service import DeploymentOperationService
from src.services.service_errors import ConflictError, DownstreamServiceError, ValidationError


def _create_user(db, email: str = "operation@example.test") -> User:
    user = User(email=email, name="Operation", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState) -> DigitalTwin:
    twin = DigitalTwin(name=f"Operation Twin {id(db)}", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _closing_scheduler(scheduled):
    def schedule(coro):
        scheduled.append(coro)
        coro.close()

    return schedule


async def _no_active_sessions(_twin_id):
    return []


async def _active_sessions(_twin_id):
    return [object()]


def _session_recorder(records):
    async def create(twin_id, session_id, operation_type):
        records.append((twin_id, session_id, operation_type))

    return create


async def _fake_test_runner(**_kwargs):
    return None


def _service(db, *, active_session_provider=_no_active_sessions, session_records=None, scheduled=None, project_preparer=None):
    session_records = session_records if session_records is not None else []
    scheduled = scheduled if scheduled is not None else []

    async def default_preparer(_twin, _user_id):
        return "resource-name"

    return DeploymentOperationService(
        db=db,
        twin_repository=TwinRepository(db),
        active_session_provider=active_session_provider,
        session_creator=_session_recorder(session_records),
        task_scheduler=_closing_scheduler(scheduled),
        project_preparer=project_preparer or default_preparer,
    )


@pytest.mark.asyncio
async def test_deploy_sets_state_and_schedules_real_stream(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=False,
    )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYING
    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][0] == twin.id
    assert session_records[0][2] == "deploy"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_deploy_rejects_invalid_state(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)

    with pytest.raises(ValidationError):
        await _service(db_session).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )


@pytest.mark.asyncio
async def test_deploy_rolls_back_when_active_session_exists(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    with pytest.raises(ConflictError):
        await _service(db_session, active_session_provider=_active_sessions).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED


@pytest.mark.asyncio
async def test_deploy_active_session_restores_original_state_when_validation_is_skipped(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)

    with pytest.raises(ConflictError):
        await _service(db_session, active_session_provider=_active_sessions).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=True,
            test_stream_runner=_fake_test_runner,
            skip_state_validation=True,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DRAFT


@pytest.mark.asyncio
async def test_deploy_rolls_back_on_project_preparation_failure(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    async def failing_preparer(_twin, _user_id):
        raise HTTPException(status_code=502, detail="Deployer project setup failed")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_deploy_redacts_project_preparation_public_detail(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    async def failing_preparer(_twin, _user_id):
        raise HTTPException(status_code=502, detail="client_secret=LEAKED-SECRET-123")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    assert "LEAKED-SECRET-123" not in exc.value.public_detail
    assert "client_secret=[REDACTED]" in exc.value.public_detail


@pytest.mark.asyncio
async def test_destroy_sets_state_and_schedules_real_stream(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DEPLOYED)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).destroy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=False,
    )

    db_session.refresh(twin)
    assert twin.state == TwinState.DESTROYING
    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][0] == twin.id
    assert session_records[0][2] == "destroy"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_destroy_rolls_back_when_active_session_exists(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DEPLOYED)

    with pytest.raises(ConflictError):
        await _service(db_session, active_session_provider=_active_sessions).destroy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYED


@pytest.mark.asyncio
async def test_destroy_active_session_restores_original_state_when_validation_is_skipped(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)

    with pytest.raises(ConflictError):
        await _service(db_session, active_session_provider=_active_sessions).destroy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=True,
            test_stream_runner=_fake_test_runner,
            skip_state_validation=True,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DRAFT


@pytest.mark.asyncio
async def test_test_mode_deploy_uses_test_session_type(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=True,
        test_stream_runner=_fake_test_runner,
    )

    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][2] == "test"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_test_mode_deploy_can_skip_state_validation_for_explicit_test_endpoint(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=True,
        test_stream_runner=_fake_test_runner,
        skip_state_validation=True,
    )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYING
    assert result["sse_url"].startswith("/sse/deploy/")
