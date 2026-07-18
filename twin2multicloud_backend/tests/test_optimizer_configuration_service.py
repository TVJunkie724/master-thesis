"""Tests for the read and parameter-draft optimizer configuration boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_config import OptimizerParamsUpdate
from src.services.optimizer_configuration_service import OptimizerConfigurationService
from src.services.service_errors import EntityNotFoundError


def _create_user(db, email: str = "optimizer-config-service@example.test") -> User:
    user = User(email=email, name="Optimizer Config", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(
    db,
    user: User,
    state: TwinState = TwinState.DRAFT,
) -> DigitalTwin:
    twin = DigitalTwin(name="Optimizer Config Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db) -> OptimizerConfigurationService:
    return OptimizerConfigurationService(db, TwinRepository(db))


def test_get_config_creates_default_optimizer_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).get_config(twin.id, user.id)

    assert response.twin_id == twin.id
    assert response.params is None
    assert response.result is None
    assert response.cheapest_path is None


def test_update_params_persists_without_calculation(
    db_session,
    sample_calc_params,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).update_params(
        twin.id,
        user.id,
        OptimizerParamsUpdate(params={**sample_calc_params, "numberOfDevices": 250}),
    )

    assert response.params == {**sample_calc_params, "numberOfDevices": 250}
    assert response.result is None
    assert response.cheapest_path is None


def test_update_params_persists_compatibility_defaults(
    db_session,
    sample_calc_params,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    params = {
        key: value
        for key, value in sample_calc_params.items()
        if not key.startswith("averageDigitalTwinQuery")
    }

    response = _service(db_session).update_params(
        twin.id,
        user.id,
        OptimizerParamsUpdate(params=params),
    )

    assert response.params["averageDigitalTwinQueryUnitsPerQuery"] == 1
    assert response.params["averageDigitalTwinQueryResponseSizeInKb"] == 1


def test_get_cheapest_path_rejects_missing_result(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    _service(db_session).get_config(twin.id, user.id)

    with pytest.raises(EntityNotFoundError, match="No optimizer result found"):
        _service(db_session).get_cheapest_path(twin.id, user.id)


def test_service_rejects_inactive_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.INACTIVE)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        _service(db_session).get_config(twin.id, user.id)
