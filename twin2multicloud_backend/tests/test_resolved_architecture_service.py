"""Immutable resolved architecture validation and projection coverage."""

from __future__ import annotations

import copy
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
from src.models.user_function_extension import (
    TwinExtensionBinding,
    UserFunctionArtifact,
)
from src.services.architecture_errors import ArchitectureDomainError
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.architecture_contract_service import (
    calculate_digest,
    calculate_resolution_id,
)
from src.services.resolved_architecture_service import (
    ARCHITECTURE_METRICS,
    ResolvedArchitectureService,
)
from src.services.cost_calculation_run_service import CostCalculationRunService
from tests.pricing_catalog_test_data import catalog_context
from tests.architecture_test_data import (
    RUN_ID,
    calculation_result_and_contracts,
    linked_architecture_fixture_documents,
)


def _state(db_session, provider: str | None = None):
    result, specification, architecture = calculation_result_and_contracts(
        provider
    )
    calculation_path = result["calculationResult"]
    user = User(id="resolved-owner", email="resolved@example.test")
    twin = DigitalTwin(
        id="resolved-twin",
        user_id=user.id,
        name="Resolved Twin",
    )
    config = OptimizerConfiguration(
        id="resolved-config",
        twin_id=twin.id,
    )
    db_session.add_all([user, twin, config])
    db_session.flush()
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=twin.id,
            user_id=user.id,
        )
    )
    artifact = UserFunctionArtifact(
        id="artifact.user.processor.example",
        user_id=user.id,
        schema_version="user-function-artifact.v1",
        artifact_state="valid",
        artifact_digest=architecture["extension_bindings"][0][
            "artifact_digest"
        ],
        slot_id="processor.telemetry",
        slot_version="1",
        runtime_id="python311",
        configuration_json="{}",
        declared_capabilities_json="[]",
        validator_version="user-function-validator.v1",
        created_by=user.id,
    )
    binding = TwinExtensionBinding(
        id="resolved-binding",
        user_id=user.id,
        twin_id=twin.id,
        slot_id="processor.telemetry",
        slot_version="1",
        artifact_id=artifact.id,
        binding_digest="sha256:" + ("4" * 64),
        active=True,
        revision=1,
    )
    db_session.add_all([artifact, binding])
    db_session.flush()
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
                "l1": calculation_path["L1"],
                "l2": calculation_path["L2"],
                "l3_hot": calculation_path["L3"]["Hot"],
                "l3_cool": calculation_path["L3"]["Cool"],
                "l3_archive": calculation_path["L3"]["Archive"],
                "l4": calculation_path["L4"],
                "l5": calculation_path["L5"],
            }
        ),
        total_monthly_cost=7.6,
        currency="USD",
        optimization_profile_id="cost_minimization_v1",
        optimization_profile_version="1",
        scoring_strategy_id="min_total_cost_v1",
        deployment_specification_json=json.dumps(specification),
        deployment_specification_digest=specification["digest"],
        deployment_specification_version=specification["schema_version"],
        deployment_compatibility_status="ready",
    )
    db_session.add(run)
    return user, twin, config, run, architecture


@pytest.mark.parametrize("provider", ("aws", "azure"))
def test_single_provider_resolution_is_canonical_and_complete(
    db_session,
    provider,
):
    _user, _twin, _config, run, architecture = _state(
        db_session,
        provider,
    )

    metric_before = ARCHITECTURE_METRICS[("persisted", "1")]
    record = ResolvedArchitectureService(db_session).persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    db_session.commit()

    assert {
        assignment.provider for assignment in record.components
    } == {provider}
    assert len(record.components) == 7
    assert len(record.edges) == 6
    assert ARCHITECTURE_METRICS[("persisted", "1")] == metric_before + 1


def test_persist_is_canonical_atomic_and_reproducible(db_session):
    user, twin, config, run, architecture = _state(db_session)
    service = ResolvedArchitectureService(db_session)

    record = service.persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    run.selected_for_deployment_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    db_session.commit()
    db_session.refresh(record)

    assert run.architecture_compatibility_status == "ready"
    assert run.resolved_architecture_digest == architecture["content_digest"]
    assert len(record.components) == 7
    assert len(record.edges) == 6
    service.assert_projection_reproduction(record)
    assert config.cheapest_l1 == "AWS"
    assert config.cheapest_l2 == "Azure"
    assert config.cheapest_l5 == "Azure"
    selected = service.get_for_selected_twin(
        twin_id=twin.id,
        user_id=user.id,
    )
    assert selected.architecture.content_digest == record.content_digest


