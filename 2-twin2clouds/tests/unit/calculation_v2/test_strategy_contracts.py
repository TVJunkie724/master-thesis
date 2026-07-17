"""
Strategy contract tests.

These tests keep the optimizer's objective, pricing intent, formula, and
evidence declarations aligned with the bundled pricing shape.
"""

import json
from pathlib import Path

import pytest

from backend.calculation_v2.strategy_contracts import (
    EvidenceRequirement,
    ObjectiveStatus,
    OptimizationObjective,
    PricingSourceType,
    cost_strategy_contract,
    enabled_strategy_contracts,
    get_strategy_contract,
    strategy_contracts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_combined_pricing():
    return {
        provider: json.loads(
            (PROJECT_ROOT / "json" / "fetched_data" / f"pricing_dynamic_{provider}.json").read_text()
        )
        for provider in ("aws", "azure", "gcp")
    }


def _path_exists(document, path):
    current = document
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    return True


def test_only_cost_strategy_is_enabled():
    contracts = strategy_contracts()

    assert set(contracts) == {
        OptimizationObjective.COST,
        OptimizationObjective.LATENCY,
        OptimizationObjective.EMISSIONS,
        OptimizationObjective.RESILIENCE,
    }
    assert [contract.objective for contract in enabled_strategy_contracts()] == [
        OptimizationObjective.COST
    ]
    assert contracts[OptimizationObjective.COST].status == ObjectiveStatus.ENABLED
    assert contracts[OptimizationObjective.LATENCY].status == ObjectiveStatus.DISABLED
    assert contracts[OptimizationObjective.EMISSIONS].status == ObjectiveStatus.DISABLED
    assert contracts[OptimizationObjective.RESILIENCE].status == ObjectiveStatus.DISABLED


def test_strategy_contracts_validate_without_internal_drift():
    for contract in strategy_contracts().values():
        assert contract.validate() == ()


def test_cost_strategy_declares_pricing_intents_for_all_layers_and_providers():
    contract = cost_strategy_contract()
    active_pairs = {
        (intent.provider.value, intent.layer.name)
        for intent in contract.pricing_intents
        if intent.enabled_for_cost_path
    }

    assert ("aws", "L1_INGESTION") in active_pairs
    assert ("azure", "L1_INGESTION") in active_pairs
    assert ("gcp", "L1_INGESTION") in active_pairs
    assert ("aws", "L4_TWIN_MANAGEMENT") in active_pairs
    assert ("azure", "L4_TWIN_MANAGEMENT") in active_pairs
    assert ("aws", "L5_VISUALIZATION") in active_pairs
    assert ("azure", "L5_VISUALIZATION") in active_pairs

    disabled_pairs = {
        (intent.provider.value, intent.layer.name, intent.intent_id)
        for intent in contract.pricing_intents
        if not intent.enabled_for_cost_path
    }
    assert ("gcp", "L4_TWIN_MANAGEMENT", "gcp.l4.self_hosted_twin") in disabled_pairs
    assert ("gcp", "L5_VISUALIZATION", "gcp.l5.self_hosted_grafana") in disabled_pairs


def test_cost_strategy_pricing_fields_resolve_against_bundled_dynamic_pricing():
    pricing = _load_combined_pricing()
    missing = []

    for intent in cost_strategy_contract().pricing_intents:
        for field in intent.fields:
            if not any(_path_exists(pricing, path) for path in field.candidate_paths()):
                missing.append(f"{intent.intent_id}.{field.field_id}: {field.candidate_paths()}")

    assert missing == []


def test_cost_strategy_requires_evidence_for_provider_api_fields():
    for intent in cost_strategy_contract().pricing_intents:
        for field in intent.fields:
            if field.source_type == PricingSourceType.DYNAMIC_PROVIDER_API:
                assert field.evidence == EvidenceRequirement.REQUIRED


def test_formula_bindings_reference_known_pricing_intents():
    contract = cost_strategy_contract()
    known_intents = set(contract.intent_map())

    for binding in contract.formula_bindings:
        assert binding.intent_ids
        assert set(binding.intent_ids).issubset(known_intents)
        assert binding.required_usage_inputs
        assert binding.calculation_entrypoint


def test_future_objectives_are_not_runtime_selectable_with_formula_bindings():
    for objective in (
        OptimizationObjective.LATENCY,
        OptimizationObjective.EMISSIONS,
        OptimizationObjective.RESILIENCE,
    ):
        contract = get_strategy_contract(objective.value)
        assert contract.status == ObjectiveStatus.DISABLED
        assert contract.pricing_intents == ()
        assert contract.formula_bindings == ()
        assert contract.extension_note


@pytest.mark.parametrize(
    "field_id",
    [
        "azure.l1.iot_hub.message_tiers",
        "gcp.l1.pubsub.data_volume",
        "gcp.l3.firestore.write",
    ],
)
def test_unit_normalizer_hotspots_are_explicit(field_id):
    contract = cost_strategy_contract()
    intent_id, field_name = field_id.rsplit(".", 1)
    intent = contract.intent_map()[intent_id]
    field = next(item for item in intent.fields if item.field_id == field_name)

    assert field.normalizer is not None


@pytest.mark.parametrize(
    ("intent_id", "field_id", "canonical_key"),
    [
        (
            "azure.l4.digital_twins_operations",
            "operation",
            "pricePerOperation",
        ),
        (
            "azure.l4.digital_twins_messages",
            "message",
            "pricePerMessage",
        ),
        (
            "azure.l4.digital_twins_query_units",
            "query",
            "pricePerQueryUnit",
        ),
    ],
)
def test_adt_contract_exposes_only_normalized_evidence_fields(
    intent_id,
    field_id,
    canonical_key,
):
    field = next(
        item
        for item in cost_strategy_contract().intent_map()[intent_id].fields
        if item.field_id == field_id
    )

    assert field.key_path == ("azure", "azureDigitalTwins", canonical_key)
    assert field.aliases == ()
    assert field.source_type == PricingSourceType.DYNAMIC_PROVIDER_API

    binding = next(
        item
        for item in cost_strategy_contract().formula_bindings
        if item.intent_ids == (intent_id,)
    )
    assert binding.normalizer is None
