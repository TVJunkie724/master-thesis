"""Cross-stack drift tests for Optimizer deployment selections."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from itertools import product
import json
from pathlib import Path

import pytest

from backend.calculation_v2.engine import (
    _layer_result_payload,
    calculate_aws_costs,
    calculate_azure_costs,
    calculate_gcp_costs,
)
from backend.calculation_v2.layers import (
    AWSLayerCalculators,
    AzureLayerCalculators,
    GCPLayerCalculators,
)
from backend.calculation_v2.strategy_context import (
    resolve_calculation_strategy_execution_context,
)
from backend.deployment_specification.builder import (
    LAYER_TO_SLOT,
    _digest,
    build_resolved_deployment_specification,
)
from backend.optimization.profiles import build_default_profile_registry
from tests.unit.calculation_v2.test_engine_consistency import (
    REALISTIC_PRICING,
    STANDARD_PARAMS,
)
from tests.unit.pricing.transfer_fixtures import pricing_catalog_context_for


CONTRACT_V1 = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)
MATRIX = json.loads(
    (CONTRACT_V1 / "verification-matrix.json").read_text(encoding="utf-8")
)
PROVIDER_LABELS = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
SLOT_TO_LAYER = {slot: layer for layer, slot in LAYER_TO_SLOT.items()}
TRANSITION_WORKLOADS = {
    "l3_hot_to_l3_cool": (30, "one_daily_source_mover_invocation"),
    "l3_cool_to_l3_archive": (4, "one_weekly_source_mover_invocation"),
}


@pytest.fixture(scope="module")
def deployment_inputs():
    pricing = deepcopy(REALISTIC_PRICING)
    pricing["__aws_schema__"] = {
        "pricing_region": "eu-central-1",
        "snapshot_digest": "sha256:" + ("a" * 64),
    }
    params = deepcopy(STANDARD_PARAMS)
    params["providerPricingContexts"] = {
        "awsTwinMaker": {
            "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
            "status": "available",
            "sourceRefreshRunId": "drift-matrix",
            "connectionFingerprint": "sha256:" + ("b" * 64),
            "providerAccountId": "123456789012",
            "pricingRegion": "eu-central-1",
            "catalogSnapshotDigest": "sha256:" + ("a" * 64),
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "currentPlan": {
                "mode": "STANDARD",
                "billableEntityCount": 1,
                "effectiveAt": None,
                "updatedAt": None,
                "updateReason": None,
                "bundle": None,
            },
            "pendingPlan": None,
        }
    }
    provider_costs = {
        "AWS": calculate_aws_costs(params, pricing),
        "Azure": calculate_azure_costs(params, pricing),
        "GCP": calculate_gcp_costs(params, pricing),
    }
    return params, pricing, provider_costs


def _build_specification(
    providers_by_slot: dict[str, str],
    *,
    pricing: dict,
    provider_costs: dict,
) -> dict:
    calculators = {
        "aws": AWSLayerCalculators(),
        "azure": AzureLayerCalculators(),
        "gcp": GCPLayerCalculators(),
    }
    transition_selections = {}
    for transition in MATRIX["storage_transitions"]:
        provider = providers_by_slot[transition["source_slot"]]
        invocations, basis = TRANSITION_WORKLOADS[transition["boundary_id"]]
        transition_selections[transition["boundary_id"]] = calculators[
            provider
        ].calculate_transition_runtime(
            edge_id=transition["boundary_id"],
            monthly_invocations=invocations,
            invocation_basis=basis,
            pricing=pricing,
        ).deployment_selection

    profile_registry = build_default_profile_registry()
    selected_providers = {
        SLOT_TO_LAYER[slot]: PROVIDER_LABELS[provider]
        for slot, provider in providers_by_slot.items()
    }
    return build_resolved_deployment_specification(
        calculation_run_id=STANDARD_PARAMS["calculationRunId"],
        selected_providers=selected_providers,
        provider_costs=provider_costs,
        glue_selections={
            provider: calculator.glue_deployment_selection()
            for provider, calculator in calculators.items()
        },
        transition_runtime_selections=transition_selections,
        optimization_metadata=profile_registry.build_result_metadata(
            "cost_minimization_v1"
        ),
        execution_context=resolve_calculation_strategy_execution_context(
            profile_registry=profile_registry,
        ),
        pricing_catalog_context=pricing_catalog_context_for(pricing),
    )


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


def _assert_expected_targets(
    specification: dict,
    *,
    overrides: dict[str, dict[str, object]] | None = None,
) -> None:
    expected = MATRIX["expected_targets_by_component"]
    overrides = overrides or {}
    for component_id, actual_targets in _deployable_targets(specification).items():
        assert actual_targets == overrides.get(component_id, expected[component_id])


def _assert_runtime_and_glue_ownership(
    specification: dict,
    providers_by_slot: dict[str, str],
) -> None:
    component_ids = {
        component["component_id"] for component in specification["components"]
    }
    for transition in MATRIX["storage_transitions"]:
        source = providers_by_slot[transition["source_slot"]]
        assert (
            transition["runtime_component_by_source"][source] in component_ids
        )

    expected_glue = set()
    registry = json.loads(
        (CONTRACT_V1 / "deployment-dimensions.json").read_text(encoding="utf-8")
    )
    for boundary in registry["cross_cloud_glue_policy"]["boundaries"]:
        source = providers_by_slot[boundary["source_slot"]]
        target = providers_by_slot[boundary["target_slot"]]
        if source != target:
            receiver = providers_by_slot[boundary["receiver_slot"]]
            expected_glue.add(MATRIX["glue_component_by_receiver"][receiver])
    actual_glue = {
        component["component_id"]
        for component in specification["components"]
        if component["slot_id"] == "cross_cloud_glue"
    }
    assert actual_glue == expected_glue


def _azure_l1_payload(case: dict, pricing: dict) -> dict:
    result = AzureLayerCalculators().calculate_l1_cost(
        messages_per_month=case["messages_per_month"],
        average_message_size_kb=case["average_message_size_kb"],
        pricing=pricing,
    )
    return _layer_result_payload(result)


@pytest.mark.parametrize(
    "case",
    MATRIX["azure_iot_hub_cases"],
    ids=lambda case: case["id"],
)
def test_azure_formula_selection_reaches_resolved_specification(
    case,
    deployment_inputs,
):
    _, pricing, base_provider_costs = deployment_inputs
    provider_costs = deepcopy(base_provider_costs)
    provider_costs["Azure"]["L1"] = _azure_l1_payload(case, pricing)
    providers = {
        slot: "azure"
        for slot in (
            "l1_ingestion",
            "l2_processing",
            "l3_hot_storage",
            "l3_cool_storage",
            "l3_archive_storage",
            "l4_twin_state",
            "l5_visualization",
        )
    }

    specification = _build_specification(
        providers,
        pricing=pricing,
        provider_costs=provider_costs,
    )
    expected_iot = {
        "azure_iot_hub_sku": case["expected_sku"],
        "azure_iot_hub_capacity": case["expected_capacity"],
    }

    assert specification["digest"] == _digest(specification)
    _assert_expected_targets(
        specification,
        overrides={"l1.azure.iot_hub": expected_iot},
    )
    assert _deployable_targets(specification)["l1.azure.iot_hub"] == expected_iot


@pytest.mark.parametrize(
    "path",
    MATRIX["representative_paths"],
    ids=lambda path: path["id"],
)
def test_representative_provider_paths_are_complete(
    path,
    deployment_inputs,
):
    _, pricing, base_provider_costs = deployment_inputs
    provider_costs = deepcopy(base_provider_costs)
    overrides = {}
    if path["providers"]["l1_ingestion"] == "azure":
        free_case = MATRIX["azure_iot_hub_cases"][0]
        provider_costs["Azure"]["L1"] = _azure_l1_payload(
            free_case,
            pricing,
        )
        overrides["l1.azure.iot_hub"] = {
            "azure_iot_hub_sku": free_case["expected_sku"],
            "azure_iot_hub_capacity": free_case["expected_capacity"],
        }

    specification = _build_specification(
        path["providers"],
        pricing=pricing,
        provider_costs=provider_costs,
    )

    assert specification["digest"] == _digest(specification)
    _assert_expected_targets(specification, overrides=overrides)
    _assert_runtime_and_glue_ownership(specification, path["providers"])


@pytest.mark.parametrize(
    ("hot_provider", "cool_provider", "archive_provider"),
    tuple(product(MATRIX["providers"], repeat=3)),
)
def test_every_storage_provider_triple_has_source_owned_runtime(
    hot_provider,
    cool_provider,
    archive_provider,
    deployment_inputs,
):
    _, pricing, provider_costs = deployment_inputs
    providers = {
        "l1_ingestion": "aws",
        "l2_processing": "aws",
        "l3_hot_storage": hot_provider,
        "l3_cool_storage": cool_provider,
        "l3_archive_storage": archive_provider,
        "l4_twin_state": "aws",
        "l5_visualization": "aws",
    }

    specification = _build_specification(
        providers,
        pricing=pricing,
        provider_costs=provider_costs,
    )

    _assert_expected_targets(specification)
    _assert_runtime_and_glue_ownership(specification, providers)
