"""
Pricing source inventory tests.

The inventory turns strategy contract fields into source/failure policies that
future fetcher, API, and UI layers can consume without guessing.
"""

from backend.calculation_v2.pricing_source_inventory import (
    PricingFailureBehavior,
    Refreshability,
    pricing_source_inventory,
    pricing_source_inventory_by_id,
)
from backend.calculation_v2.strategy_contracts import (
    PricingSourceType,
    cost_strategy_contract,
)


def test_inventory_contains_exactly_one_record_per_contract_field():
    contract = cost_strategy_contract()
    expected_ids = {
        f"{intent.intent_id}.{field.field_id}"
        for intent in contract.pricing_intents
        for field in intent.fields
    }

    inventory = pricing_source_inventory(contract)
    actual_ids = {record.record_id for record in inventory}

    assert actual_ids == expected_ids
    assert len(actual_ids) == len(inventory)


def test_dynamic_provider_fields_are_refreshable_and_fail_closed_or_review_required():
    inventory = pricing_source_inventory_by_id()

    for record in inventory.values():
        if record.policy.primary_source_type != PricingSourceType.DYNAMIC_PROVIDER_API:
            continue

        assert record.policy.refreshability == Refreshability.REFRESHABLE
        assert record.policy.failure_behavior in {
            PricingFailureBehavior.REJECT_FIELD,
            PricingFailureBehavior.REQUIRE_REVIEW,
        }
        assert record.policy.emergency_fallback_allowed is False


def test_static_official_fields_are_non_fetchable_and_review_required():
    inventory = pricing_source_inventory_by_id()

    for record_id in (
        "aws.l2.lambda.free_requests",
        "aws.l3.dynamodb.free_storage",
        "gcp.l1.pubsub.device_month",
    ):
        record = inventory[record_id]
        assert record.policy.primary_source_type == PricingSourceType.STATIC_OFFICIAL_TABLE
        assert record.policy.refreshability == Refreshability.STATIC_NON_FETCHABLE
        assert record.policy.failure_behavior == PricingFailureBehavior.REQUIRE_REVIEW


def test_derived_usage_model_fields_are_not_treated_as_provider_prices():
    inventory = pricing_source_inventory_by_id()

    for record_id in (
        "azure.l3.cosmos_db.ru_per_read",
        "azure.l3.cosmos_db.ru_per_write",
    ):
        record = inventory[record_id]
        assert record.policy.primary_source_type == PricingSourceType.DERIVED_CALCULATION
        assert record.policy.refreshability == Refreshability.DERIVED_AT_RUNTIME
        assert record.policy.failure_behavior == PricingFailureBehavior.DERIVE_FROM_USAGE_MODEL


def test_current_emergency_fallbacks_are_visible_but_not_publishable_successes():
    inventory = pricing_source_inventory_by_id()

    for record_id in (
        "aws.l1.iot_core.device_month",
        "azure.l1.iot_hub.message_tiers",
        "gcp.l4.self_hosted_twin.vm_hour",
    ):
        record = inventory[record_id]
        assert record.policy.emergency_fallback_source_type == PricingSourceType.STATIC_OFFICIAL_TABLE
        assert record.policy.emergency_fallback_allowed is False
        assert record.policy.failure_behavior == PricingFailureBehavior.REQUIRE_REVIEW


def test_inventory_records_are_serializable_for_api_and_ui_review_surfaces():
    record = pricing_source_inventory_by_id()["azure.l4.digital_twins_query_units.query"]

    payload = record.as_dict()

    assert payload["record_id"] == record.record_id
    assert payload["primary_source_type"] == "dynamic_provider_api"
    assert payload["refreshability"] == "refreshable"
    assert payload["failure_behavior"] == "reject_field"
    assert payload["key_path"] == ["azure", "azureDigitalTwins", "pricePerQueryUnit"]
    assert payload["normalizer"] is None
