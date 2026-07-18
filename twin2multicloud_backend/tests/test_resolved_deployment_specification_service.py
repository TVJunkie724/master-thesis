import copy

import pytest

from src.services.resolved_deployment_specification_service import (
    ResolvedDeploymentSpecificationError,
    calculate_digest,
    validate_resolved_deployment_specification,
)
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
