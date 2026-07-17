
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from rest_api import app

client = TestClient(app)


def _valid_payload():
    return {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
    }


# -----------------------------------------------------------------------------
# 1. Input Validation Edge Cases
# -----------------------------------------------------------------------------

def test_calculate_missing_fields():
    """Test that missing required fields returns 422 Unprocessable Entity."""
    # Sending empty body
    response = client.put("/calculate", json={})
    assert response.status_code == 422
    data = response.json()
    # Check that at least one field is missing (e.g., numberOfDevices)
    # detail is a list of dicts
    assert any(err["loc"][-1] == "numberOfDevices" for err in data["detail"])

def test_calculate_invalid_data_types():
    """Test sending string for integer field returns 422."""
    payload = {
        "numberOfDevices": "one_hundred", # Invalid
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0
    }
    response = client.put("/calculate", json=payload)
    assert response.status_code == 422
    # Check for type error message
    assert "valid integer" in response.text.lower() or "valid number" in response.text.lower()

def test_calculate_negative_values():
    """Test validation of negative values where positive are required."""
    payload = {
        "numberOfDevices": -50, # Invalid
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0
    }
    response = client.put("/calculate", json=payload)
    assert response.status_code == 422

def test_calculate_storage_duration_logic_ordering():
    """Test logic: Hot <= Cool <= Archive."""
    payload = {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 4,   # > Cool (3)
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12, # Valid >= 6
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0
    }
    response = client.put("/calculate", json=payload)
    assert response.status_code == 422
    # Pydantic returns details in JSON
    # Msg: "Value error, Hot storage duration (4) must be <= Cool storage duration (3)"
    assert "Hot storage duration" in response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("averageDigitalTwinQueryUnitsPerQuery", 0),
        ("averageDigitalTwinQueryResponseSizeInKb", 0),
        ("averageDigitalTwinQueryUnitsPerQuery", "invalid"),
        ("averageDigitalTwinQueryResponseSizeInKb", "invalid"),
        ("averageDigitalTwinQueryUnitsPerQuery", "1.0"),
        ("averageDigitalTwinQueryResponseSizeInKb", "1.0"),
    ],
)
def test_calculate_rejects_invalid_adt_assumptions(field, value):
    payload = _valid_payload()
    payload[field] = value

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422


def test_calculate_rejects_unknown_fields():
    response = client.put(
        "/calculate",
        json={**_valid_payload(), "legacyOptimizerFlag": True},
    )

    assert response.status_code == 422

# -----------------------------------------------------------------------------
# 2. Engine Robustness / Error Handling
# -----------------------------------------------------------------------------