def test_historical_resolution_remains_readable_but_not_selectable_after_profile_change(
    db_session,
):
    user, twin, _config, run, architecture = _state(db_session)
    service = ResolvedArchitectureService(db_session)
    service.persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    db_session.commit()
    selection = service.repository.get_selection(twin.id, user.id)
    selection.profile_id = "new-profile"
    selection.profile_digest = "sha256:" + ("9" * 64)
    selection.revision += 1
    db_session.commit()

    historical = service.get_for_run(
        calculation_run_id=run.id,
        user_id=user.id,
    )
    with pytest.raises(ArchitectureDomainError) as rejected:
        service.require_selectable(run)

    assert historical.calculation_run_id == run.id
    assert rejected.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_duplicate_digest_and_reference_mismatch_are_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    service = ResolvedArchitectureService(db_session)
    service.persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    db_session.commit()
    duplicate_metric_before = ARCHITECTURE_METRICS[
        ("ARCH_RESOLUTION_DUPLICATE", "1")
    ]

    with pytest.raises(ArchitectureDomainError) as duplicate:
        service.persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )
    assert duplicate.value.code == "ARCH_RESOLUTION_DUPLICATE"
    assert ARCHITECTURE_METRICS[
        ("ARCH_RESOLUTION_DUPLICATE", "1")
    ] == duplicate_metric_before + 1

    db_session.rollback()
    other_user = User(id="other-owner", email="other@example.test")
    other_twin = DigitalTwin(
        id="other-twin",
        user_id=other_user.id,
        name="Other",
    )
    other_config = OptimizerConfiguration(id="other-config", twin_id=other_twin.id)
    db_session.add_all([other_user, other_twin, other_config])
    db_session.flush()
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=other_twin.id,
            user_id=other_user.id,
        )
    )
    other_run = CostCalculationRun(
        id="018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a02",
        twin_id=other_twin.id,
        user_id=other_user.id,
        optimizer_config_id=other_config.id,
        optimizer_config=other_config,
        status="succeeded",
        params_json="{}",
        result_summary_json=run.result_summary_json,
        total_monthly_cost=7.6,
        currency="USD",
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        deployment_specification_json=run.deployment_specification_json,
        deployment_specification_digest=run.deployment_specification_digest,
        deployment_specification_version=run.deployment_specification_version,
        deployment_compatibility_status="ready",
    )
    db_session.add(other_run)
    with pytest.raises(ArchitectureDomainError) as mismatch:
        service.persist(
            run=other_run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )
    assert mismatch.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_digest_tamper_and_mutation_are_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    tampered = copy.deepcopy(architecture)
    tampered["cost_summary"]["monthly_total"] = "8"

    with pytest.raises(ArchitectureDomainError) as digest:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=tampered,
            linked_documents=linked_architecture_fixture_documents(),
        )
    assert digest.value.code == "ARCH_RESOLUTION_DIGEST_MISMATCH"
    assert (
        db_session.query(ResolvedTwinArchitectureRecord).count() == 0
    )

    db_session.rollback()
    _user, _twin, _config, run, architecture = _state(db_session)
    service = ResolvedArchitectureService(db_session)
    record = service.persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    db_session.commit()
    record.currency = "EUR"
    with pytest.raises((ValueError, StatementError)):
        db_session.commit()
    db_session.rollback()


def test_architecture_audit_events_are_append_only(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    ResolvedArchitectureService(db_session).persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    db_session.commit()
    event = db_session.query(ArchitectureAuditEvent).one()
    event_id = event.id

    db_session.delete(event)
    with pytest.raises((ValueError, StatementError), match="append-only"):
        db_session.commit()
    db_session.rollback()
    assert db_session.get(ArchitectureAuditEvent, event_id) is not None


def test_missing_resolution_payload_returns_stable_domain_error(db_session):
    _user, _twin, _config, run, _architecture = _state(db_session)
    metric_before = ARCHITECTURE_METRICS[
        ("ARCH_RESOLUTION_INVALID", "unknown")
    ]

    with pytest.raises(ArchitectureDomainError) as rejected:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=None,
        )

    assert rejected.value.code == "ARCH_RESOLUTION_INVALID"
    assert ARCHITECTURE_METRICS[
        ("ARCH_RESOLUTION_INVALID", "unknown")
    ] == metric_before + 1


