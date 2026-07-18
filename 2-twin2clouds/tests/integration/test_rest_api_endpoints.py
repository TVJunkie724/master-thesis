from fastapi.testclient import TestClient
from unittest.mock import patch
from rest_api import app
import backend.constants as CONSTANTS

client = TestClient(app)

# ----------------------------------------------------------------
# Region Fetching Tests
# ----------------------------------------------------------------
# NOTE: Region fetching tests have been moved to tests/test_rest_api_regions.py
# to avoid mocking conflicts.

# ----------------------------------------------------------------
# File Age Tests
# ----------------------------------------------------------------

@patch("api.file_status.is_file_fresh")
@patch("api.file_status.get_file_age_string")
def test_get_regions_age_aws(mock_get_age, mock_is_fresh):
    """Test GET /regions_age/aws returns age string, is_fresh, threshold."""
    mock_get_age.return_value = "5 days"
    mock_is_fresh.return_value = True
    
    response = client.get("/regions_age/aws")
    
    assert response.status_code == 200
    assert response.json() == {"age": "5 days", "is_fresh": True, "threshold_days": 7}
    # Verify called with correct path
    mock_get_age.assert_called_with(CONSTANTS.AWS_REGIONS_FILE_PATH)

def test_get_pricing_age():
    response = client.get("/pricing_age/aws?pricing_region=eu-central-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "aws"
    assert payload["pricing_region"] == "eu-central-1"
    assert payload["active_reference"]["provider"] == "aws"
    assert payload["threshold_days"] == 7
    assert payload["status"] == "valid"

def test_get_pricing_age_incomplete():
    response = client.get("/pricing_age/azure?pricing_region=northeurope")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "azure",
        "pricing_region": "northeurope",
        "age": "missing",
        "schema_version": None,
        "contract_version": None,
        "status": "missing",
        "missing_keys": [],
        "quality_status": "review_required",
        "review_required": True,
        "fallback_fields": [],
        "unsupported_fields": [],
        "is_fresh": False,
        "threshold_days": 7,
        "active_reference": None,
    }

@patch("api.file_status.get_file_age_string")
def test_get_currency_age(mock_get_age):
    """Test GET /currency_age returns age string."""
    mock_get_age.return_value = "1 day"
    
    response = client.get("/currency_age")
    
    assert response.status_code == 200
    assert response.json() == {"age": "1 day"}
    mock_get_age.assert_called_with(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)

@patch("backend.pricing_utils.get_currency_rates")
def test_fetch_currency_rates(mock_get_rates):
    """Test POST /api/fetch_currency returns rates."""
    mock_get_rates.return_value = {"USD": 1.0, "EUR": 0.85}
    
    response = client.post("/fetch_currency")
    
    assert response.status_code == 200
    assert response.json() == {"USD": 1.0, "EUR": 0.85}
    mock_get_rates.assert_called_once()
