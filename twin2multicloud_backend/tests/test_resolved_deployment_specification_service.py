import copy
import json
from types import SimpleNamespace

import pytest

from src.services.resolved_deployment_specification_service import (
    V2_CONTRACT_ROOT,
    ResolvedDeploymentSpecificationError,
    calculate_digest,
    validate_resolved_deployment_specification,
)
from src.services.cost_calculation_run_service import (
    validate_persisted_run_deployment_specification,
)
from src.services.errors import CostCalculationRunSelectionError
from tests.pricing_catalog_test_data import catalog_context
from tests.resolved_deployment_specification_test_data import (
    build_resolved_deployment_specification,
)


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
ALL_AWS_PATH = {
    "l1": "AWS",
    "l2": "AWS",
    "l3_hot": "AWS",
    "l3_cool": "AWS",
    "l3_archive": "AWS",
    "l4": "AWS",
    "l5": "AWS",
}


def _result_and_specification():
    result = {
        "optimization_profile_id": "cost_minimization_v1",
        "calculation_strategy_id": "cost_calculation_v2",
        "optimizationProfile": {
            "profile_version": "2026.06.08",
            "pricing_registry_version": "2026.07.17",
        },
        "calculationStrategy": {
            "formula_set_id": "cost_formula_set_v1",
            "workload_contract_id": "digital_twin_workload_v1",
        },
        "calculationResult": {
            "L1": "AWS",
            "L2": "AWS",
            "L3": {"Hot": "AWS", "Cool": "AWS", "Archive": "AWS"},
            "L4": "AWS",
            "L5": "AWS",
        },
        "pricingCatalogs": catalog_context().to_http_dict(),
    }
    specification = build_resolved_deployment_specification(
        result,
        calculation_run_id=RUN_ID,
        pricing_catalogs=result["pricingCatalogs"],
    )
    result["resolvedDeploymentSpecification"] = specification
    return result, specification


def _validate(specification, result=None, path=None):
    result = result or _result_and_specification()[0]
    return validate_resolved_deployment_specification(
        specification,
        expected_run_id=RUN_ID,
        expected_cheapest_path=path or ALL_AWS_PATH,
        expected_catalog_context=catalog_context(),
        expected_result=result,
    )


def _v2_result_and_specification():
    specification = json.loads(
        (
            V2_CONTRACT_ROOT
            / "fixtures"
            / "valid"
            / "single-cloud-aws-small.json"
        ).read_text(encoding="utf-8")
    )
    architecture = json.loads(
        (
            V2_CONTRACT_ROOT.parents[1]
            / "architecture-profiles"
            / "v2"
            / "fixtures"
            / "valid"
            / "single-cloud-aws-small-resolved.json"
        ).read_text(encoding="utf-8")
    )
    specification["calculation_run_id"] = RUN_ID
    specification["readiness"] = {
        "status": "deployment_ready",
        "blocking_gate_ids": [],
    }
    specification["optimization_context"]["pricing_evidence_refs"] = [
        {
            "provider": "aws",
            "digest": catalog_context().catalogs["aws"].content_digest,
        }
    ]
    specification["digest"] = calculate_digest(specification)
    architecture["deployment_specification_ref"] = {
        "schema_version": "resolved-deployment-specification.v2",
        "calculation_run_id": RUN_ID,
        "digest": specification["digest"],
    }
    architecture["pricing_evidence_refs"][0]["digest"] = (
        catalog_context().catalogs["aws"].content_digest
    )
    return {
        "currency": specification["currency"],
        "resolvedTwinArchitecture": architecture,
    }, specification


def test_valid_specification_is_canonicalized_and_bound():
    result, specification = _result_and_specification()

    validated = _validate(specification, result)

    assert validated.specification == specification
    assert validated.digest == specification["digest"]
    assert validated.canonical_json.startswith('{"architecture_profile"')


def test_digest_tampering_is_rejected():
    _, specification = _result_and_specification()
    specification["digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(
        ResolvedDeploymentSpecificationError,
        match="digest does not match",
    ) as exc_info:
        _validate(specification)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH"


def test_secret_like_field_is_rejected_before_schema_output():
    _, specification = _result_and_specification()
    specification["client_secret"] = "must-not-leak"

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_SECRET_FIELD"
    assert "must-not-leak" not in str(exc_info.value)


def test_unknown_component_is_rejected_after_valid_digest():
    _, specification = _result_and_specification()
    specification["components"][0]["component_id"] = "l1.aws.unknown"
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"


def test_unknown_dimension_value_is_rejected_after_valid_digest():
    _, specification = _result_and_specification()
    specification["components"][0]["dimensions"][0]["value"] = "unknown"
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"


def test_selected_provider_path_mismatch_is_rejected():
    _, specification = _result_and_specification()
    mismatched_path = {**ALL_AWS_PATH, "l1": "Azure"}

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification, path=mismatched_path)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"


