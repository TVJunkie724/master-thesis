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
from backend.calculation_v2.engine import _calculate_egress_cost


def _azure_pricing(**overrides):
    base = {
        "iotHub": {
            "pricing_tiers": {
                "freeTier": {"limit": 240_000, "threshold": 240_000, "price": 0},
                "tier1": {"limit": 120_000_000, "threshold": 12_000_000, "price": 25},
                "tier2": {"limit": 1_800_000_000, "threshold": 180_000_000, "price": 250},
                "tier3": {"limit": "Infinity", "threshold": 9_000_000_000, "price": 2500},
            }
        },
        "azureDigitalTwins": {
            "messagePrice": 1.30,
            "operationPrice": 3.25,
            "queryPrice": 0.65,
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
        "transfer": {
            "pricing_tiers": {
                "freeTier": {"limit": 100, "price": 0},
                "tier1": {"limit": 10_240, "price": 0.087},
                "tier2": {"limit": 51_200, "price": 0.083},
                "tier3": {"limit": "Infinity", "price": 0.07},
            }
        },
    }
    base.update(overrides)
    return {"azure": base}


class TestAzureIoTHubTiering:
    def test_free_tier_is_used_for_small_workloads(self):
        result = AzureIoTHubCalculator().calculate_cost(
            messages_per_month=200_000,
            pricing=_azure_pricing(),
        )

        assert result == 0

    def test_paid_tier_units_scale_with_message_volume(self):
        result = AzureIoTHubCalculator().calculate_cost(
            messages_per_month=12_000_001,
            pricing=_azure_pricing(),
        )

        assert result == 50

    def test_cheapest_valid_paid_tier_is_selected_for_high_volume(self):
        result = AzureIoTHubCalculator().calculate_cost(
            messages_per_month=180_000_000,
            pricing=_azure_pricing(),
        )

        assert result == 250


class TestAzureDigitalTwinsUnitNormalization:
    def test_messages_operations_and_query_units_are_normalized_from_1k_blocks(self):
        result = AzureDigitalTwinsCalculator().calculate_cost(
            operations_per_month=2_000,
            queries_per_month=3_000,
            messages_per_month=4_000,
            pricing=_azure_pricing(),
        )

        expected = (2_000 * 0.00325) + (3_000 * 0.00065) + (4_000 * 0.0013)
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
            operations_per_month=10,
            queries_per_month=10,
            messages_per_month=10,
            pricing=pricing,
        )

        assert result == pytest.approx(0.6)


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

        expected = ((10_240 - 100) * 0.087) + ((10_500 - 10_240) * 0.083)
        assert result == pytest.approx(expected)
