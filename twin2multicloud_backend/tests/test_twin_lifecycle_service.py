"""Tests for TwinLifecycleService and TwinReadService."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import ConflictError, EntityNotFoundError, ValidationError
from src.services.twin_lifecycle_service import TwinLifecycleService, TwinReadService


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

    try:
        service.create_twin("my twin", user.id)
    except ConflictError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected ConflictError")


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

    try:
        await _lifecycle(db_session).update_twin(
            twin_id=twin.id,
            user_id=user.id,
            name="Renamed",
            state=None,
            configured_validator=_noop_configured_validator,
        )
    except ValidationError as exc:
        assert "Cannot rename twin" in str(exc)
    else:
        raise AssertionError("Expected ValidationError")


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

    try:
        _reader(db_session).get_twin("missing", user.id)
    except EntityNotFoundError:
        pass
    else:
        raise AssertionError("Expected EntityNotFoundError")


def test_read_service_hides_inactive_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, "Inactive", TwinState.INACTIVE)

    try:
        _reader(db_session).get_twin(twin.id, user.id)
    except EntityNotFoundError:
        pass
    else:
        raise AssertionError("Expected EntityNotFoundError")
