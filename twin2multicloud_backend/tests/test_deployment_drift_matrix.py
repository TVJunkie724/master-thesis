"""Management API continuity tests for resolved deployment selections."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from itertools import product
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.models.cost_calculation import CostCalculationRun
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.services.cost_calculation_run_service import (
    validate_persisted_run_deployment_specification,
)
from src.services.credential_resolution_service import DeploymentCredentials
from src.services.deployment_service import _build_deployment_manifest
from src.services.resolved_deployment_specification_service import (
    ResolvedDeploymentSpecificationError,
    calculate_digest,
    canonical_json,
    validate_resolved_deployment_specification,
)
from tests.pricing_catalog_test_data import catalog_context
from tests.resolved_deployment_specification_test_data import (
    build_resolved_deployment_specification,
)


CONTRACT_V1 = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)
MATRIX = json.loads(
    (CONTRACT_V1 / "verification-matrix.json").read_text(encoding="utf-8")
)
SLOT_TO_RESULT_PATH = {
    "l1_ingestion": ("L1",),
    "l2_processing": ("L2",),
    "l3_hot_storage": ("L3", "Hot"),
    "l3_cool_storage": ("L3", "Cool"),
    "l3_archive_storage": ("L3", "Archive"),
    "l4_twin_state": ("L4",),
    "l5_visualization": ("L5",),
}
SLOT_TO_CHEAPEST_PATH = {
    "l1_ingestion": "l1",
    "l2_processing": "l2",
    "l3_hot_storage": "l3_hot",
    "l3_cool_storage": "l3_cool",
    "l3_archive_storage": "l3_archive",
    "l4_twin_state": "l4",
    "l5_visualization": "l5",
}
SLOT_TO_DEPLOYER_KEY = {
    "l1_ingestion": "layer_1_provider",
    "l2_processing": "layer_2_provider",
    "l3_hot_storage": "layer_3_hot_provider",
    "l3_cool_storage": "layer_3_cold_provider",
    "l3_archive_storage": "layer_3_archive_provider",
    "l4_twin_state": "layer_4_provider",
    "l5_visualization": "layer_5_provider",
}
PROVIDER_LABELS = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
DEPLOYER_PROVIDER_IDS = {"aws": "aws", "azure": "azure", "gcp": "google"}
RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
VALID_FIXTURES = tuple(
    sorted((CONTRACT_V1 / "fixtures" / "valid").glob("*.json"))
)
INVALID_FIXTURES = tuple(
    sorted((CONTRACT_V1 / "fixtures" / "invalid").glob("*.json"))
)


def _result_for_path(providers_by_slot: dict[str, str]) -> dict:
    calculation_result = {
        "L1": PROVIDER_LABELS[providers_by_slot["l1_ingestion"]],
        "L2": PROVIDER_LABELS[providers_by_slot["l2_processing"]],
        "L3": {
            "Hot": PROVIDER_LABELS[providers_by_slot["l3_hot_storage"]],
            "Cool": PROVIDER_LABELS[providers_by_slot["l3_cool_storage"]],
            "Archive": PROVIDER_LABELS[
                providers_by_slot["l3_archive_storage"]
            ],
        },
        "L4": PROVIDER_LABELS[providers_by_slot["l4_twin_state"]],
        "L5": PROVIDER_LABELS[providers_by_slot["l5_visualization"]],
    }
    return {
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
        "calculationResult": calculation_result,
        "pricingCatalogs": catalog_context().to_http_dict(),
    }


def _cheapest_path(providers_by_slot: dict[str, str]) -> dict[str, str]:
    return {
        path_key: PROVIDER_LABELS[providers_by_slot[slot]]
        for slot, path_key in SLOT_TO_CHEAPEST_PATH.items()
    }


def _build_and_validate(
    providers_by_slot: dict[str, str],
    *,
    azure_iot_case: dict | None = None,
):
    result = _result_for_path(providers_by_slot)
    specification = build_resolved_deployment_specification(
        result,
        calculation_run_id=RUN_ID,
        pricing_catalogs=result["pricingCatalogs"],
    )
    if azure_iot_case is not None:
        iot_hub = next(
            component
            for component in specification["components"]
            if component["component_id"] == "l1.azure.iot_hub"
        )
        dimensions = {
            dimension["dimension_id"]: dimension
            for dimension in iot_hub["dimensions"]
        }
        dimensions["azure.iot_hub.sku"]["value"] = azure_iot_case[
            "expected_sku"
        ]
        dimensions["azure.iot_hub.capacity"]["value"] = azure_iot_case[
            "expected_capacity"
        ]
        specification["digest"] = calculate_digest(specification)
    result["resolvedDeploymentSpecification"] = specification

    validated = validate_resolved_deployment_specification(
        specification,
        expected_run_id=RUN_ID,
        expected_cheapest_path=_cheapest_path(providers_by_slot),
        expected_catalog_context=catalog_context(),
        expected_result=result,
    )
    return result, specification, validated


def _deployable_targets(specification: dict) -> dict[str, dict[str, object]]:
    return {
        component["component_id"]: {
            dimension["terraform_target"]: dimension["value"]
            for dimension in component["dimensions"]
            if "terraform_target" in dimension
        }
        for component in specification["components"]
        if any("terraform_target" in item for item in component["dimensions"])
    }


def _fixture_validation_context(specification: dict):
    optimization_context = specification["optimization_context"]
    providers_by_slot = {}
    for component in specification["components"]:
        if component["slot_id"] in SLOT_TO_CHEAPEST_PATH:
            providers_by_slot.setdefault(
                component["slot_id"],
                component["provider"],
            )
    cheapest_path = {
        SLOT_TO_CHEAPEST_PATH[slot]: PROVIDER_LABELS[provider]
        for slot, provider in providers_by_slot.items()
    }
    expected_result = {
        "optimization_profile_id": optimization_context[
            "optimization_profile_id"
        ],
        "calculation_strategy_id": optimization_context[
            "calculation_strategy_id"
        ],
        "optimizationProfile": {
            "profile_version": optimization_context[
                "optimization_profile_version"
            ],
            "pricing_registry_version": optimization_context[
                "pricing_registry_version"
            ],
        },
        "calculationStrategy": {
            "formula_set_id": optimization_context["formula_set_id"],
            "workload_contract_id": optimization_context[
                "workload_contract_id"
            ],
        },
    }
    catalog_context_value = SimpleNamespace(
        catalogs={
            provider: SimpleNamespace(**reference)
            for provider, reference in optimization_context[
                "catalog_references"
            ].items()
        }
    )
    return cheapest_path, expected_result, catalog_context_value


def _assert_expected_targets(
    specification: dict,
    *,
    overrides: dict[str, dict[str, object]] | None = None,
) -> None:
    expected = MATRIX["expected_targets_by_component"]
    overrides = overrides or {}
    for component_id, actual_targets in _deployable_targets(specification).items():
        assert actual_targets == overrides.get(component_id, expected[component_id])


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=lambda path: path.stem,
)
def test_canonical_positive_fixture_passes_management_without_rewrite(
    fixture_path,
):
    specification = json.loads(fixture_path.read_text(encoding="utf-8"))
    cheapest_path, expected_result, expected_catalog_context = (
        _fixture_validation_context(specification)
    )

    validated = validate_resolved_deployment_specification(
        specification,
        expected_run_id=specification["calculation_run_id"],
        expected_cheapest_path=cheapest_path,
        expected_catalog_context=expected_catalog_context,
        expected_result=expected_result,
    )

    assert validated.specification == specification
    assert validated.canonical_json == canonical_json(specification)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=lambda path: path.stem,
)
def test_canonical_negative_fixture_fails_management_before_persistence(
    fixture_path,
):
    wrapper = json.loads(fixture_path.read_text(encoding="utf-8"))
    specification = wrapper["specification"]
    cheapest_path, expected_result, expected_catalog_context = (
        _fixture_validation_context(specification)
    )

    with pytest.raises(ResolvedDeploymentSpecificationError):
        validate_resolved_deployment_specification(
            specification,
            expected_run_id=specification["calculation_run_id"],
            expected_cheapest_path=cheapest_path,
            expected_catalog_context=expected_catalog_context,
            expected_result=expected_result,
        )


@pytest.mark.parametrize(
    "path",
    MATRIX["representative_paths"],
    ids=lambda path: path["id"],
)
def test_representative_specs_validate_without_rewrite(path):
    azure_case = (
        MATRIX["azure_iot_hub_cases"][0]
        if path["providers"]["l1_ingestion"] == "azure"
        else None
    )
    _, specification, validated = _build_and_validate(
        path["providers"],
        azure_iot_case=azure_case,
    )
    overrides = {}
    if azure_case is not None:
        overrides["l1.azure.iot_hub"] = {
            "azure_iot_hub_sku": azure_case["expected_sku"],
            "azure_iot_hub_capacity": azure_case["expected_capacity"],
        }

    assert validated.specification == specification
    assert validated.canonical_json == canonical_json(specification)
    assert validated.digest == specification["digest"]
    _assert_expected_targets(specification, overrides=overrides)


@pytest.mark.parametrize(
    "case",
    MATRIX["azure_iot_hub_cases"],
    ids=lambda case: case["id"],
)
def test_azure_tier_values_survive_management_validation(case):
    providers = {
        slot: "azure"
        for slot in SLOT_TO_RESULT_PATH
    }
    _, specification, validated = _build_and_validate(
        providers,
        azure_iot_case=case,
    )
    expected = {
        "azure_iot_hub_sku": case["expected_sku"],
        "azure_iot_hub_capacity": case["expected_capacity"],
    }

    assert _deployable_targets(validated.specification)[
        "l1.azure.iot_hub"
    ] == expected
    _assert_expected_targets(
        specification,
        overrides={"l1.azure.iot_hub": expected},
    )


@pytest.mark.parametrize(
    ("hot_provider", "cool_provider", "archive_provider"),
    tuple(product(MATRIX["providers"], repeat=3)),
)
def test_every_storage_triple_validates_with_exact_targets(
    hot_provider,
    cool_provider,
    archive_provider,
):
    providers = {
        "l1_ingestion": "aws",
        "l2_processing": "aws",
        "l3_hot_storage": hot_provider,
        "l3_cool_storage": cool_provider,
        "l3_archive_storage": archive_provider,
        "l4_twin_state": "aws",
        "l5_visualization": "aws",
    }

    _, specification, validated = _build_and_validate(providers)

    assert validated.specification == specification
    _assert_expected_targets(specification)


def test_sqlite_round_trip_and_manifest_preserve_exact_specification(db_session):
    providers = next(
        path["providers"]
        for path in MATRIX["representative_paths"]
        if path["id"] == "mixed"
    )
    result, specification, _ = _build_and_validate(providers)
    user = User(email="deployment-drift@example.test", name="Drift Test")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="Deployment Drift Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.flush()
    run = CostCalculationRun(
        id=RUN_ID,
        twin_id=twin.id,
        user_id=user.id,
        status="succeeded",
        params_json="{}",
        result_summary_json=canonical_json(result),
        cheapest_path_json=canonical_json(_cheapest_path(providers)),
        currency="USD",
        optimization_profile_id="cost_minimization_v1",
        optimization_profile_version="2026.06.08",
        scoring_strategy_id="min_total_cost_v1",
        calculation_model_version="cost_model_v1",
        pricing_registry_version="2026.07.17",
        pricing_catalog_context_json=catalog_context().canonical_json(),
        deployment_specification_json=canonical_json(specification),
        deployment_specification_digest=specification["digest"],
        deployment_specification_version=specification["schema_version"],
        deployment_compatibility_status="ready",
        selected_for_deployment_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.commit()
    db_session.expire_all()
    stored = db_session.get(CostCalculationRun, RUN_ID)

    validated = validate_persisted_run_deployment_specification(stored)
    deployer_providers = {
        SLOT_TO_DEPLOYER_KEY[slot]: DEPLOYER_PROVIDER_IDS[provider]
        for slot, provider in providers.items()
    }
    credential_providers = tuple(
        provider
        for provider in MATRIX["providers"]
        if provider in set(providers.values())
    )
    manifest = _build_deployment_manifest(
        stored.twin,
        deployer_providers,
        DeploymentCredentials(
            providers=credential_providers,
            config_credentials={},
            sources={
                provider: "cloud_connection"
                for provider in credential_providers
            },
        ),
        ["config.json", "config_providers.json"],
        deployment_specification=validated.specification,
    )

    assert validated.specification == specification
    assert json.loads(stored.deployment_specification_json) == specification
    assert manifest["resolved_deployment_specification"] == specification
    assert manifest["resolved_deployment_specification_digest"] == (
        specification["digest"]
    )
    assert manifest["calculation_run_id"] == RUN_ID


def test_invalid_tier_is_rejected_without_echoing_value():
    providers = {
        slot: "azure"
        for slot in SLOT_TO_RESULT_PATH
    }
    result, specification, _ = _build_and_validate(
        providers,
        azure_iot_case=MATRIX["azure_iot_hub_cases"][0],
    )
    tampered = deepcopy(specification)
    iot_hub = next(
        component
        for component in tampered["components"]
        if component["component_id"] == "l1.azure.iot_hub"
    )
    secret_shaped_value = "SECRET-PREVIEW-SKU"
    iot_hub["dimensions"][0]["value"] = secret_shaped_value
    tampered["digest"] = calculate_digest(tampered)

    with pytest.raises(ValueError) as exc_info:
        validate_resolved_deployment_specification(
            tampered,
            expected_run_id=RUN_ID,
            expected_cheapest_path=_cheapest_path(providers),
            expected_catalog_context=catalog_context(),
            expected_result=result,
        )

    assert secret_shaped_value not in str(exc_info.value)
