"""Cross-route contracts for the closed Six-layer workload."""

import json
from copy import deepcopy

import pytest
from pydantic import TypeAdapter

from src.schemas.optimizer_calculation import (
    SIX_LAYER_WORKLOAD_ROOT,
    OptimizerCalculationParams,
)
from src.schemas.resolved_deployment_specification import (
    ResolvedDeploymentSpecificationDocument,
    ResolvedDeploymentSpecificationV2,
)
from src.services.resolved_deployment_specification_service import V2_CONTRACT_ROOT


def _workload() -> dict:
    return json.loads(
        (SIX_LAYER_WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json").read_text(
            encoding="utf-8"
        )
    )


def _deployment_specification() -> dict:
    return json.loads(
        (
            V2_CONTRACT_ROOT
            / "fixtures"
            / "valid"
            / "six-layer-aws-azure-eventing-small.json"
        ).read_text(encoding="utf-8")
    )


def _references_component(schema: dict, node: object, component_name: str) -> bool:
    pending = [node]
    visited_refs: set[str] = set()
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            ref = current.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                referenced_name = ref.rsplit("/", 1)[-1]
                if referenced_name == component_name:
                    return True
                if ref not in visited_refs:
                    visited_refs.add(ref)
                    pending.append(
                        schema["components"]["schemas"].get(referenced_name, {})
                    )
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return False


def test_six_layer_deployment_read_model_round_trips_without_shape_loss():
    source = _deployment_specification()
    parsed = TypeAdapter(ResolvedDeploymentSpecificationDocument).validate_python(
        source
    )

    assert isinstance(parsed, ResolvedDeploymentSpecificationV2)
    assert parsed.model_dump(mode="json", exclude_none=True) == source


def test_run_params_accept_only_frozen_scenarios_and_supported_currency():
    payload = _workload()
    parsed = OptimizerCalculationParams.model_validate(payload)
    euro = OptimizerCalculationParams.model_validate({**payload, "currency": "EUR"})
    mutated = deepcopy(payload)
    mutated["numberOfDevices"] = 101

    assert parsed.schemaVersion == "six-layer-workload.v1"
    assert euro.currency == "EUR"
    with pytest.raises(ValueError, match="immutable Small, Medium, or Large"):
        OptimizerCalculationParams.model_validate(mutated)


@pytest.mark.parametrize(
    "removed_field",
    (
        "useEventChecking",
        "needs3DModel",
        "integrateErrorHandling",
        "averageDigitalTwinQueryUnitsPerQuery",
    ),
)
def test_removed_product_fields_are_rejected(removed_field):
    with pytest.raises(ValueError):
        OptimizerCalculationParams.model_validate({**_workload(), removed_field: True})


@pytest.mark.parametrize(
    ("method", "path", "body_factory"),
    [
        (
            "put",
            "/twins/unused/optimizer-config/params",
            lambda params: {"params": params},
        ),
        (
            "post",
            "/twins/unused/optimizer-runs",
            lambda params: {"params": params},
        ),
        (
            "put",
            "/twins/unused/config",
            lambda params: {"optimizer_params": params},
        ),
    ],
)
def test_architecture_enrichment_cannot_be_client_authored(
    authenticated_client,
    method,
    path,
    body_factory,
):
    client, headers = authenticated_client
    params = {
        **_workload(),
        "architectureProfile": {
            "profileId": "six-layer-eventing",
            "profileVersion": "1",
            "contentDigest": "sha256:" + ("0" * 64),
        },
        "extensionBindings": [],
    }

    response = getattr(client, method)(
        path,
        json=body_factory(params),
        headers=headers,
    )

    assert response.status_code == 422
    assert {error["loc"][-1] for error in response.json()["detail"]} == {
        "architectureProfile",
        "extensionBindings",
    }


def test_openapi_reuses_closed_workload_for_all_write_paths(authenticated_client):
    client, headers = authenticated_client
    schema = client.get("/openapi.json", headers=headers).json()
    paths = (
        "/twins/{twin_id}/optimizer-config/params",
        "/twins/{twin_id}/optimizer-runs/",
        "/twins/{twin_id}/config/",
    )
    for path in paths:
        assert _references_component(
            schema,
            schema["paths"][path],
            "OptimizerCalculationParams",
        ), path

    component = schema["components"]["schemas"]["OptimizerCalculationParams"]
    assert component["additionalProperties"] is False
    assert component["properties"]["schemaVersion"]["const"] == (
        "six-layer-workload.v1"
    )
    assert "optimizationProfileId" not in component["properties"]
    assert "architectureProfile" not in component["properties"]
    assert "extensionBindings" not in component["properties"]
    assert "integrateErrorHandling" not in component["properties"]


def test_openapi_exposes_only_rds_v2_as_read_only_contract(authenticated_client):
    client, headers = authenticated_client
    schema = client.get("/openapi.json", headers=headers).json()
    components = schema["components"]["schemas"]

    create_properties = components["CostCalculationRunCreate"]["properties"]
    assert "resolved_deployment_specification" not in create_properties
    summary = components["CostCalculationRunSummaryResponse"]
    assert summary["properties"]["deployment_compatibility_status"]["enum"] == [
        "ready",
        "unavailable",
    ]

    detail_specification = components["CostCalculationRunDetailResponse"]["properties"][
        "resolved_deployment_specification"
    ]
    assert _references_component(
        schema,
        detail_specification,
        "ResolvedDeploymentSpecificationV2",
    )
    assert "ResolvedDeploymentSpecification" not in components
    specification = components["ResolvedDeploymentSpecificationV2"]
    assert specification["additionalProperties"] is False
    assert specification["properties"]["schema_version"]["const"] == (
        "resolved-deployment-specification.v2"
    )
    assert {
        "fixed_dimensions",
        "component_selections",
        "bindings",
        "readiness",
    }.issubset(specification["required"])
