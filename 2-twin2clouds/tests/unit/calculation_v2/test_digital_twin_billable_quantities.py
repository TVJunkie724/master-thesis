"""Regression tests for Azure Digital Twins workload derivation and L4 topology."""

import pytest

from backend.calculation_v2.engine import _calculate_derived_params
from backend.calculation_v2.layers import AzureLayerCalculators


def _params(**overrides):
    params = {
        "numberOfDevices": 1,
        "deviceSendingIntervalInMinutes": 60,
        "averageSizeOfMessageInKb": 1,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 2,
        "archiveStorageDurationInMonths": 6,
        "dashboardActiveHoursPerDay": 2,
        "dashboardRefreshesPerHour": 3,
        "apiCallsPerDashboardRefresh": 4,
    }
    params.update(overrides)
    return params


def _pricing():
    return {
        "azure": {
            "azureDigitalTwins": {
                "pricePerOperation": 0.00325,
                "pricePerQueryUnit": 0.00065,
                "pricePerMessage": 0.0013,
            },
            "functions": {
                "requestPrice": 0,
                "durationPrice": 0,
                "freeRequests": 0,
                "freeComputeTime": 0,
            },
        }
    }


def test_derived_quantities_apply_adt_billing_rules_and_baseline_topology():
    derived = _calculate_derived_params(
        _params(
            averageDigitalTwinQueryUnitsPerQuery=2.5,
            averageDigitalTwinQueryResponseSizeInKb=1.1,
            _assumption_sources={
                "averageDigitalTwinQueryUnitsPerQuery": "explicit_input",
                "averageDigitalTwinQueryResponseSizeInKb": "explicit_input",
            },
        )
    )

    assert derived["total_messages_per_month"] == 720
    assert derived["queries_per_month"] == 720
    assert derived["digital_twin_query_response_operations"] == 1_440
    assert derived["monthly_digital_twin_billable_operations"] == 2_160
    assert derived["monthly_digital_twin_query_units"] == 1_800
    assert derived["monthly_digital_twin_routed_messages"] == 0
    assert derived["digital_twin_assumption_sources"] == {
        "averageDigitalTwinQueryUnitsPerQuery": "explicit_input",
        "averageDigitalTwinQueryResponseSizeInKb": "explicit_input",
    }


def test_omitted_assumptions_are_visible_as_compatibility_defaults():
    derived = _calculate_derived_params(_params())

    assert derived["average_digital_twin_query_units_per_query"] == 1
    assert derived["average_digital_twin_query_response_size_kb"] == 1
    assert derived["digital_twin_assumption_sources"] == {
        "averageDigitalTwinQueryUnitsPerQuery": "compatibility_default",
        "averageDigitalTwinQueryResponseSizeInKb": "compatibility_default",
    }


def test_azure_l4_exposes_exact_canonical_components():
    result = AzureLayerCalculators().calculate_l4_cost(
        billable_operations=10,
        billable_query_units=20,
        billable_messages=0,
        telemetry_updates_per_month=10,
        pricing=_pricing(),
    )

    assert set(result.components) == {
        "digital_twins_operations",
        "digital_twins_query_units",
        "digital_twins_routed_messages",
        "adt_pusher_function",
    }
    assert result.components["digital_twins_operations"] == pytest.approx(0.0325)
    assert result.components["digital_twins_query_units"] == pytest.approx(0.013)
    assert result.components["digital_twins_routed_messages"] == 0
    assert result.components["adt_pusher_function"] == 0
    assert result.total_cost == pytest.approx(0.0455)
