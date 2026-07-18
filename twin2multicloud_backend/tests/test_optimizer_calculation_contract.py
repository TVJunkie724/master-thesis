"""Cross-route contract tests for canonical optimizer calculation parameters."""

from copy import deepcopy

import pytest

from src.schemas.optimizer_calculation import OptimizerCalculationParams


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
    assert selection["properties"]["resolved_deployment_specification"] == {
        "$ref": "#/components/schemas/ResolvedDeploymentSpecification"
    }
    assert "resolved_deployment_specification" in selection["required"]

    specification = components["ResolvedDeploymentSpecification"]
    assert specification["additionalProperties"] is False
    assert specification["properties"]["schema_version"]["const"] == (
        "resolved-deployment-specification.v1"
    )
    assert specification["properties"]["currency"]["const"] == "USD"
