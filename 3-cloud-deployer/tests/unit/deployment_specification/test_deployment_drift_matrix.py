"""Cross-provider deployment-specification drift tests."""

from __future__ import annotations

from itertools import product

import pytest

from src.deployment_specification import (
    calculate_digest,
    translate_deployment_tfvars,
    validate_deployment_manifest,
)
from tests.utils.deployment_specification import (
    build_specification_for_path,
    deployment_manifest,
    load_specification,
    load_verification_matrix,
    provider_config_for_specification,
)


MATRIX = load_verification_matrix()
PROVIDERS = tuple(MATRIX["providers"])


def _expected_targets(specification: dict) -> dict[str, str | int | bool]:
    expected: dict[str, str | int | bool] = {}
    by_component = MATRIX["expected_targets_by_component"]
    for component in specification["components"]:
        for target, value in by_component.get(
            component["component_id"], {}
        ).items():
            previous = expected.setdefault(target, value)
            assert previous == value
    return dict(sorted(expected.items()))


def _validated_tfvars(
    specification: dict,
) -> dict[str, str | int | bool]:
    providers = provider_config_for_specification(specification)
    validated = validate_deployment_manifest(
        deployment_manifest(specification, providers=providers),
        providers,
    )
    return dict(translate_deployment_tfvars(validated.specification))


@pytest.mark.parametrize(
    "path_case",
    MATRIX["representative_paths"],
    ids=lambda case: case["id"],
)
def test_representative_paths_translate_exact_matrix_targets(path_case):
    if path_case["fixture"]:
        specification = load_specification(path_case["fixture"])
    else:
        specification = build_specification_for_path(path_case["providers"])

    assert _validated_tfvars(specification) == _expected_targets(specification)


@pytest.mark.parametrize(
    ("hot_provider", "cool_provider", "archive_provider"),
    tuple(product(PROVIDERS, repeat=3)),
)
def test_all_storage_paths_preserve_source_runtime_and_receiver_glue(
    hot_provider,
    cool_provider,
    archive_provider,
):
    provider_by_slot = {
        "l1_ingestion": "aws",
        "l2_processing": "aws",
        "l3_hot_storage": hot_provider,
        "l3_cool_storage": cool_provider,
        "l3_archive_storage": archive_provider,
        "l4_twin_state": "aws",
        "l5_visualization": "aws",
    }
    specification = build_specification_for_path(provider_by_slot)
    component_ids = [
        component["component_id"] for component in specification["components"]
    ]

    expected_transitions = [
        transition["runtime_component_by_source"][
            provider_by_slot[transition["source_slot"]]
        ]
        for transition in MATRIX["storage_transitions"]
    ]
    actual_transitions = [
        component["component_id"]
        for component in specification["components"]
        if component["slot_id"] == "transition_runtime"
    ]
    assert actual_transitions == expected_transitions

    required_receivers = {
        provider_by_slot[target]
        for source, target in (
            ("l1_ingestion", "l2_processing"),
            ("l2_processing", "l3_hot_storage"),
            ("l3_hot_storage", "l3_cool_storage"),
            ("l3_cool_storage", "l3_archive_storage"),
            ("l4_twin_state", "l3_hot_storage"),
        )
        if provider_by_slot[source] != provider_by_slot[target]
    }
    expected_glue = [
        MATRIX["glue_component_by_receiver"][provider]
        for provider in PROVIDERS
        if provider in required_receivers
    ]
    actual_glue = [
        component["component_id"]
        for component in specification["components"]
        if component["slot_id"] == "cross_cloud_glue"
    ]
    assert actual_glue == expected_glue
    assert len(component_ids) == len(set(component_ids))
    assert _validated_tfvars(specification) == _expected_targets(specification)


@pytest.mark.parametrize(
    "case",
    MATRIX["azure_iot_hub_cases"],
    ids=lambda case: case["id"],
)
def test_azure_iot_hub_tiers_reach_tfvars_without_coercion(case):
    specification = load_specification("all-azure.json")
    for component in specification["components"]:
        if component["component_id"] != "l1.azure.iot_hub":
            continue
        for dimension in component["dimensions"]:
            target = dimension.get("terraform_target")
            if target == "azure_iot_hub_sku":
                dimension["value"] = case["expected_sku"]
            if target == "azure_iot_hub_capacity":
                dimension["value"] = case["expected_capacity"]
    specification["digest"] = calculate_digest(specification)

    translated = _validated_tfvars(specification)

    assert translated["azure_iot_hub_sku"] == case["expected_sku"]
    assert translated["azure_iot_hub_capacity"] == case["expected_capacity"]


def test_evidence_dimensions_never_become_terraform_variables():
    specification = build_specification_for_path(
        next(
            case["providers"]
            for case in MATRIX["representative_paths"]
            if case["id"] == "mixed"
        )
    )
    translated = _validated_tfvars(specification)

    deployable_targets = {
        dimension["terraform_target"]
        for component in specification["components"]
        for dimension in component["dimensions"]
        if dimension["classification"] == "deployable_selection"
    }
    evidence_dimensions = {
        dimension["dimension_id"]
        for component in specification["components"]
        for dimension in component["dimensions"]
        if dimension["classification"] != "deployable_selection"
    }

    assert set(translated) == deployable_targets
    assert set(translated).isdisjoint(evidence_dimensions)
