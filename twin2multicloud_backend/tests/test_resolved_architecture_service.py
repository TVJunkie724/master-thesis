"""Six-layer resolved-architecture validation and persistence coverage."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json

import pytest
from sqlalchemy.exc import StatementError

from src.models.architecture_profile import (
    ArchitectureAuditEvent,
    ResolvedTwinArchitectureRecord,
)
from src.models.cost_calculation import CostCalculationRun
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin
from src.models.user import User
from src.models.user_function_extension import TwinUserFunction
from src.services.architecture_contract_service import (
    calculate_digest,
    calculate_resolution_id,
)
from src.services.architecture_errors import ArchitectureDomainError
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.resolved_architecture_service import (
    ARCHITECTURE_METRICS,
    ResolvedArchitectureService,
)
from tests.architecture_test_data import (
    RUN_ID,
    calculation_result_and_contracts,
    linked_architecture_fixture_documents,
)


def _state(db_session):
    result, specification, architecture = calculation_result_and_contracts()
    user = User(id="resolved-owner", email="resolved@example.test")
    twin = DigitalTwin(
        id="resolved-twin",
        user_id=user.id,
        name="Resolved Twin",
    )
    config = OptimizerConfiguration(id="resolved-config", twin_id=twin.id)
    db_session.add_all([user, twin, config])
    db_session.flush()

    profile = ArchitectureProfileService.get_definition(
        "six-layer-eventing",
        "1",
    )
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=twin.id,
            user_id=user.id,
        )
    )
    extension = architecture["extension_bindings"][0]
    user_function = TwinUserFunction(
        id=extension["artifact_id"],
        twin_id=twin.id,
        artifact_digest=extension["artifact_digest"],
        slot_id=extension["slot_id"],
        slot_version=extension["slot_version"],
        runtime_id="python311",
        manifest_json="{}",
        configuration_json='{"scale_factor":1}',
        declared_capabilities_json="[]",
        validator_version="user-function-validator.v1",
    )
    db_session.add(user_function)
    db_session.flush()

    calculation = result["calculationResult"]
    run = CostCalculationRun(
        id=RUN_ID,
        twin_id=twin.id,
        user_id=user.id,
        optimizer_config_id=config.id,
        optimizer_config=config,
        status="succeeded",
        params_json="{}",
        result_summary_json=json.dumps(result),
        cheapest_path_json=json.dumps(
            {
                "l1": calculation["L1"],
                "l2": calculation["L2"],
                "l3_hot": calculation["L3"]["Hot"],
                "l3_cool": calculation["L3"]["Cool"],
                "l3_archive": calculation["L3"]["Archive"],
                "l4": calculation["L4"],
                "l5": calculation["L5"],
                "eventing": calculation["Eventing"],
            }
        ),
        total_monthly_cost=float(result["totalCostExact"]),
        currency=result["currency"],
        optimization_profile_id=profile["optimization_bundle"][
            "optimization_strategy_id"
        ],
        optimization_profile_version=profile["optimization_bundle"][
            "optimization_strategy_version"
        ],
        scoring_strategy_id=profile["optimization_bundle"]["scoring_strategy_id"],
        calculation_model_version="profile-resolution-v2@2",
        deployment_specification_json=json.dumps(specification),
        deployment_specification_digest=specification["digest"],
        deployment_specification_version=specification["schema_version"],
        deployment_compatibility_status="ready",
    )
    db_session.add(run)
    return user, twin, config, run, architecture


def _persist(db_session):
    state = _state(db_session)
    record = ResolvedArchitectureService(db_session).persist(
        run=state[3],
        raw_architecture=state[4],
        linked_documents=linked_architecture_fixture_documents(),
    )
    return (*state, record)


def test_six_layer_resolution_is_canonical_atomic_and_reproducible(db_session):
    user, twin, config, run, architecture, record = _persist(db_session)
    run.selected_for_deployment_at = datetime.now(timezone.utc)
    db_session.commit()

    service = ResolvedArchitectureService(db_session)
    assert record.schema_version == "resolved-twin-architecture.v2"
    assert record.origin == "native_v2"
    assert len(record.components) == 8
    assert len(record.edges) == 9
    assert run.architecture_compatibility_status == "ready"
    assert run.resolved_architecture_digest == architecture["content_digest"]
    service.assert_projection_reproduction(record)
    assert (
        service.get_for_run(
            calculation_run_id=run.id, user_id=user.id
        ).architecture.content_digest
        == record.content_digest
    )
    assert (
        service.get_for_selected_twin(
            twin_id=twin.id, user_id=user.id
        ).architecture.content_digest
        == record.content_digest
    )


def test_offline_fixture_persists_but_cannot_be_selected_for_deployment(db_session):
    _user, _twin, _config, run, _architecture, _record = _persist(db_session)
    db_session.flush()

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).require_selectable(run)

    assert rejected.value.code == "ARCH_RESOLUTION_INCOMPLETE"


def test_duplicate_resolution_is_rejected(db_session):
    _user, _twin, _config, run, architecture, _record = _persist(db_session)
    db_session.commit()
    before = ARCHITECTURE_METRICS[("ARCH_RESOLUTION_DUPLICATE", "1")]

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert rejected.value.code == "ARCH_RESOLUTION_DUPLICATE"
    assert ARCHITECTURE_METRICS[("ARCH_RESOLUTION_DUPLICATE", "1")] == before + 1


def test_digest_tamper_is_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    tampered = copy.deepcopy(architecture)
    tampered["cost_summary"]["monthly_total"] = "8"

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=tampered,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert rejected.value.code == "ARCH_RESOLUTION_DIGEST_MISMATCH"
    assert db_session.query(ResolvedTwinArchitectureRecord).count() == 0


def test_component_binding_drift_is_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    specification = json.loads(run.deployment_specification_json)
    specification["component_selections"][0]["provider"] = "azure"
    run.deployment_specification_json = json.dumps(specification)

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert rejected.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_cross_resolution_edge_reference_is_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    architecture["resolved_edges"][0]["destination_assignment_id"] = (
        "assignment.unknown"
    )
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    architecture["content_digest"] = calculate_digest(architecture)

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert rejected.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_stale_extension_binding_is_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    user_function = db_session.query(TwinUserFunction).one()
    user_function.artifact_digest = "sha256:" + "0" * 64

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert rejected.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_architecture_records_and_audits_are_immutable(db_session):
    _user, _twin, _config, _run, _architecture, record = _persist(db_session)
    db_session.commit()
    record.currency = "EUR"

    with pytest.raises((ValueError, StatementError)):
        db_session.commit()
    db_session.rollback()

    event = db_session.query(ArchitectureAuditEvent).one()
    event_id = event.id
    db_session.delete(event)
    with pytest.raises((ValueError, StatementError), match="append-only"):
        db_session.commit()
    db_session.rollback()
    assert db_session.get(ArchitectureAuditEvent, event_id) is not None