@patch("api.calculation.load_combined_pricing")
def test_calculate_load_pricing_failure(mock_load_pricing):
    """Test 500 behavior when pricing load completely fails."""
    mock_load_pricing.side_effect = Exception("Disk failure simulation")
    
    payload = {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0
    }
    
    response = client.put("/calculate", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Calculation failed" in data["detail"]

@patch("backend.calculation_v2.engine.calculate_cheapest_costs")
@patch("api.calculation.load_combined_pricing")
def test_calculate_engine_internal_error(mock_load, mock_engine):
    """Test behavior when engine raises an unexpected error."""
    # PATCH TARGET: backend.calculation_v2.engine.calculate_cheapest_costs
    # Because api/calculation.py imports it locally inside the function 'calc'
    mock_load.return_value = {}
    mock_engine.side_effect = ValueError("Calculation logic exploded")
    
    payload = {
        "numberOfDevices": 100, 
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0
    }
    
    response = client.put("/calculate", json=payload)
    # ValueError is caught as a 400 by the handler (not 500)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Calculation logic exploded" in data["detail"]

# -----------------------------------------------------------------------------
# 3. Feature Toggle Verification
# -----------------------------------------------------------------------------

@patch("api.calculation.load_combined_pricing")
def test_feature_toggle_gcp_l4_disabled(mock_load_pricing):
    """Verify that disabling 'allowGcpSelfHostedL4' in params passes correct flag to engine."""
    
    # We patch the ENGINE function (backend.calculation_v2.engine.calculate_cheapest_costs)
    # to inspect arguments passed to it.
    with patch("backend.calculation_v2.engine.calculate_cheapest_costs") as mock_calc:
        mock_calc.return_value = {}
        mock_load_pricing.return_value = {}
        
        payload = {
            "numberOfDevices": 100,
            "deviceSendingIntervalInMinutes": 2.0,
            "averageSizeOfMessageInKb": 0.25,
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
            "archiveStorageDurationInMonths": 12,
            "needs3DModel": False,
            "entityCount": 0,
            "amountOfActiveEditors": 0,
            "amountOfActiveViewers": 0,
            "dashboardRefreshesPerHour": 0,
            "dashboardActiveHoursPerDay": 0,
            "allowGcpSelfHostedL4": False, # Flag
            "allowGcpSelfHostedL5": False
        }
        
        client.put("/calculate", json=payload)
        
        # Verify call args
        args, _ = mock_calc.call_args
        params_arg = args[0]
        assert params_arg["allowGcpSelfHostedL4"] is False
        assert params_arg["allowGcpSelfHostedL5"] is False


@patch("api.calculation.load_combined_pricing")
def test_calculate_response_exposes_additive_trace_metadata(mock_load_pricing):
    """The public calculate endpoint exposes read-only intent trace metadata."""
    from tests.unit.calculation_v2.test_intent_to_result_traceability import _sample_pricing

    mock_load_pricing.return_value = _sample_pricing()
    payload = {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 1,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 5,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "allowGcpSelfHostedL4": False,
        "allowGcpSelfHostedL5": False,
    }

    response = client.put("/calculate", json=payload)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["trace_schema_version"] == "intent-result-trace.v1"
    assert result["intentTrace"]["summary"]["record_count"] > 0
    assert result["intentTrace"]["profile"]["profile_id"] == "cost_minimization_v1"
    assert result["intentTrace"]["workload"]["assumption_sources"] == {
        "averageDigitalTwinQueryUnitsPerQuery": "compatibility_default",
        "averageDigitalTwinQueryResponseSizeInKb": "compatibility_default",
    }


@patch("api.calculation.load_combined_pricing")
def test_calculate_preserves_explicit_adt_assumptions_in_trace(mock_load_pricing):
    from tests.unit.calculation_v2.test_intent_to_result_traceability import (
        _sample_pricing,
    )

    mock_load_pricing.return_value = _sample_pricing()
    payload = {
        **_valid_payload(),
        "dashboardRefreshesPerHour": 2,
        "dashboardActiveHoursPerDay": 1,
        "averageDigitalTwinQueryUnitsPerQuery": 2.5,
        "averageDigitalTwinQueryResponseSizeInKb": 1.1,
    }

    response = client.put("/calculate", json=payload)

    assert response.status_code == 200
    workload = response.json()["result"]["intentTrace"]["workload"]
    assert workload["inputs"]["averageDigitalTwinQueryUnitsPerQuery"] == 2.5
    assert workload["inputs"]["averageDigitalTwinQueryResponseSizeInKb"] == 1.1
    assert workload["assumption_sources"] == {
        "averageDigitalTwinQueryUnitsPerQuery": "explicit_input",
        "averageDigitalTwinQueryResponseSizeInKb": "explicit_input",
    }
    assert workload["derived"]["queries_per_month"] == 60
    assert workload["derived"]["digital_twin_query_response_operations"] == 120
    assert workload["derived"]["monthly_digital_twin_query_units"] == 150


def test_calculate_rejects_unimplemented_gcp_self_hosted_paths():
    payload = {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 1,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 5,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "allowGcpSelfHostedL4": True,
    }

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    assert "cannot be enabled" in response.text
