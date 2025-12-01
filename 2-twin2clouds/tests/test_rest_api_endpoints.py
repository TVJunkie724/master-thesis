from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from rest_api import app
import backend.constants as CONSTANTS

client = TestClient(app)

# ----------------------------------------------------------------
# Region Fetching Tests
# ----------------------------------------------------------------

@patch("backend.fetch_data.initial_fetch_aws.fetch_region_map")
def test_fetch_regions_aws(mock_fetch):
    """Test POST /api/fetch_regions/aws triggers force update."""
    mock_fetch.return_value = {"us-east-1": "US East (N. Virginia)"}
    
    response = client.post("/api/fetch_regions/aws")
    
    assert response.status_code == 200
    assert response.json() == {"us-east-1": "US East (N. Virginia)"}
    mock_fetch.assert_called_once_with(force_update=True)

@patch("backend.fetch_data.initial_fetch_azure.fetch_region_map")
def test_fetch_regions_azure(mock_fetch):
    """Test POST /api/fetch_regions/azure triggers force update."""
    mock_fetch.return_value = {"westeurope": "West Europe"}
    
    response = client.post("/api/fetch_regions/azure")
    
    assert response.status_code == 200
    assert response.json() == {"westeurope": "West Europe"}
    mock_fetch.assert_called_once_with(force_update=True)

@patch("backend.fetch_data.initial_fetch_google.fetch_region_map")
def test_fetch_regions_gcp(mock_fetch):
    """Test POST /api/fetch_regions/gcp triggers force update."""
    mock_fetch.return_value = {"us-central1": "us-central1"}
    
    response = client.post("/api/fetch_regions/gcp")
    
    assert response.status_code == 200
    assert response.json() == {"us-central1": "us-central1"}
    mock_fetch.assert_called_once_with(force_update=True)

# ----------------------------------------------------------------
# File Age Tests
# ----------------------------------------------------------------

@patch("rest_api.get_file_age_string")
def test_get_regions_age_aws(mock_get_age):
    """Test GET /api/regions_age/aws returns age string."""
    mock_get_age.return_value = "5 days"
    
    response = client.get("/api/regions_age/aws")
    
    assert response.status_code == 200
    assert response.json() == {"age": "5 days"}
    # Verify called with correct path
    mock_get_age.assert_called_with(CONSTANTS.AWS_REGIONS_FILE_PATH)

@patch("rest_api.get_file_age_string")
def test_get_pricing_age_azure(mock_get_age):
    """Test GET /api/pricing_age/azure returns age string."""
    mock_get_age.return_value = "2 hours"
    
    response = client.get("/api/pricing_age/azure")
    
    assert response.status_code == 200
    assert response.json() == {"age": "2 hours"}
    mock_get_age.assert_called_with(CONSTANTS.AZURE_PRICING_FILE_PATH)
