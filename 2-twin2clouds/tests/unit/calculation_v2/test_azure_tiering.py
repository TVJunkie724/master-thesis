"""Azure unit and tier-aware calculation regression tests."""

import pytest

from backend.calculation_v2.components.azure import (
    AzureBlobArchiveCalculator,
    AzureBlobCoolCalculator,
    AzureDigitalTwinsCalculator,
    AzureEventGridCalculator,
    AzureIoTHubCalculator,
    AzureLogicAppsCalculator,
)
from backend.calculation_v2.components.azure.iot_hub import (
    IOT_HUB_MAXIMUM_CAPACITY,
)
from backend.calculation_v2.engine import _calculate_egress_cost
from tests.unit.pricing.transfer_fixtures import canonical_transfer_catalog


def _azure_pricing(**overrides):
    base = {
        "iotHub": {
            "pricing_tiers": {
                "freeTier": {"limit": 240_000, "threshold": 0, "price": 0},
                "tier1": {"limit": 120_000_000, "threshold": 12_000_000, "price": 25},
                "tier2": {"limit": 1_800_000_000, "threshold": 180_000_000, "price": 250},
                "tier3": {"limit": "Infinity", "threshold": 9_000_000_000, "price": 2500},
            }
        },
        "azureDigitalTwins": {
            "pricePerMessage": 0.00130,
            "pricePerOperation": 0.00325,
            "pricePerQueryUnit": 0.00065,
        },
        "blobStorageCool": {
            "storagePrice": 0.01,
            "writePricePer10kRequests": 0.055,
            "readPricePer10kRequests": 0.0044,
            "dataRetrievalPrice": 0.01,
        },
        "blobStorageArchive": {
            "storagePrice": 0.0018,
            "writePricePer10kRequests": 0.13,
            "readPricePer10kRequests": 0.65,
            "dataRetrievalPrice": 0.024,
        },
        "logicApps": {"pricePer1kStateTransitions": 0.125},
        "eventGrid": {"pricePerMillionEvents": 0.60},
        "transfer": canonical_transfer_catalog("azure"),
    }
    base.update(overrides)
    return {"azure": base}


class TestAzureIoTHubTiering:
    def test_formula_capacity_limits_match_deployment_registry(self):
        from backend.deployment_specification.builder import _contract

        registry = _contract()[1]
        constraints = registry["components"]["l1.azure.iot_hub"][
            "combination_constraints"
        ][0]["ranges_by_selector"]

        assert IOT_HUB_MAXIMUM_CAPACITY == {
            sku: values["maximum"]
            for sku, values in constraints.items()
        }

    def test_free_tier_is_used_for_small_workloads(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=200_000,
            pricing=_azure_pricing(),
        )

        assert result.sku == "F1"
        assert result.capacity == 1
        assert result.total_cost == 0

    def test_paid_tier_units_scale_with_message_volume(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=12_000_001,
            pricing=_azure_pricing(),
        )

        assert result.sku == "S1"
        assert result.capacity == 2
        assert result.total_cost == 50

    def test_cheapest_valid_paid_tier_is_selected_for_high_volume(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=180_000_000,
            pricing=_azure_pricing(),
        )

        assert result.sku == "S2"
        assert result.capacity == 1
        assert result.total_cost == 250

    def test_s1_remains_eligible_beyond_the_legacy_catalog_limit(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=200_000_000,
            pricing=_azure_pricing(),
        )

        assert result.sku == "S1"
        assert result.capacity == 17
        assert result.total_cost == 425

    def test_s3_tier_is_selected_when_lower_tiers_exceed_maximum_capacity(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=45_000_000_000,
            pricing=_azure_pricing(),
        )

        assert result.sku == "S3"
        assert result.capacity == 5
        assert result.total_cost == 12_500

    def test_workload_above_all_supported_capacity_fails_closed(self):
        with pytest.raises(ValueError, match="valid paid tier"):
            AzureIoTHubCalculator().calculate_selection(
                messages_per_month=90_000_000_001,
                pricing=_azure_pricing(),
            )

    def test_unknown_provider_tier_fails_closed(self):
        pricing = _azure_pricing()
        pricing["azure"]["iotHub"]["pricing_tiers"]["previewTier"] = {
            "limit": "Infinity",
            "threshold": 1,
            "price": 1,
        }

        with pytest.raises(ValueError, match="unsupported tiers"):
            AzureIoTHubCalculator().calculate_selection(
                messages_per_month=1,
                pricing=pricing,
            )

    def test_message_size_uses_provider_specific_quota_blocks(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=200_000,
            average_message_size_kb=1.0,
            pricing=_azure_pricing(),
        )

        assert result.sku == "S1"
        assert result.capacity == 1
        assert result.billable_quantity == 200_000
        assert result.total_cost == 25

    def test_paid_tier_capacity_uses_four_kb_billable_message_blocks(self):
        result = AzureIoTHubCalculator().calculate_selection(
            messages_per_month=12_000_000,
            average_message_size_kb=8.0,
            pricing=_azure_pricing(),
        )

        assert result.sku == "S1"
        assert result.capacity == 2
        assert result.billable_quantity == 24_000_000