def test_cross_contract_component_mismatch_is_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    specification = json.loads(run.deployment_specification_json)
    specification["components"] = specification["components"][1:]
    run.deployment_specification_json = json.dumps(specification)

    with pytest.raises(ArchitectureDomainError) as mismatch:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )
    assert mismatch.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_cross_resolution_edge_reference_is_rejected(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    architecture["resolved_edges"][0][
        "destination_assignment_id"
    ] = "assignment.unknown"
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    architecture["content_digest"] = calculate_digest(architecture)

    with pytest.raises(ArchitectureDomainError) as mismatch:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert mismatch.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_profile_optimization_bundle_drift_is_reference_mismatch(
    db_session,
):
    _user, _twin, _config, run, architecture = _state(db_session)
    architecture["optimization_bundle_ref"]["formula_set_version"] = "2"
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    architecture["content_digest"] = calculate_digest(architecture)

    with pytest.raises(ArchitectureDomainError) as mismatch:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )

    assert mismatch.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_incomplete_capabilities_and_stale_extension_binding_are_rejected(
    db_session,
):
    _user, _twin, _config, run, architecture = _state(db_session)
    incomplete = copy.deepcopy(architecture)
    missing = incomplete["functional_completeness"][
        "provided_capability_ids"
    ].pop()
    incomplete["functional_completeness"]["missing_capability_ids"] = [
        missing
    ]
    incomplete["content_digest"] = calculate_digest(incomplete)

    with pytest.raises(ArchitectureDomainError) as capability_error:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=incomplete,
            linked_documents=linked_architecture_fixture_documents(),
        )
    assert capability_error.value.code == "ARCH_RESOLUTION_INCOMPLETE"

    binding = (
        db_session.query(TwinExtensionBinding)
        .filter(TwinExtensionBinding.twin_id == run.twin_id)
        .one()
    )
    binding.active = False
    with pytest.raises(ArchitectureDomainError) as binding_error:
        ResolvedArchitectureService(db_session).persist(
            run=run,
            raw_architecture=architecture,
            linked_documents=linked_architecture_fixture_documents(),
        )
    assert binding_error.value.code == "ARCH_RESOLUTION_REFERENCE_MISMATCH"


def test_fixture_gated_successful_run_ingestion_is_atomic(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    result, specification, _ = calculation_result_and_contracts()

    persisted = CostCalculationRunService(db_session).persist_successful_run(
        result,
        specification,
        architecture,
        run=run,
        catalog_context=catalog_context(),
        linked_architecture_documents=(
            linked_architecture_fixture_documents()
        ),
    )

    assert persisted.status == "succeeded"
    assert persisted.deployment_compatibility_status == "ready"
    assert persisted.architecture_compatibility_status == "ready"
    assert persisted.resolved_architecture is not None


def test_invalid_fixture_ingestion_persists_only_failed_run(db_session):
    _user, _twin, _config, run, architecture = _state(db_session)
    result, specification, _ = calculation_result_and_contracts()
    architecture["content_digest"] = "sha256:" + ("0" * 64)
    optimizer_config_id = run.optimizer_config_id
    run.optimizer_config = None
    run.optimizer_config_id = optimizer_config_id
    db_session.expunge(run)
    db_session.commit()
    db_session.add(run)

    with pytest.raises(ArchitectureDomainError):
        CostCalculationRunService(db_session).persist_successful_run(
            result,
            specification,
            architecture,
            run=run,
            catalog_context=catalog_context(),
            linked_architecture_documents=(
                linked_architecture_fixture_documents()
            ),
        )

    failed = db_session.get(CostCalculationRun, run.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.architecture_compatibility_status == "legacy_not_resolvable"
    assert failed.resolved_architecture is None
    assert (
        db_session.query(ResolvedTwinArchitectureRecord).count() == 0
    )
    audit = db_session.query(ArchitectureAuditEvent).one()
    assert audit.action == "resolution.persistence"
    assert audit.outcome == "rejected"
    assert audit.result_code == "ARCH_RESOLUTION_DIGEST_MISMATCH"