def test_transition_runtime_must_match_source_storage_provider():
    result, specification = _result_and_specification()
    alternate_result = copy.deepcopy(result)
    alternate_result["calculationResult"]["L3"]["Hot"] = "Azure"
    alternate_specification = build_resolved_deployment_specification(
        alternate_result,
        calculation_run_id=RUN_ID,
        pricing_catalogs=result["pricingCatalogs"],
    )
    alternate_runtime = next(
        component
        for component in alternate_specification["components"]
        if component["component_id"]
        == "transition.l3_hot_to_l3_cool.azure.runtime"
    )
    runtime_index = next(
        index
        for index, component in enumerate(specification["components"])
        if component["component_id"]
        == "transition.l3_hot_to_l3_cool.aws.runtime"
    )
    specification["components"][runtime_index] = alternate_runtime
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification, result)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"
    assert exc_info.value.field.endswith("transition_runtime")


def test_transition_runtime_order_is_canonical():
    result, specification = _result_and_specification()
    indexes = [
        index
        for index, component in enumerate(specification["components"])
        if component["slot_id"] == "transition_runtime"
    ]
    first, second = indexes
    specification["components"][first], specification["components"][second] = (
        specification["components"][second],
        specification["components"][first],
    )
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification, result)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"
    assert exc_info.value.field.endswith("transition_runtime")


def test_catalog_reference_mismatch_is_rejected_after_valid_digest():
    _, specification = _result_and_specification()
    specification["optimization_context"]["catalog_references"]["aws"][
        "content_digest"
    ] = "sha256:" + ("f" * 64)
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_CATALOG_MISMATCH"


def test_strategy_context_mismatch_is_rejected_after_valid_digest():
    result, specification = _result_and_specification()
    result = copy.deepcopy(result)
    result["calculationStrategy"]["formula_set_id"] = "other_formula_set"

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification, result)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH"


def test_excessive_nesting_is_rejected_before_canonical_persistence():
    _, specification = _result_and_specification()
    nested = {}
    cursor = nested
    for index in range(20):
        cursor[f"level_{index}"] = {}
        cursor = cursor[f"level_{index}"]
    specification["unexpected"] = nested

    with pytest.raises(ResolvedDeploymentSpecificationError) as exc_info:
        _validate(specification)

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_TOO_DEEP"


def test_valid_five_layer_v2_specification_is_canonicalized_and_bound():
    result, specification = _v2_result_and_specification()

    validated = _validate(specification, result)

    assert validated.schema_version == "resolved-deployment-specification.v2"
    assert validated.digest == specification["digest"]
    assert validated.specification["readiness"]["status"] == "deployment_ready"


def test_five_layer_v2_offline_evidence_and_eur_are_canonicalized():
    result, specification = _v2_result_and_specification()
    specification["currency"] = "EUR"
    specification["readiness"] = {
        "status": "offline_contract_fixture",
        "blocking_gate_ids": ["gate.live-capacity.aws.reader-latency-and-quota"],
    }
    specification["digest"] = calculate_digest(specification)
    result["currency"] = "EUR"
    result["resolvedTwinArchitecture"]["resolution_status"] = (
        "offline_contract_fixture"
    )
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]

    validated = _validate(specification, result)

    assert validated.specification["currency"] == "EUR"
    assert validated.specification["readiness"] == specification["readiness"]


def test_five_layer_v2_offline_evidence_requires_a_real_blocker():
    result, specification = _v2_result_and_specification()
    specification["readiness"] = {
        "status": "offline_contract_fixture",
        "blocking_gate_ids": [],
    }
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_INVALID"


def test_five_layer_v2_offline_evidence_cannot_be_selected_for_deployment():
    result, specification = _v2_result_and_specification()
    specification["readiness"] = {
        "status": "offline_contract_fixture",
        "blocking_gate_ids": ["gate.live-capacity.aws.reader-latency-and-quota"],
    }
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["resolution_status"] = (
        "offline_contract_fixture"
    )
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]
    result["resolvedDeploymentSpecification"] = specification
    run = SimpleNamespace(
        deployment_compatibility_status="ready",
        deployment_specification_json=json.dumps(specification),
        deployment_specification_digest=specification["digest"],
        deployment_specification_version=specification["schema_version"],
        result_summary_json=json.dumps(result),
        pricing_catalog_context_json=json.dumps(catalog_context().to_http_dict()),
        cheapest_path_json=json.dumps(ALL_AWS_PATH),
        id=RUN_ID,
    )

    with pytest.raises(CostCalculationRunSelectionError) as raised:
        validate_persisted_run_deployment_specification(run)

    assert raised.value.error_code == "DEPLOYMENT_CAPACITY_EVIDENCE_PENDING"


def test_five_layer_v2_rejects_catalog_digest_mismatch():
    result, specification = _v2_result_and_specification()
    specification["optimization_context"]["pricing_evidence_refs"][0][
        "digest"
    ] = "sha256:" + ("f" * 64)
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_CATALOG_MISMATCH"


def test_five_layer_v2_rejects_unknown_component_after_valid_digest():
    result, specification = _v2_result_and_specification()
    specification["component_selections"][0][
        "implementation_component_id"
    ] = "aws.unknown-service"
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"


def test_five_layer_v2_rejects_missing_dimension_binding():
    result, specification = _v2_result_and_specification()
    specification["bindings"].pop()
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"


def test_five_layer_v2_rejects_component_moved_to_another_assignment():
    result, specification = _v2_result_and_specification()
    selection = specification["component_selections"][0]
    selection["logical_component_id"] = "component.cool-storage"
    selection["architecture_assignment_id"] = "assignment.cool-storage"
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"][
        "digest"
    ] = specification["digest"]

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"
