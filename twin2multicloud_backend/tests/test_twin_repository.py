"""Tests for TwinRepository persistence boundaries."""

from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository


def _create_user(db, email: str = "repo-owner@example.test") -> User:
    user = User(email=email, name=email, auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, name: str = "Factory Twin", state: TwinState = TwinState.DRAFT) -> DigitalTwin:
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


def test_get_active_for_user_filters_owner_and_inactive_state(db_session):
    owner = _create_user(db_session, "repo-active-owner@example.test")
    other = _create_user(db_session, "repo-active-other@example.test")
    active = _create_twin(db_session, owner, "Active")
    inactive = _create_twin(db_session, owner, "Inactive", TwinState.INACTIVE)
    other_twin = _create_twin(db_session, other, "Other")
    repository = TwinRepository(db_session)

    assert repository.get_active_for_user(active.id, owner.id).id == active.id
    assert repository.get_active_for_user(inactive.id, owner.id) is None
    assert repository.get_active_for_user(other_twin.id, owner.id) is None
    assert repository.get_for_user(inactive.id, owner.id).id == inactive.id


def test_find_active_by_name_is_case_insensitive_and_ignores_inactive(db_session):
    user = _create_user(db_session, "repo-name@example.test")
    active = _create_twin(db_session, user, "My Twin")
    _create_twin(db_session, user, "Reusable", TwinState.INACTIVE)

    repository = TwinRepository(db_session)

    assert repository.find_active_by_name(user.id, "my twin").id == active.id
    assert repository.find_active_by_name(user.id, "reusable") is None


def test_name_exists_for_user_is_case_insensitive_and_ignores_inactive(db_session):
    owner = _create_user(db_session, "repo-name-exists@example.test")
    twin = _create_twin(db_session, owner, "Factory Twin")
    _create_twin(db_session, owner, "Reusable", TwinState.INACTIVE)
    repository = TwinRepository(db_session)

    assert repository.name_exists_for_user("factory twin", owner.id) is True
    assert repository.name_exists_for_user("Factory Twin", owner.id, exclude_twin_id=twin.id) is False
    assert repository.name_exists_for_user("Reusable", owner.id) is False


def test_get_with_configs_for_user_loads_related_configuration_records(db_session):
    owner = _create_user(db_session, "repo-configs@example.test")
    twin = _create_twin(db_session, owner)
    db_session.add(TwinConfiguration(twin_id=twin.id, debug_mode=True))
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="aws"))
    db_session.add(DeployerConfiguration(twin_id=twin.id, deployer_digital_twin_name="factory"))
    db_session.commit()

    loaded = TwinRepository(db_session).get_with_configs_for_user(twin.id, owner.id)

    assert loaded is not None
    assert loaded.configuration.debug_mode is True
    assert loaded.optimizer_config.cheapest_l1 == "aws"
    assert loaded.deployer_config.deployer_digital_twin_name == "factory"


def test_soft_delete_marks_inactive_and_renames_to_free_unique_name(db_session):
    owner = _create_user(db_session, "repo-soft-delete@example.test")
    twin = _create_twin(db_session, owner, "Reusable Name")
    repository = TwinRepository(db_session)

    repository.soft_delete(twin)
    db_session.commit()
    db_session.refresh(twin)

    assert twin.state == TwinState.INACTIVE
    assert twin.name == f"_deleted_{twin.id}_Reusable Name"
    assert repository.name_exists_for_user("Reusable Name", owner.id) is False
