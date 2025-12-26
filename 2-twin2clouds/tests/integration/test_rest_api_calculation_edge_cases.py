
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from rest_api import app

client = TestClient(app)

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
    assert "error" in data
    assert "Disk failure simulation" in data["error"]

@patch("backend.calculation.engine.calculate_cheapest_costs")
@patch("api.calculation.load_combined_pricing")
def test_calculate_engine_internal_error(mock_load, mock_engine):
    """Test behavior when engine raises an unexpected error."""
    # PATCH TARGET: backend.calculation.engine.calculate_cheapest_costs
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
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "Calculation logic exploded" in data["error"]

# -----------------------------------------------------------------------------
# 3. Feature Toggle Verification
# -----------------------------------------------------------------------------

@patch("api.calculation.load_combined_pricing")
def test_feature_toggle_gcp_l4_disabled(mock_load_pricing):
    """Verify that disabling 'allowGcpSelfHostedL4' in params passes correct flag to engine."""
    
    # We patch the ENGINE function (backend.calculation.engine.calculate_cheapest_costs)
    # to inspect arguments passed to it.
    with patch("backend.calculation.engine.calculate_cheapest_costs") as mock_calc:
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
