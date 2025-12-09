
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from rest_api import app

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. File System Errors (Corrupt Cache / Permissions)
# -----------------------------------------------------------------------------

@patch("api.pricing.load_json_file")
@patch("api.pricing.is_file_fresh")
def test_pricing_endpoint_corrupt_cache(mock_is_fresh, mock_load):
    """Test behavior when the cached file is corrupted (JSON decode error)."""
    mock_is_fresh.return_value = True
    mock_load.side_effect = Exception("Corrupt JSON")
    
    response = client.post("/api/fetch_pricing/aws?force_fetch=false")
    
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "Corrupt JSON" in data["error"]

# -----------------------------------------------------------------------------
# 2. Network/Fetch Failures
# -----------------------------------------------------------------------------

@patch("api.pricing.calculate_up_to_date_pricing")
def test_fetch_pricing_network_timeout(mock_calc):
    """Test fetch pricing endpoint handling network timeouts."""
    mock_calc.side_effect = TimeoutError("Connection timed out")
    
    response = client.post("/api/fetch_pricing/azure?force_fetch=true")
    
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "Connection timed out" in data["error"]

@patch("api.regions.initial_fetch_aws.fetch_region_map")
def test_fetch_regions_network_failure(mock_fetch):
    """Test fetch regions endpoint handling upstream API failure."""
    mock_fetch.side_effect = Exception("AWS API Down")
    
    response = client.post("/api/fetch_regions/aws?force_fetch=true")
    
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "AWS API Down" in data["error"]

# -----------------------------------------------------------------------------
# 3. File Status Edge Cases
# -----------------------------------------------------------------------------

@patch("api.file_status.get_file_age_string")
def test_get_pricing_age_returns_age_string(mock_age_str):
    """Test that pricing age endpoint correctly returns the age string."""
    mock_age_str.return_value = "2 days, 3 hours"
    
    response = client.get("/api/pricing_age/aws")
    assert response.status_code == 200
    data = response.json()
    assert data["age"] == "2 days, 3 hours"

@patch("api.file_status.get_file_age_string")
def test_get_pricing_age_file_not_found(mock_age_str):
    """Test pricing age returns appropriate message when file doesn't exist."""
    # When file doesn't exist, get_file_age_string returns "File not found" or similar
    mock_age_str.return_value = "File not found"
    
    response = client.get("/api/pricing_age/aws")
    assert response.status_code == 200
    data = response.json()
    assert "not found" in data["age"].lower()
