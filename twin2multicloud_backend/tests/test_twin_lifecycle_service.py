"""Tests for TwinLifecycleService and TwinReadService."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.errors import InvalidTwinStateTransition, OperationAlreadyInProgress
from src.services.service_errors import ConflictError, EntityNotFoundError, ValidationError
from src.services.twin_lifecycle_service import TwinLifecycleService, TwinReadService


def _memory_twin(state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    return DigitalTwin(id="twin-1", name="Factory Twin", user_id="user-1", state=state)


def _create_user(db, email: str = "lifecycle@example.test") -> User:
    user = User(email=email, name="Lifecycle", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, name: str, state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    twin = DigitalTwin(name=name, user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


async def _noop_configured_validator(_twin, _db):
    return None


def _lifecycle(db) -> TwinLifecycleService:
    return TwinLifecycleService(db=db, twin_repository=TwinRepository(db))


def _reader(db) -> TwinReadService:
    return TwinReadService(twin_repository=TwinRepository(db))


def test_rename_updates_allowed_state():
    twin = _memory_twin(TwinState.DRAFT)

    TwinLifecycleService().rename(twin, "Renamed Twin")

    assert twin.name == "Renamed Twin"


@pytest.mark.parametrize("state", [TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING])
def test_rename_blocks_deployment_owned_states(state):
    twin = _memory_twin(state)

    with pytest.raises(InvalidTwinStateTransition) as exc_info:
        TwinLifecycleService().rename(twin, "Renamed Twin")

    assert exc_info.value.message == f"Cannot rename twin in '{state.value}' state"
    assert twin.name == "Factory Twin"


@pytest.mark.parametrize("state", [TwinState.CONFIGURED, TwinState.DESTROYED, TwinState.ERROR])
def test_start_deploy_allows_configured_destroyed_and_error(state):
    twin = _memory_twin(state)
    twin.last_error = "old error"

    TwinLifecycleService().start_deploy(twin)

    assert twin.state == TwinState.DEPLOYING
    assert twin.last_error is None


@pytest.mark.parametrize("state", [TwinState.DRAFT, TwinState.DEPLOYED, TwinState.DESTROYING, TwinState.INACTIVE])
def test_start_deploy_rejects_invalid_states(state):
    twin = _memory_twin(state)

    with pytest.raises(InvalidTwinStateTransition) as exc_info:
        TwinLifecycleService().start_deploy(twin)

    assert exc_info.value.message == (
        f"Cannot deploy twin in '{state.value}' state. Must be configured, destroyed, or error."
    )
    assert twin.state == state


def test_start_deploy_reports_operation_in_progress():
    twin = _memory_twin(TwinState.DEPLOYING)

    with pytest.raises(OperationAlreadyInProgress) as exc_info:
        TwinLifecycleService().start_deploy(twin)

    assert exc_info.value.message == "Deployment already in progress"


def test_deploy_completion_and_failure_mutate_state_and_error_fields():
    service = TwinLifecycleService()
    deployed_at = datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc)
    twin = _memory_twin(TwinState.DEPLOYING)

    service.complete_deploy(twin, deployed_at=deployed_at)

    assert twin.state == TwinState.DEPLOYED
    assert twin.deployed_at == deployed_at
    assert twin.last_error is None

    service.fail_deploy(twin, "terraform failed")

    assert twin.state == TwinState.ERROR
    assert twin.last_error == "terraform failed"


@pytest.mark.parametrize("state", [TwinState.DEPLOYED, TwinState.ERROR])
def test_start_destroy_allows_deployed_and_error(state):
    twin = _memory_twin(state)
    twin.last_error = "old error"

    TwinLifecycleService().start_destroy(twin)

    assert twin.state == TwinState.DESTROYING
    assert twin.last_error is None


@pytest.mark.parametrize(
    "state",
    [TwinState.DRAFT, TwinState.CONFIGURED, TwinState.DEPLOYING, TwinState.DESTROYED, TwinState.INACTIVE],
)
def test_start_destroy_rejects_invalid_states(state):
    twin = _memory_twin(state)

    with pytest.raises(InvalidTwinStateTransition) as exc_info:
        TwinLifecycleService().start_destroy(twin)

    assert exc_info.value.message == (
        f"Cannot destroy twin in '{state.value}' state. Must be deployed or error."
    )
    assert twin.state == state


def test_start_destroy_reports_operation_in_progress():
    twin = _memory_twin(TwinState.DESTROYING)

    with pytest.raises(OperationAlreadyInProgress) as exc_info:
        TwinLifecycleService().start_destroy(twin)

    assert exc_info.value.message == "Destroy operation already in progress"


def test_destroy_completion_and_failure_mutate_state_and_error_fields():
    service = TwinLifecycleService()
    destroyed_at = datetime(2026, 4, 26, 11, 0, tzinfo=timezone.utc)
    twin = _memory_twin(TwinState.DESTROYING)

    service.complete_destroy(twin, destroyed_at=destroyed_at)

    assert twin.state == TwinState.DESTROYED
    assert twin.destroyed_at == destroyed_at
    assert twin.last_error is None

    service.fail_destroy(twin, "destroy failed")

    assert twin.state == TwinState.ERROR
    assert twin.last_error == "destroy failed"


def test_deploy_and_destroy_rollbacks_restore_previous_state():
    service = TwinLifecycleService()
    twin = _memory_twin(TwinState.DEPLOYING)

    service.rollback_deploy_start(twin, previous_state=TwinState.DESTROYED)
    assert twin.state == TwinState.DESTROYED

    twin.state = TwinState.DESTROYING
    service.rollback_destroy_start(twin, previous_state=TwinState.ERROR)
    assert twin.state == TwinState.ERROR


def test_read_service_lists_only_active_twins(db_session):
    user = _create_user(db_session)
    active = _create_twin(db_session, user, "Active")
    _create_twin(db_session, user, "Inactive", TwinState.INACTIVE)

    result = _reader(db_session).list_twins(user.id)

    assert [twin.id for twin in result] == [active.id]


def test_create_twin_enforces_active_duplicate_name(db_session):
    user = _create_user(db_session)
    service = _lifecycle(db_session)

    service.create_twin("My Twin", user.id)

    with pytest.raises(ConflictError, match="already exists"):
        service.create_twin("my twin", user.id)


def test_create_twin_reuses_inactive_name(db_session):
    user = _create_user(db_session)
    _create_twin(db_session, user, "_deleted_old-id_Reusable", TwinState.INACTIVE)

    twin = _lifecycle(db_session).create_twin("Reusable", user.id)

    assert twin.name == "Reusable"
    assert twin.state == TwinState.DRAFT


@pytest.mark.asyncio
async def test_update_twin_renames_and_sets_state(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, "Original")

    result = await _lifecycle(db_session).update_twin(
        twin_id=twin.id,
        user_id=user.id,
        name="Renamed",
        state=TwinState.ERROR,
        configured_validator=_noop_configured_validator,
    )

    assert result.name == "Renamed"
    assert result.state == TwinState.ERROR


@pytest.mark.asyncio
async def test_update_twin_blocks_rename_for_deployed_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, "Original", TwinState.DEPLOYED)

    with pytest.raises(ValidationError, match="Cannot rename twin"):
        await _lifecycle(db_session).update_twin(
            twin_id=twin.id,
            user_id=user.id,
            name="Renamed",
            state=None,
            configured_validator=_noop_configured_validator,
        )


@pytest.mark.asyncio
async def test_update_twin_invokes_configured_validator(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, "Configurable")
    calls = []

    async def validator(candidate, db):
        calls.append((candidate.id, db is db_session))

    result = await _lifecycle(db_session).update_twin(
        twin_id=twin.id,
        user_id=user.id,
        name=None,
        state=TwinState.CONFIGURED,
        configured_validator=validator,
    )

    assert result.state == TwinState.CONFIGURED
    assert calls == [(twin.id, True)]


def test_delete_twin_soft_deletes_and_renames(db_session, tmp_path, monkeypatch):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, "Delete Me")
    upload_dir = tmp_path / "uploads"
    twin_dir = upload_dir / twin.id
    twin_dir.mkdir(parents=True)
    (twin_dir / "scene.glb").write_bytes(b"glb")
    monkeypatch.setattr("src.services.twin_lifecycle_service.settings.UPLOAD_DIR", str(upload_dir))

    result = _lifecycle(db_session).delete_twin(twin.id, user.id)

    db_session.refresh(twin)
    assert result == {"message": "Twin deleted"}
    assert twin.state == TwinState.INACTIVE
    assert twin.name.startswith(f"_deleted_{twin.id}_")
    assert not twin_dir.exists()


def test_unknown_twin_raises_not_found(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        _reader(db_session).get_twin("missing", user.id)


def test_read_service_hides_inactive_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, "Inactive", TwinState.INACTIVE)

    with pytest.raises(EntityNotFoundError):
        _reader(db_session).get_twin(twin.id, user.id)
