"""Tests for TwinRepository persistence boundaries."""

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository


def _create_user(db, email: str) -> User:
    user = User(email=email, name=email, auth_provider="google")
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


def test_list_active_for_user_excludes_inactive_and_other_users(db_session):
    user = _create_user(db_session, "repo-owner@example.test")
    other = _create_user(db_session, "repo-other@example.test")
    active = _create_twin(db_session, user, "Active")
    _create_twin(db_session, user, "Inactive", TwinState.INACTIVE)
    _create_twin(db_session, other, "Other")

    result = TwinRepository(db_session).list_active_for_user(user.id)

    assert [twin.id for twin in result] == [active.id]


def test_find_active_by_name_is_case_insensitive_and_ignores_inactive(db_session):
    user = _create_user(db_session, "repo-name@example.test")
    active = _create_twin(db_session, user, "My Twin")
    _create_twin(db_session, user, "Reusable", TwinState.INACTIVE)

    repository = TwinRepository(db_session)

    assert repository.find_active_by_name(user.id, "my twin").id == active.id
    assert repository.find_active_by_name(user.id, "reusable") is None


def test_get_active_for_user_filters_inactive(db_session):
    user = _create_user(db_session, "repo-active@example.test")
    inactive = _create_twin(db_session, user, "Inactive", TwinState.INACTIVE)

    repository = TwinRepository(db_session)

    assert repository.get_active_for_user(inactive.id, user.id) is None
    assert repository.get_for_user(inactive.id, user.id).id == inactive.id

