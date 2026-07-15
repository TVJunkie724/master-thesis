"""Tests for deployment command service boundaries."""

from __future__ import annotations

import asyncio
import pytest

from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_operation_service import DeploymentOperationService
from src.services.deployment_service import PreparedDeploymentProject
from src.services.service_errors import (
    ConflictError,
    DownstreamServiceError,
    ValidationError,
)


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


def _service(
    db,
    *,
    active_session_provider=_no_active_sessions,
    session_records=None,
    scheduled=None,
    project_preparer=None,
    session_creator=None,
    session_cleaner=None,
    task_scheduler=None,
):
    session_records = session_records if session_records is not None else []
    scheduled = scheduled if scheduled is not None else []

    async def default_preparer(_twin, _user_id):
        return PreparedDeploymentProject("resource-name", "operation-token")

    async def default_cleaner(_session_id):
        return None

    return DeploymentOperationService(
        db=db,
        twin_repository=TwinRepository(db),
        active_session_provider=active_session_provider,
        session_creator=session_creator or _session_recorder(session_records),
        session_cleaner=session_cleaner or default_cleaner,
        task_scheduler=task_scheduler or _closing_scheduler(scheduled),
        project_preparer=project_preparer or default_preparer,
    )


@pytest.mark.asyncio
async def test_deploy_sets_state_and_schedules_real_stream(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    session_records = []
    scheduled = []

    result = await _service(
        db_session, session_records=session_records, scheduled=scheduled
    ).deploy_twin(
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
async def test_deploy_normalizes_google_alias_for_deployer_api(db_session, monkeypatch):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="Google"))
    db_session.commit()
    stream_calls = []

    async def fake_run_real_deploy_stream(**kwargs):
        stream_calls.append(kwargs)

    monkeypatch.setattr(
        "src.services.deployment_operation_service.run_real_deploy_stream",
        fake_run_real_deploy_stream,
    )
    session_records = []

    service = DeploymentOperationService(
        db=db_session,
        twin_repository=TwinRepository(db_session),
        session_creator=_session_recorder(session_records),
        task_scheduler=asyncio.create_task,
        project_preparer=lambda _twin, _user_id: _async_resource_name(),
    )

    await service.deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=False,
    )
    await asyncio.sleep(0)

    assert stream_calls[0]["provider"] == "gcp"


async def _async_resource_name():
    return PreparedDeploymentProject("resource-name", "operation-token")


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
        await _service(
            db_session, active_session_provider=_active_sessions
        ).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED


@pytest.mark.asyncio
async def test_deploy_rolls_back_when_active_session_lookup_fails(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    async def failing_session_lookup(_twin_id):
        raise RuntimeError("registry unavailable")

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            active_session_provider=failing_session_lookup,
        ).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED
    assert exc_info.value.public_detail == (
        "Failed to check active deployment operations"
    )


@pytest.mark.asyncio
async def test_test_mode_missing_runner_does_not_change_twin_state(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    with pytest.raises(ValidationError, match="runner is not configured"):
        await _service(db_session).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=True,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED


@pytest.mark.asyncio
async def test_deploy_active_session_restores_original_state_when_validation_is_skipped(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)

    with pytest.raises(ConflictError):
        await _service(
            db_session, active_session_provider=_active_sessions
        ).deploy_twin(
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
        raise DownstreamServiceError(
            status_code=502, public_detail="Deployer project setup failed"
        )

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
async def test_deploy_preparation_failure_restores_original_allowed_state(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DESTROYED)

    async def failing_preparer(_twin, _user_id):
        raise DownstreamServiceError(
            status_code=502, public_detail="Deployer project setup failed"
        )

    with pytest.raises(DownstreamServiceError):
        await _service(db_session, project_preparer=failing_preparer).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DESTROYED


@pytest.mark.asyncio
async def test_deploy_redacts_project_preparation_public_detail(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    async def failing_preparer(_twin, _user_id):
        raise DownstreamServiceError(
            status_code=502, public_detail="client_secret=LEAKED-SECRET-123"
        )

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    assert "LEAKED-SECRET-123" not in exc.value.public_detail
    assert "client_secret=[REDACTED]" in exc.value.public_detail


@pytest.mark.asyncio
async def test_deploy_rolls_back_when_session_creation_fails(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    async def failing_session_creator(_twin_id, _session_id, _operation_type):
        raise RuntimeError("session registry failed")

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            session_creator=failing_session_creator,
        ).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED
    assert exc_info.value.public_detail == "Failed to start deployment session"


@pytest.mark.asyncio
async def test_deploy_cleans_session_and_rolls_back_when_scheduling_fails(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    cleaned = []

    async def cleaner(session_id):
        cleaned.append(session_id)

    def failing_scheduler(_operation):
        raise RuntimeError("scheduler failed")

    with pytest.raises(DownstreamServiceError):
        await _service(
            db_session,
            session_cleaner=cleaner,
            task_scheduler=failing_scheduler,
        ).deploy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.CONFIGURED
    assert len(cleaned) == 1


@pytest.mark.asyncio
async def test_destroy_sets_state_and_schedules_real_stream(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DEPLOYED)
    session_records = []
    scheduled = []

    result = await _service(
        db_session, session_records=session_records, scheduled=scheduled
    ).destroy_twin(
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
        await _service(
            db_session, active_session_provider=_active_sessions
        ).destroy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYED


@pytest.mark.asyncio
async def test_destroy_cleans_session_and_rolls_back_when_scheduling_fails(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DEPLOYED)
    cleaned = []

    async def cleaner(session_id):
        cleaned.append(session_id)

    def failing_scheduler(_operation):
        raise RuntimeError("scheduler failed")

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            session_cleaner=cleaner,
            task_scheduler=failing_scheduler,
        ).destroy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYED
    assert exc_info.value.public_detail == "Failed to start destroy session"
    assert len(cleaned) == 1


@pytest.mark.asyncio
async def test_destroy_active_session_restores_original_state_when_validation_is_skipped(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)

    with pytest.raises(ConflictError):
        await _service(
            db_session, active_session_provider=_active_sessions
        ).destroy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=True,
            test_stream_runner=_fake_test_runner,
            skip_state_validation=True,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DRAFT


@pytest.mark.asyncio
async def test_destroy_fails_closed_and_restores_state_when_project_preparation_fails(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DEPLOYED)
    session_records = []
    scheduled = []

    async def failing_preparer(_twin, _user_id):
        raise RuntimeError("aws_secret_access_key=DESTROY-SECRET")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(
            db_session,
            session_records=session_records,
            scheduled=scheduled,
            project_preparer=failing_preparer,
        ).destroy_twin(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYED
    assert exc.value.public_detail == "Failed to prepare project for destroy"
    assert "DESTROY-SECRET" not in exc.value.public_detail
    assert session_records == []
    assert scheduled == []


@pytest.mark.asyncio
async def test_test_mode_deploy_uses_test_session_type(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)
    session_records = []
    scheduled = []

    result = await _service(
        db_session, session_records=session_records, scheduled=scheduled
    ).deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=True,
        test_stream_runner=_fake_test_runner,
    )

    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][2] == "test"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_test_mode_deploy_can_skip_state_validation_for_explicit_test_endpoint(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DRAFT)
    session_records = []
    scheduled = []

    result = await _service(
        db_session, session_records=session_records, scheduled=scheduled
    ).deploy_twin(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=True,
        test_stream_runner=_fake_test_runner,
        skip_state_validation=True,
    )

    db_session.refresh(twin)
    assert twin.state == TwinState.DEPLOYING
    assert result["sse_url"].startswith("/sse/deploy/")
