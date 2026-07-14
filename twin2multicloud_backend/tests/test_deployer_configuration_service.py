"""Tests for deployer configuration read/write service boundary."""

from __future__ import annotations

import json

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployer_config import DeployerConfigUpdate
from src.services.deployer_configuration_service import DeployerConfigurationService
from src.services.service_errors import EntityNotFoundError, ValidationError


def _create_user(db) -> User:
    user = User(email="deployer-config-service@example.test", name="Deployer Config", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    twin = DigitalTwin(name="Deployer Config Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db) -> DeployerConfigurationService:
    return DeployerConfigurationService(db=db, twin_repository=TwinRepository(db))


def test_get_config_creates_default_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).get_config(twin.id, user.id)

    db_session.refresh(twin)
    assert response.twin_id == twin.id
    assert twin.deployer_config is not None
    assert response.config_json_validated is False


def test_update_config_persists_scalar_and_json_dict_fields(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    result = _service(db_session).update_config(
        twin.id,
        user.id,
        DeployerConfigUpdate(
            deployer_digital_twin_name="thesis-twin",
            config_events_json='{"events": []}',
            config_json_validated=True,
            processor_contents={"device-1": "def process(payload): return payload"},
            processor_validated={"device-1": True},
            processor_requirements={"device-1": "numpy==1.26.0"},
            event_action_contents={"alarm": "def handler(event): return event"},
            event_action_validated={"alarm": False},
            scene_glb_uploaded=True,
        ),
    )

    db_session.refresh(twin)
    assert result["twin_state"] == "draft"
    assert result["deployer_digital_twin_name"] == "thesis-twin"
    assert result["processor_validated"] == {"device-1": True}
    assert twin.deployer_config.config_events_json == '{"events": []}'
    assert twin.deployer_config.config_json_validated is True
    assert json.loads(twin.deployer_config.processor_contents) == {
        "device-1": "def process(payload): return payload"
    }
    assert json.loads(twin.deployer_config.event_action_contents) == {
        "alarm": "def handler(event): return event"
    }
    assert twin.deployer_config.scene_glb_uploaded is True


def test_update_config_regresses_configured_twin_to_draft(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    result = _service(db_session).update_config(
        twin.id,
        user.id,
        DeployerConfigUpdate(deployer_digital_twin_name="draft-again"),
    )

    db_session.refresh(twin)
    assert twin.state == TwinState.DRAFT
    assert result["twin_state"] == "draft"


@pytest.mark.parametrize("blocked_state", [TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING])
def test_update_config_blocks_immutable_states(db_session, blocked_state):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, blocked_state)

    with pytest.raises(ValidationError, match=f"Cannot modify twin in '{blocked_state.value}' state"):
        _service(db_session).update_config(
            twin.id,
            user.id,
            DeployerConfigUpdate(deployer_digital_twin_name="blocked"),
        )


def test_update_config_rejects_too_long_deployer_name(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError, match="Digital twin name exceeds 15 characters"):
        _service(db_session).update_config(
            twin.id,
            user.id,
            DeployerConfigUpdate(deployer_digital_twin_name="name-is-too-long"),
        )


def test_get_config_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        _service(db_session).get_config("missing", user.id)


@pytest.mark.parametrize("operation", ["get", "update"])
def test_config_rejects_inactive_twin(db_session, operation):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.INACTIVE)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        if operation == "get":
            _service(db_session).get_config(twin.id, user.id)
        else:
            _service(db_session).update_config(
                twin.id,
                user.id,
                DeployerConfigUpdate(deployer_digital_twin_name="inactive"),
            )
