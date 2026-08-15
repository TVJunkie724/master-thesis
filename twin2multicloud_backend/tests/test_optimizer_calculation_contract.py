"""Cross-route contract tests for canonical optimizer calculation parameters."""

from copy import deepcopy
import json

import pytest
from pydantic import TypeAdapter

from src.schemas.optimizer_calculation import (
    FIVE_LAYER_V2_WORKLOAD_ROOT,
    FiveLayerV2OptimizerCalculationParams,
    OptimizerCalculationParams,
)
from src.schemas.resolved_deployment_specification import (
    ResolvedDeploymentSpecificationDocument,
    ResolvedDeploymentSpecificationV2,
)
from src.services.resolved_deployment_specification_service import (
    V2_CONTRACT_ROOT,
)


def _five_layer_v2_workload() -> dict:
    return json.loads(
        (
            FIVE_LAYER_V2_WORKLOAD_ROOT
            / "fixtures"
            / "valid"
            / "core-small.json"
        ).read_text(encoding="utf-8")
    )


def _five_layer_v2_deployment_specification() -> dict:
    return json.loads(
        (
            V2_CONTRACT_ROOT
            / "fixtures"
            / "valid"
            / "single-cloud-aws-small.json"
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


def test_five_layer_v2_deployment_read_model_round_trips_without_shape_loss():
    source = _five_layer_v2_deployment_specification()

    parsed = TypeAdapter(ResolvedDeploymentSpecificationDocument).validate_python(
        source
    )

    assert isinstance(parsed, ResolvedDeploymentSpecificationV2)
    assert parsed.model_dump(mode="json", exclude_none=True) == source


def test_omitted_adt_assumptions_remain_omitted_only_for_downstream_payload(
    sample_calc_params,
):
    source = {
        key: value
        for key, value in sample_calc_params.items()
        if key
        not in {
            "averageDigitalTwinQueryUnitsPerQuery",
            "averageDigitalTwinQueryResponseSizeInKb",
        }
    }

    params = OptimizerCalculationParams.model_validate(source)

    assert "averageDigitalTwinQueryUnitsPerQuery" not in params.to_optimizer_payload()
    assert (
        "averageDigitalTwinQueryResponseSizeInKb" not in params.to_optimizer_payload()
    )
    assert params.to_persisted_payload()["averageDigitalTwinQueryUnitsPerQuery"] == 1
    assert params.to_persisted_payload()["averageDigitalTwinQueryResponseSizeInKb"] == 1


@pytest.mark.parametrize(
    ("method", "path", "body_factory"),
    [
        ("put", "/optimizer/calculate", lambda params: params),
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
@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("averageDigitalTwinQueryUnitsPerQuery", 0),
        ("averageDigitalTwinQueryResponseSizeInKb", 0),
        ("averageDigitalTwinQueryUnitsPerQuery", "not-a-number"),
        ("averageDigitalTwinQueryResponseSizeInKb", "not-a-number"),
        ("averageDigitalTwinQueryUnitsPerQuery", "1.0"),
        ("averageDigitalTwinQueryResponseSizeInKb", "1.0"),
    ],
)
def test_every_management_write_path_rejects_invalid_adt_assumptions(
    authenticated_client,
    sample_calc_params,
    method,
    path,
    body_factory,
    field,
    invalid_value,
):
    client, headers = authenticated_client
    params = deepcopy(sample_calc_params)
    params[field] = invalid_value

    response = getattr(client, method)(
        path,
        json=body_factory(params),
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "body_factory"),
    [
        ("put", "/optimizer/calculate", lambda params: params),
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
def test_every_management_write_path_rejects_unsupported_error_handling(
    authenticated_client,
    sample_calc_params,
    method,
    path,
    body_factory,
):
    client, headers = authenticated_client
    params = deepcopy(sample_calc_params)
    params["integrateErrorHandling"] = True

    response = getattr(client, method)(
        path,
        json=body_factory(params),
        headers=headers,
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "integrateErrorHandling"
        and error["type"] == "UNSUPPORTED_ERROR_HANDLING_TOPOLOGY"
        for error in response.json()["detail"]
    )


def test_optimizer_params_accept_false_or_omitted_error_handling(
    sample_calc_params,
):
    explicit = OptimizerCalculationParams.model_validate(sample_calc_params)
    omitted_payload = deepcopy(sample_calc_params)
    omitted_payload.pop("integrateErrorHandling")
    omitted = OptimizerCalculationParams.model_validate(omitted_payload)

    assert explicit.integrateErrorHandling is False
    assert omitted.integrateErrorHandling is False


def test_five_layer_v2_run_params_accept_only_frozen_scenarios():
    payload = _five_layer_v2_workload()

    parsed = FiveLayerV2OptimizerCalculationParams.model_validate(payload)
    euro = FiveLayerV2OptimizerCalculationParams.model_validate(
        {**payload, "currency": "EUR"}
    )
    mutated = deepcopy(payload)
    mutated["numberOfDevices"] = 101

    assert parsed.optimizationProfileId == "cost-minimization-v2"
    assert euro.currency == "EUR"
    assert euro.eventingScenarioId == parsed.eventingScenarioId
    with pytest.raises(ValueError, match="immutable Small, Medium, or Large"):
        FiveLayerV2OptimizerCalculationParams.model_validate(mutated)


def test_five_layer_v2_run_params_reject_legacy_event_and_scene_fields():
    payload = {
        **_five_layer_v2_workload(),
        "useEventChecking": True,
        "needs3DModel": False,
    }

    with pytest.raises(ValueError):
        FiveLayerV2OptimizerCalculationParams.model_validate(payload)


@pytest.mark.parametrize(
    ("method", "path", "body_factory"),
    [
        ("put", "/optimizer/calculate", lambda params: params),
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
def test_architecture_request_enrichment_cannot_be_client_authored(
    authenticated_client,
    sample_calc_params,
    method,
    path,
    body_factory,
):
    client, headers = authenticated_client
    params = deepcopy(sample_calc_params)
    params["architectureProfile"] = {
        "profileId": "five-layer-baseline",
        "profileVersion": "1",
        "contentDigest": "sha256:" + ("0" * 64),
    }
    params["extensionBindings"] = []

    response = getattr(client, method)(
        path,
        json=body_factory(params),
        headers=headers,
    )

    assert response.status_code == 422
    rejected_fields = {
        error["loc"][-1] for error in response.json()["detail"]
    }
    assert rejected_fields == {
        "architectureProfile",
        "extensionBindings",
    }


def test_openapi_reuses_one_optimizer_parameter_schema_for_all_write_paths(
    authenticated_client,
):
    client, headers = authenticated_client

    schema = client.get("/openapi.json", headers=headers).json()
    paths = (
        "/optimizer/calculate",
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
    assert (
        component["properties"]["averageDigitalTwinQueryUnitsPerQuery"][
            "exclusiveMinimum"
        ]
        == 0
    )
    assert (
        component["properties"]["averageDigitalTwinQueryResponseSizeInKb"][
            "exclusiveMinimum"
        ]
        == 0
    )
    assert component["properties"]["integrateErrorHandling"]["const"] is False
    assert "architectureProfile" not in component["properties"]
    assert "extensionBindings" not in component["properties"]

    assert _references_component(
        schema,
        schema["paths"]["/twins/{twin_id}/optimizer-runs/"],
        "FiveLayerV2OptimizerCalculationParams",
    )


def test_openapi_exposes_only_server_owned_optimizer_result_writes(
    authenticated_client,
):
    client, headers = authenticated_client

    schema = client.get("/openapi.json", headers=headers).json()

    assert "/twins/{twin_id}/optimizer-config/result" not in schema["paths"]
    assert "/twins/{twin_id}/optimizer-runs/" in schema["paths"]
    assert (
        schema["paths"]["/twins/{twin_id}/optimizer-runs/"]["post"]["operationId"]
        == "createOptimizerRun"
    )
    twin_update = schema["components"]["schemas"]["TwinConfigUpdate"]
    assert twin_update["additionalProperties"] is False
    assert "optimizer_result" not in twin_update["properties"]


def test_openapi_exposes_deployment_specification_as_typed_read_only_contract(
    authenticated_client,
):
    client, headers = authenticated_client

    schema = client.get("/openapi.json", headers=headers).json()
    components = schema["components"]["schemas"]

    create_properties = components["CostCalculationRunCreate"]["properties"]
    assert "resolved_deployment_specification" not in create_properties
    assert "deployment_specification_digest" not in create_properties
    assert "deployment_compatibility_status" not in create_properties

    summary = components["CostCalculationRunSummaryResponse"]
    assert {
        "deployment_specification_digest",
        "deployment_specification_version",
        "deployment_compatibility_status",
    }.issubset(summary["properties"])
    assert summary["properties"]["deployment_compatibility_status"]["enum"] == [
        "ready",
        "legacy_not_deployable",
    ]

    detail_specification = components["CostCalculationRunDetailResponse"][
        "properties"
    ]["resolved_deployment_specification"]
    assert _references_component(
        schema,
        detail_specification,
        "ResolvedDeploymentSpecification",
    )

    selection = components["CostCalculationRunSelectResponse"]
    selection_specification = selection["properties"][
        "resolved_deployment_specification"
    ]
    assert selection_specification["discriminator"] == {
        "propertyName": "schema_version",
        "mapping": {
            "resolved-deployment-specification.v1": (
                "#/components/schemas/ResolvedDeploymentSpecification"
            ),
            "resolved-deployment-specification.v2": (
                "#/components/schemas/ResolvedDeploymentSpecificationV2"
            ),
        },
    }
    assert {
        item["$ref"] for item in selection_specification["oneOf"]
    } == {
        "#/components/schemas/ResolvedDeploymentSpecification",
        "#/components/schemas/ResolvedDeploymentSpecificationV2",
    }
    assert "resolved_deployment_specification" in selection["required"]

    specification = components["ResolvedDeploymentSpecification"]
    assert specification["additionalProperties"] is False
    assert specification["properties"]["schema_version"]["const"] == (
        "resolved-deployment-specification.v1"
    )
    assert specification["properties"]["currency"]["const"] == "USD"

    specification_v2 = components["ResolvedDeploymentSpecificationV2"]
    assert specification_v2["additionalProperties"] is False
    assert specification_v2["properties"]["schema_version"]["const"] == (
        "resolved-deployment-specification.v2"
    )
    assert set(specification_v2["properties"]["currency"]["enum"]) == {
        "USD",
        "EUR",
    }
    assert {
        "fixed_dimensions",
        "component_selections",
        "bindings",
        "readiness",
    }.issubset(specification_v2["required"])
