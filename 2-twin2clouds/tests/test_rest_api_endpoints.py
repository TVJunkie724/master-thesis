from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
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

@patch("api.file_status.get_file_age_string")
def test_get_regions_age_aws(mock_get_age):
    """Test GET /api/regions_age/aws returns age string."""
    mock_get_age.return_value = "5 days"
    
    response = client.get("/api/regions_age/aws")
    
    assert response.status_code == 200
    assert response.json() == {"age": "5 days"}
    # Verify called with correct path
    mock_get_age.assert_called_with(CONSTANTS.AWS_REGIONS_FILE_PATH)

def test_get_pricing_age():
    with patch("api.file_status.get_file_age_string") as mock_age, \
         patch("api.file_status.load_json_file") as mock_load, \
         patch("backend.pricing_utils.validate_pricing_schema") as mock_validate, \
         patch("os.path.isfile") as mock_isfile:
        
        mock_age.return_value = "2 days"
        mock_isfile.return_value = True
        mock_load.return_value = {"some": "data"}
        mock_validate.return_value = {"status": "valid", "missing_keys": []}
        
        response = client.get("/api/pricing_age/aws")
        assert response.status_code == 200
        assert response.json() == {
            "age": "2 days",
            "status": "valid",
            "missing_keys": []
        }
        mock_age.assert_called_with(CONSTANTS.AWS_PRICING_FILE_PATH)
        mock_validate.assert_called_with("aws", {"some": "data"})

def test_get_pricing_age_incomplete():
    with patch("api.file_status.get_file_age_string") as mock_age, \
         patch("api.file_status.load_json_file") as mock_load, \
         patch("backend.pricing_utils.validate_pricing_schema") as mock_validate, \
         patch("os.path.isfile") as mock_isfile:
        
        mock_age.return_value = "5 hours"
        mock_isfile.return_value = True
        mock_load.return_value = {"some": "data"}
        mock_validate.return_value = {"status": "incomplete", "missing_keys": ["service.key"]}
        
        response = client.get("/api/pricing_age/azure")
        assert response.status_code == 200
        assert response.json() == {
            "age": "5 hours",
            "status": "incomplete",
            "missing_keys": ["service.key"]
        }

@patch("api.file_status.get_file_age_string")
def test_get_currency_age(mock_get_age):
    """Test GET /api/currency_age returns age string."""
    mock_get_age.return_value = "1 day"
    
    response = client.get("/api/currency_age")
    
    assert response.status_code == 200
    assert response.json() == {"age": "1 day"}
    mock_get_age.assert_called_with(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)

@patch("backend.pricing_utils.get_currency_rates")
def test_fetch_currency_rates(mock_get_rates):
    """Test POST /api/fetch_currency returns rates."""
    mock_get_rates.return_value = {"USD": 1.0, "EUR": 0.85}
    
    response = client.post("/api/fetch_currency")
    
    assert response.status_code == 200
    assert response.json() == {"USD": 1.0, "EUR": 0.85}
    mock_get_rates.assert_called_once()
