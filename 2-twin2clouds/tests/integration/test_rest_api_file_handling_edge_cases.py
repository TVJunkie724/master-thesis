
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.pricing_catalog_repository import PricingCatalogNotFoundError
from rest_api import app

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. File System Errors (Corrupt Cache / Permissions)
# -----------------------------------------------------------------------------

@patch("api.pricing._cached_refresh_result")
def test_pricing_endpoint_corrupt_cache(mock_cached_result):
    """Catalog integrity failures are never treated as valid cached pricing."""
    mock_cached_result.side_effect = Exception("Corrupt catalog")
    
    response = client.post("/fetch_pricing/aws?force_fetch=false")
    
    # The handler catches FileNotFoundError (404) and generic Exception differently.
    # A generic Exception from load_json_file returns 500 with a generic detail message.
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to fetch AWS pricing" in data["detail"]

# -----------------------------------------------------------------------------
# 2. Network/Fetch Failures
# -----------------------------------------------------------------------------

@patch("api.pricing.calculate_up_to_date_pricing")
def test_fetch_pricing_network_timeout(mock_calc):
    """Test fetch pricing endpoint handling network timeouts."""
    mock_calc.side_effect = TimeoutError("Connection timed out")
    
    response = client.post("/fetch_pricing/azure?force_fetch=true")
    
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to fetch Azure pricing" in data["detail"]

@patch("api.regions.initial_fetch_aws.fetch_region_map")
def test_fetch_regions_network_failure(mock_fetch):
    """Test fetch regions endpoint handling upstream API failure."""
    mock_fetch.side_effect = Exception("AWS API Down")
    
    response = client.post("/fetch_regions/aws?force_fetch=true")
    
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to fetch AWS regions" in data["detail"]

# -----------------------------------------------------------------------------
# 3. File Status Edge Cases
# -----------------------------------------------------------------------------

def test_get_pricing_age_returns_catalog_identity():
    """Pricing status is derived from immutable catalog metadata."""
    response = client.get("/pricing_age/aws")
    assert response.status_code == 200
    data = response.json()
    assert data["age"].endswith(("minutes", "hours", "days"))
    assert data["active_reference"]["snapshotId"].startswith("pcs_")
    assert data["pricing_region"] == "eu-central-1"

@patch("api.file_status.get_pricing_catalog_repository")
def test_get_pricing_age_catalog_not_found(mock_repository):
    """Missing provider-region catalogs return an explicit non-fresh state."""
    mock_repository.return_value.resolve_published.side_effect = (
        PricingCatalogNotFoundError("missing")
    )

    response = client.get("/pricing_age/aws")
    assert response.status_code == 200
    data = response.json()
    assert data["age"] == "missing"
    assert data["status"] == "missing"
    assert data["active_reference"] is None
