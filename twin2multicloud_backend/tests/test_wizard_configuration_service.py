"""Unit tests for backend-owned wizard configuration update semantics."""

import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.schemas.deployer_config import DeployerConfigUpdate
from src.schemas.twin_config import TwinConfigUpdate
from src.services.wizard_configuration_service import WizardConfigurationService


def _create_twin(db_session, state=TwinState.DRAFT):
    user = User(email="wizard-service@example.test", name="Wizard Service")
    db_session.add(user)
    db_session.flush()

    twin = DigitalTwin(name="Wizard Service Twin", user_id=user.id, state=state)
    db_session.add(twin)
    db_session.flush()
    return user, twin


def test_deployer_update_distinguishes_omitted_and_explicit_null(db_session):
    _, twin = _create_twin(db_session)
    service = WizardConfigurationService(db_session)

    config = service.apply_deployer_config_update(
        twin,
        DeployerConfigUpdate(
            payloads_json='{"device-1":{"temperature":21}}',
            payloads_validated=True,
            processor_contents={"device-1": "def process(event): return event"},
        ),
    )
    db_session.flush()

    service.apply_deployer_config_update(
        twin,
        DeployerConfigUpdate(config_events_json="[]"),
    )
    assert config.config_events_json == "[]"
    assert config.payloads_json == '{"device-1":{"temperature":21}}'
    assert config.payloads_validated is True
    assert config.processor_contents is not None

    service.apply_deployer_config_update(
        twin,
        DeployerConfigUpdate(
            payloads_json=None,
            payloads_validated=None,
            processor_contents=None,
        ),
    )
    assert config.payloads_json is None
    assert config.payloads_validated is False
    assert config.processor_contents is None


def test_twin_config_update_rejects_direct_per_twin_credentials(db_session):
    user, twin = _create_twin(db_session)

    with pytest.raises(HTTPException) as exc_info:
        WizardConfigurationService(db_session).apply_twin_config_update(
            twin,
            TwinConfigUpdate.model_validate(
                {
                    "gcp": {
                        "project_id": "my-project-12345",
                        "billing_account": "012345-6789AB-CDEF01",
                        "region": "europe-west1",
                    }
                }
            ),
            user.id,
        )

    assert exc_info.value.status_code == 400
    assert "Cloud Connection" in exc_info.value.detail


def test_wizard_updates_regress_configured_twin_to_draft(db_session):
    _, twin = _create_twin(db_session, state=TwinState.CONFIGURED)

    WizardConfigurationService(db_session).apply_deployer_config_update(
        twin,
        DeployerConfigUpdate(payloads_json='{"device-1":{}}'),
    )

    assert twin.state == TwinState.DRAFT


def test_optimizer_update_is_parameter_only(
    db_session,
    sample_calc_params,
):
    user, twin = _create_twin(db_session)
    service = WizardConfigurationService(db_session)

    service.apply_twin_config_update(
        twin,
        TwinConfigUpdate.model_validate(
            {
                "optimizer_params": sample_calc_params,
            }
        ),
        user.id,
    )

    optimizer_config = twin.optimizer_config
    assert json.loads(optimizer_config.params) == sample_calc_params
    assert optimizer_config.result_json is None
    assert optimizer_config.cheapest_l1 is None

    service.apply_twin_config_update(
        twin,
        TwinConfigUpdate.model_validate({"debug_mode": True}),
        user.id,
    )
    assert json.loads(optimizer_config.params) == sample_calc_params
    assert optimizer_config.result_json is None

    service.apply_twin_config_update(
        twin,
        TwinConfigUpdate.model_validate({"optimizer_params": None}),
        user.id,
    )
    assert optimizer_config.params is None
    assert optimizer_config.result_json is None
    assert optimizer_config.cheapest_l1 is None


def test_twin_update_schema_rejects_client_authored_optimizer_result():
    with pytest.raises(PydanticValidationError):
        TwinConfigUpdate.model_validate(
            {
                "optimizer_result": {
                    "totalCost": 1,
                    "cheapestPath": ["L1_AWS"],
                }
            }
        )
