import copy
import json
from types import SimpleNamespace

import pytest

from src.services.cost_calculation_run_service import (
    validate_persisted_run_deployment_specification,
)
from src.services.errors import CostCalculationRunSelectionError
from src.services.resolved_deployment_specification_service import (
    V2_CONTRACT_ROOT,
    ResolvedDeploymentSpecificationError,
    calculate_digest,
    validate_resolved_deployment_specification,
)
from tests.pricing_catalog_test_data import catalog_context


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
LOGICAL_TO_PATH = {
    "component.ingestion": "l1",
    "component.processing": "l2",
    "component.hot-storage": "l3_hot",
    "component.cool-storage": "l3_cool",
    "component.archive-storage": "l3_archive",
    "component.twin-state": "l4",
    "component.visualization": "l5",
    "component.eventing": "eventing",
}


def _documents(*, ready: bool = True, currency: str = "USD"):
    specification = json.loads(
        (
            V2_CONTRACT_ROOT
            / "fixtures"
            / "valid"
            / "six-layer-aws-azure-eventing-small.json"
        ).read_text(encoding="utf-8")
    )
    architecture = json.loads(
        (
            V2_CONTRACT_ROOT.parents[1]
            / "architecture-profiles"
            / "v2"
            / "fixtures"
            / "valid"
            / "six-layer-aws-azure-eventing-small-resolved.json"
        ).read_text(encoding="utf-8")
    )
    specification["calculation_run_id"] = RUN_ID
    specification["currency"] = currency
    specification["readiness"] = (
        {"status": "deployment_ready", "blocking_gate_ids": []}
        if ready
        else {
            "status": "offline_contract_fixture",
            "blocking_gate_ids": ["gate.live-capacity.aws.reader-latency-and-quota"],
        }
    )
    providers = sorted(
        {item["provider"] for item in specification["component_selections"]}
    )
    specification["optimization_context"]["pricing_evidence_refs"] = [
        {
            "provider": provider,
            "digest": catalog_context().catalogs[provider].content_digest,
        }
        for provider in providers
    ]
    specification["digest"] = calculate_digest(specification)

    architecture["calculation_run_id"] = RUN_ID
    architecture["resolution_status"] = (
        "publishable" if ready else "offline_contract_fixture"
    )
    architecture["deployment_specification_ref"] = {
        "schema_version": "resolved-deployment-specification.v2",
        "calculation_run_id": RUN_ID,
        "digest": specification["digest"],
    }
    path = {
        LOGICAL_TO_PATH[item["logical_component_id"]]: item["provider"].upper()
        for item in architecture["component_assignments"]
    }
    result = {
        "currency": currency,
        "resolvedTwinArchitecture": architecture,
        "resolvedDeploymentSpecification": specification,
    }
    return result, specification, path


def _validate(specification, result, path):
    return validate_resolved_deployment_specification(
        specification,
        expected_run_id=RUN_ID,
        expected_cheapest_path=path,
        expected_catalog_context=catalog_context(),
        expected_result=result,
    )


def test_canonical_six_layer_specification_is_bound():
    result, specification, path = _documents()

    validated = _validate(specification, result, path)

    assert validated.schema_version == "resolved-deployment-specification.v2"
    assert validated.digest == specification["digest"]
    assert validated.specification["architecture_profile_ref"] == {
        "id": "six-layer-eventing",
        "version": "1",
        "digest": specification["architecture_profile_ref"]["digest"],
    }


def test_offline_evidence_and_eur_are_canonicalized():
    result, specification, path = _documents(ready=False, currency="EUR")

    validated = _validate(specification, result, path)

    assert validated.specification["currency"] == "EUR"
    assert validated.specification["readiness"]["status"] == (
        "offline_contract_fixture"
    )


def test_digest_tampering_is_rejected():
    result, specification, path = _documents()
    specification["digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result, path)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH"


def test_secret_like_field_is_rejected_without_echoing_value():
    result, specification, path = _documents()
    specification["client_secret"] = "must-not-leak"

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result, path)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_SECRET_FIELD"
    assert "must-not-leak" not in str(raised.value)


def test_unknown_component_is_rejected_after_valid_digest():
    result, specification, path = _documents()
    specification["component_selections"][0]["implementation_component_id"] = (
        "aws.unknown-service"
    )
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"]["digest"] = (
        specification["digest"]
    )

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result, path)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"


def test_missing_dimension_binding_is_rejected():
    result, specification, path = _documents()
    specification["bindings"].pop()
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"]["digest"] = (
        specification["digest"]
    )

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result, path)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"


def test_pricing_evidence_mismatch_is_rejected():
    result, specification, path = _documents()
    specification["optimization_context"]["pricing_evidence_refs"][0]["digest"] = (
        "sha256:" + ("f" * 64)
    )
    specification["digest"] = calculate_digest(specification)
    result["resolvedTwinArchitecture"]["deployment_specification_ref"]["digest"] = (
        specification["digest"]
    )

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(specification, result, path)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_CATALOG_MISMATCH"


def test_offline_evidence_cannot_be_selected_for_deployment():
    result, specification, path = _documents(ready=False)
    run = SimpleNamespace(
        deployment_compatibility_status="ready",
        deployment_specification_json=json.dumps(specification),
        deployment_specification_digest=specification["digest"],
        deployment_specification_version=specification["schema_version"],
        result_summary_json=json.dumps(result),
        pricing_catalog_context_json=json.dumps(catalog_context().to_http_dict()),
        cheapest_path_json=json.dumps(path),
        id=RUN_ID,
    )

    with pytest.raises(CostCalculationRunSelectionError) as raised:
        validate_persisted_run_deployment_specification(run)

    assert raised.value.error_code == "DEPLOYMENT_CAPACITY_EVIDENCE_PENDING"


def test_v1_contract_is_rejected():
    result, specification, path = _documents()
    legacy = copy.deepcopy(specification)
    legacy["schema_version"] = "resolved-deployment-specification.v1"

    with pytest.raises(ResolvedDeploymentSpecificationError) as raised:
        _validate(legacy, result, path)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_VERSION_UNSUPPORTED"