class TestAzureDigitalTwinsUnitNormalization:
    def test_canonical_unit_prices_are_applied_to_billable_quantities(self):
        result = AzureDigitalTwinsCalculator().calculate_cost(
            billable_operations=2_000,
            billable_query_units=3_000,
            billable_messages=4_000,
            pricing=_azure_pricing(),
        )

        expected = (2_000 * 0.00325) + (3_000 * 0.00065) + (4_000 * 0.00130)
        assert result == pytest.approx(expected)

    def test_explicit_per_unit_keys_take_precedence_over_legacy_block_keys(self):
        pricing = _azure_pricing(
            azureDigitalTwins={
                "pricePerOperation": 0.01,
                "operationPrice": 100,
                "pricePerQueryUnit": 0.02,
                "queryPrice": 100,
                "pricePerMessage": 0.03,
                "messagePrice": 100,
            }
        )

        result = AzureDigitalTwinsCalculator().calculate_cost(
            billable_operations=10,
            billable_query_units=10,
            billable_messages=10,
            pricing=pricing,
        )

        assert result == pytest.approx(0.6)

    def test_breakdown_keeps_each_meter_contribution_inspectable(self):
        result = AzureDigitalTwinsCalculator().calculate_breakdown(
            billable_operations=2,
            billable_query_units=3,
            billable_messages=4,
            pricing=_azure_pricing(),
        )

        assert result.operation_cost == pytest.approx(0.0065)
        assert result.query_unit_cost == pytest.approx(0.00195)
        assert result.routed_message_cost == pytest.approx(0.0052)
        assert result.total_cost == pytest.approx(0.01365)

    def test_zero_routed_messages_do_not_require_message_pricing(self):
        pricing = _azure_pricing(
            azureDigitalTwins={
                "pricePerOperation": 0.00325,
                "pricePerQueryUnit": 0.00065,
            }
        )

        result = AzureDigitalTwinsCalculator().calculate_cost(
            billable_operations=1,
            billable_query_units=1,
            billable_messages=0,
            pricing=pricing,
        )

        assert result == pytest.approx(0.0039)

    @pytest.mark.parametrize(
        "missing_key",
        ["pricePerOperation", "pricePerQueryUnit"],
    )
    def test_required_adt_prices_fail_closed(self, missing_key):
        prices = dict(_azure_pricing()["azure"]["azureDigitalTwins"])
        prices.pop(missing_key)

        with pytest.raises(ValueError, match="Missing required pricing field"):
            AzureDigitalTwinsCalculator().calculate_cost(
                billable_operations=1,
                billable_query_units=1,
                billable_messages=0,
                pricing={"azure": {"azureDigitalTwins": prices}},
            )

    @pytest.mark.parametrize(
        "quantity",
        [-1, float("inf"), float("nan"), True, "1"],
    )
    def test_invalid_billable_quantities_fail_closed(self, quantity):
        with pytest.raises(ValueError, match="finite non-negative"):
            AzureDigitalTwinsCalculator().calculate_cost(
                billable_operations=quantity,
                billable_query_units=1,
                billable_messages=0,
                pricing=_azure_pricing(),
            )


class TestAzureStorageOperationUnits:
    def test_cool_storage_normalizes_write_and_read_operation_blocks(self):
        result = AzureBlobCoolCalculator().calculate_cost(
            storage_gb=100,
            writes_per_month=20_000,
            reads_per_month=30_000,
            retrievals_gb=10,
            pricing=_azure_pricing(),
        )

        expected = 1.0 + (20_000 * 0.0000055) + (30_000 * 0.00000044) + 0.10
        assert result == pytest.approx(expected)

    def test_archive_storage_normalizes_write_and_read_operation_blocks(self):
        result = AzureBlobArchiveCalculator().calculate_cost(
            storage_gb=100,
            writes_per_month=20_000,
            reads_per_month=10_000,
            retrievals_gb=10,
            pricing=_azure_pricing(),
        )

        expected = 0.18 + (20_000 * 0.000013) + (10_000 * 0.000065) + 0.24
        assert result == pytest.approx(expected)


class TestAzureActionUnitNormalization:
    def test_logic_apps_normalizes_per_1k_action_price(self):
        result = AzureLogicAppsCalculator().calculate_cost(
            executions=10,
            actions_per_execution=5,
            pricing=_azure_pricing(),
        )

        assert result == pytest.approx(50 * 0.000125)

    def test_event_grid_normalizes_per_million_event_price(self):
        result = AzureEventGridCalculator().calculate_cost(
            events=2_000_000,
            pricing=_azure_pricing(),
        )

        assert result == pytest.approx(1.2)


class TestAzureTransferTiering:
    def test_azure_egress_uses_tiered_transfer_pricing(self):
        result = _calculate_egress_cost(
            data_gb=10_500,
            pricing=_azure_pricing(),
            source_provider="Azure",
        )

        expected = ((10_335 - 100) * 0.087) + ((10_500 - 10_335) * 0.083)
        assert result == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("data_gb", "expected"),
        [
            (0, 0),
            (100, 0),
            (101, 0.087),
            (10_335, 10_235 * 0.087),
            (10_336, (10_235 * 0.087) + 0.083),
            (51_295, (10_235 * 0.087) + (40_960 * 0.083)),
            (
                51_296,
                (10_235 * 0.087) + (40_960 * 0.083) + 0.07,
            ),
        ],
    )
    def test_azure_egress_live_catalog_boundaries(self, data_gb, expected):
        result = _calculate_egress_cost(
            data_gb=data_gb,
            pricing=_azure_pricing(),
            source_provider="Azure",
        )

        assert result == pytest.approx(expected)
