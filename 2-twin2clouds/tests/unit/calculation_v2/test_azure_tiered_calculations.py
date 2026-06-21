"""
Azure tier and unit-aware calculation tests.
"""

import pytest

from backend.calculation_v2.components.azure.digital_twins import AzureDigitalTwinsCalculator
from backend.calculation_v2.components.azure.iot_hub import AzureIoTHubCalculator


def _iot_pricing():
    return {
        "azure": {
            "iotHub": {
                "pricing_tiers": {
                    "freeTier": {"limit": 240_000, "threshold": 0, "price": 0},
                    "tier1": {"limit": 120_000_000, "threshold": 12_000_000, "price": 25.0},
                    "tier2": {"limit": 1_800_000_000, "threshold": 180_000_000, "price": 250.0},
                    "tier3": {"limit": "Infinity", "threshold": 9_000_000_000, "price": 2500.0},
                }
            }
        }
    }


def test_azure_iot_hub_uses_free_tier_from_pricing_tiers():
    calc = AzureIoTHubCalculator()

    assert calc.calculate_cost(200_000, _iot_pricing()) == 0


def test_azure_iot_hub_scales_units_inside_tier_capacity():
    calc = AzureIoTHubCalculator()

    assert calc.calculate_cost(24_000_000, _iot_pricing()) == 50.0


def test_azure_iot_hub_selects_next_tier_when_lower_tier_capacity_is_exceeded():
    calc = AzureIoTHubCalculator()

    assert calc.calculate_cost(200_000_000, _iot_pricing()) == 500.0


def test_azure_iot_hub_raises_when_tier_table_cannot_cover_volume():
    calc = AzureIoTHubCalculator()
    pricing = _iot_pricing()
    pricing["azure"]["iotHub"]["pricing_tiers"].pop("tier3")

    with pytest.raises(ValueError, match="cannot cover"):
        calc.calculate_cost(2_000_000_000, pricing)


def test_azure_digital_twins_normalizes_per_1k_prices_and_query_unit_tiers():
    calc = AzureDigitalTwinsCalculator()
    pricing = {
        "azure": {
            "azureDigitalTwins": {
                "messagePrice": 0.0013,
                "operationPrice": 0.00325,
                "queryPrice": 0.00065,
                "queryUnitTiers": [
                    {"lower": 1, "upper": 99, "value": 15},
                    {"lower": 100, "upper": 9999, "value": 1500},
                    {"lower": 10000, "value": 4000},
                ],
            }
        }
    }

    result = calc.calculate_cost(
        operations_per_month=1_000,
        queries_per_month=100,
        messages_per_month=1_000,
        pricing=pricing,
    )

    operation_cost = 1_000 * (0.00325 / 1_000)
    message_cost = 1_000 * (0.0013 / 1_000)
    query_cost = (100 * 15) * (0.00065 / 1_000)
    assert result == pytest.approx(operation_cost + message_cost + query_cost)


def test_azure_digital_twins_accepts_explicit_per_query_unit_weight():
    calc = AzureDigitalTwinsCalculator()
    pricing = {
        "azure": {
            "azureDigitalTwins": {
                "messagePrice": 0.001,
                "operationPrice": 0.002,
                "queryPrice": 0.003,
                "queryUnitTiers": [{"lower": 1, "value": 15}],
            }
        }
    }

    result = calc.calculate_cost(
        operations_per_month=0,
        queries_per_month=10,
        messages_per_month=0,
        pricing=pricing,
        query_units_per_query=4,
    )

    assert result == pytest.approx(10 * 4 * (0.003 / 1_000))
