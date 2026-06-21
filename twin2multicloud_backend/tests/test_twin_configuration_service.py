"""Tests for twin configuration read/write service boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_config import AWSCredentials, TwinConfigUpdate
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.twin_configuration_service import TwinConfigurationService


def _create_user(db) -> User:
    user = User(email="twin-config-service@example.test", name="Twin Config", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    twin = DigitalTwin(name="Config Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db) -> TwinConfigurationService:
    return TwinConfigurationService(db=db, twin_repository=TwinRepository(db))


def test_get_config_creates_default_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).get_config(twin.id, user.id)

    assert response.twin_id == twin.id
    assert response.aws_configured is False


def test_update_config_rejects_direct_aws_credentials(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    update = TwinConfigUpdate(
        aws=AWSCredentials(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            region="eu-central-1",
        )
    )

    with pytest.raises(ValidationError, match="Cloud Connection"):
        _service(db_session).update_config(twin.id, user.id, update)


def test_update_config_regresses_configured_twin_to_draft(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    result = _service(db_session).update_config(twin.id, user.id, TwinConfigUpdate(debug_mode=True))

    db_session.refresh(twin)
    assert twin.state == TwinState.DRAFT
    assert result["twin_state"] == "draft"


def test_update_config_blocks_deployed_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.DEPLOYED)

    with pytest.raises(ValidationError):
        _service(db_session).update_config(twin.id, user.id, TwinConfigUpdate(debug_mode=True))


def test_update_config_populates_optimizer_cheapest_columns(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    optimizer_result = {
        "cheapestPath": [
            "L1_GCP",
            "L2_AWS",
            "L3_hot_AZURE",
            "L3_cool_GCP",
            "L3_archive_AWS",
            "L4_AZURE",
            "L5_GCP",
        ]
    }

    _service(db_session).update_config(
        twin.id,
        user.id,
        TwinConfigUpdate(optimizer_params={"numberOfDevices": 10}, optimizer_result=optimizer_result),
    )

    db_session.refresh(twin)
    assert twin.optimizer_config.cheapest_l1 == "gcp"
    assert twin.optimizer_config.cheapest_l2 == "aws"
    assert twin.optimizer_config.cheapest_l3_hot == "azure"
    assert twin.optimizer_config.cheapest_l3_cool == "gcp"
    assert twin.optimizer_config.cheapest_l3_archive == "aws"
    assert twin.optimizer_config.cheapest_l4 == "azure"
    assert twin.optimizer_config.cheapest_l5 == "gcp"


def test_get_config_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        _service(db_session).get_config("missing", user.id)
