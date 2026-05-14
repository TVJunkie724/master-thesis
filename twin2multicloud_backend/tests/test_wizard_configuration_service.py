"""Unit tests for backend-owned wizard configuration update semantics."""

import json

import pytest
from fastapi import HTTPException

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


def test_twin_config_update_rejects_stored_gcp_without_service_account(db_session):
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

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "service_account_json is required for stored GCP credentials"


def test_wizard_updates_regress_configured_twin_to_draft(db_session):
    _, twin = _create_twin(db_session, state=TwinState.CONFIGURED)

    WizardConfigurationService(db_session).apply_deployer_config_update(
        twin,
        DeployerConfigUpdate(payloads_json='{"device-1":{}}'),
    )

    assert twin.state == TwinState.DRAFT


def test_optimizer_update_distinguishes_omitted_and_explicit_null(db_session):
    user, twin = _create_twin(db_session)
    service = WizardConfigurationService(db_session)

    service.apply_twin_config_update(
        twin,
        TwinConfigUpdate.model_validate(
            {
                "optimizer_params": {"numberOfDevices": 10},
                "optimizer_result": {
                    "cheapestPath": ["L1_AWS", "L2_AZURE", "L4_GCP"],
                    "calculationResult": {},
                },
            }
        ),
        user.id,
    )

    optimizer_config = twin.optimizer_config
    assert json.loads(optimizer_config.params) == {"numberOfDevices": 10}
    assert optimizer_config.cheapest_l1 == "aws"
    assert optimizer_config.cheapest_l2 == "azure"
    assert optimizer_config.cheapest_l4 == "gcp"

    service.apply_twin_config_update(
        twin,
        TwinConfigUpdate.model_validate({"debug_mode": True}),
        user.id,
    )
    assert json.loads(optimizer_config.params) == {"numberOfDevices": 10}
    assert optimizer_config.result_json is not None
    assert optimizer_config.cheapest_l1 == "aws"

    service.apply_twin_config_update(
        twin,
        TwinConfigUpdate.model_validate(
            {
                "optimizer_params": None,
                "optimizer_result": None,
            }
        ),
        user.id,
    )
    assert optimizer_config.params is None
    assert optimizer_config.result_json is None
    assert optimizer_config.cheapest_l1 is None
    assert optimizer_config.cheapest_l2 is None
    assert optimizer_config.cheapest_l4 is None
