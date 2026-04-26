from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository


def _create_user(db, email="owner@example.test") -> User:
    user = User(email=email, name=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user_id: str, name="Factory Twin", state=TwinState.DRAFT) -> DigitalTwin:
    twin = DigitalTwin(name=name, user_id=user_id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def test_list_active_for_user_excludes_inactive_and_other_users(db):
    owner = _create_user(db)
    other = _create_user(db, "other@example.test")
    active = _create_twin(db, owner.id, "Active")
    _create_twin(db, owner.id, "Inactive", TwinState.INACTIVE)
    _create_twin(db, other.id, "Other")

    twins = TwinRepository(db).list_active_for_user(owner.id)

    assert [t.id for t in twins] == [active.id]


def test_get_active_for_user_filters_owner_and_inactive_state(db):
    owner = _create_user(db)
    other = _create_user(db, "other@example.test")
    active = _create_twin(db, owner.id, "Active")
    inactive = _create_twin(db, owner.id, "Inactive", TwinState.INACTIVE)
    other_twin = _create_twin(db, other.id, "Other")
    repository = TwinRepository(db)

    assert repository.get_active_for_user(active.id, owner.id).id == active.id
    assert repository.get_active_for_user(inactive.id, owner.id) is None
    assert repository.get_active_for_user(other_twin.id, owner.id) is None


def test_name_exists_for_user_is_case_insensitive_and_ignores_inactive(db):
    owner = _create_user(db)
    twin = _create_twin(db, owner.id, "Factory Twin")
    _create_twin(db, owner.id, "Reusable", TwinState.INACTIVE)
    repository = TwinRepository(db)

    assert repository.name_exists_for_user("factory twin", owner.id) is True
    assert repository.name_exists_for_user("Factory Twin", owner.id, exclude_twin_id=twin.id) is False
    assert repository.name_exists_for_user("Reusable", owner.id) is False


def test_get_with_configs_for_user_loads_related_configuration_records(db):
    owner = _create_user(db)
    twin = _create_twin(db, owner.id)
    db.add(TwinConfiguration(twin_id=twin.id, debug_mode=True))
    db.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="aws"))
    db.add(DeployerConfiguration(twin_id=twin.id, deployer_digital_twin_name="factory"))
    db.commit()

    loaded = TwinRepository(db).get_with_configs_for_user(twin.id, owner.id)

    assert loaded is not None
    assert loaded.configuration.debug_mode is True
    assert loaded.optimizer_config.cheapest_l1 == "aws"
    assert loaded.deployer_config.deployer_digital_twin_name == "factory"


def test_soft_delete_marks_inactive_and_renames_to_free_unique_name(db):
    owner = _create_user(db)
    twin = _create_twin(db, owner.id, "Reusable Name")
    repository = TwinRepository(db)

    repository.soft_delete(twin)
    db.commit()
    db.refresh(twin)

    assert twin.state == TwinState.INACTIVE
    assert twin.name == f"_deleted_{twin.id}_Reusable Name"
    assert repository.name_exists_for_user("Reusable Name", owner.id) is False
