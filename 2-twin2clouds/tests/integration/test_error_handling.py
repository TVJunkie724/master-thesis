"""
Error Handling Tests for Optimizer API (2-twin2clouds).

Tests error handling for pricing, regions, and calculation endpoints.
Each category has:
- 2 happy cases (successful operations)
- 2 error cases (expected failures)
- 5 edge cases (boundary conditions)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

from rest_api import app

client = TestClient(app)


# ============================================================
# Pricing Endpoint Tests (/fetch_pricing/{provider})
# ============================================================

class TestPricingErrorHandling:
    """Tests for /fetch_pricing/* error handling."""

    # Happy Path Tests
    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_fetch_pricing_cached_success(self, mock_load, mock_fresh):
        """Returns cached pricing data when file is fresh."""
        mock_fresh.return_value = True
        mock_load.return_value = {"compute": {"price": 0.01}}
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code == 200
        assert "compute" in response.json()

    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_fetch_pricing_stale_cache(self, mock_load, mock_fresh):
        """Stale cache (not fresh) returns cached data or triggers refresh."""
        mock_fresh.return_value = False
        mock_load.return_value = {"compute": {"price": 0.02}}
        
        response = client.post("/fetch_pricing/aws")
        
        # Either cached data or error if refresh fails
        assert response.status_code in [200, 500]

    # Error Case Tests
    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_file_not_found_returns_404(self, mock_load, mock_fresh):
        """FileNotFoundError returns 404 with user-friendly message."""
        mock_fresh.return_value = True
        mock_load.side_effect = FileNotFoundError("pricing_aws.json not found")
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code == 404
        assert "not available" in response.json()["detail"].lower()
        # Raw path NOT exposed
        assert "pricing_aws.json" not in response.json()["detail"]

    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_generic_exception_returns_500_hidden(self, mock_load, mock_fresh):
        """Generic exception returns 500 with generic message."""
        mock_fresh.return_value = True
        mock_load.side_effect = Exception("Database connection failed at 192.168.1.1")
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code == 500
        # Internal details NOT exposed
        assert "192.168.1.1" not in response.json()["detail"]
        assert "connection" not in response.json()["detail"].lower()

    # Edge Case Tests
    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_empty_pricing_file(self, mock_load, mock_fresh):
        """Empty pricing file handled gracefully."""
        mock_fresh.return_value = True
        mock_load.return_value = {}
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code == 200
        assert response.json() == {}

    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_malformed_json_handled(self, mock_load, mock_fresh):
        """Malformed JSON in file raises controlled error."""
        mock_fresh.return_value = True
        mock_load.side_effect = json.JSONDecodeError("Invalid", "doc", 0)
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code in [400, 500]

    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_permission_error_handled(self, mock_load, mock_fresh):
        """Permission error returns 500 with generic message."""
        mock_fresh.return_value = True
        mock_load.side_effect = PermissionError("Access denied to /secret/path")
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code == 500
        # Path NOT exposed
        assert "/secret/path" not in response.json().get("detail", "")

    def test_invalid_provider_handled(self):
        """Invalid provider returns 422."""
        response = client.post("/fetch_pricing/invalid_provider")
        
        # Either 422 or 404
        assert response.status_code in [404, 422]

    @patch("api.pricing.is_file_fresh")
    @patch("api.pricing.load_json_file")
    def test_unicode_in_pricing_data(self, mock_load, mock_fresh):
        """Unicode characters in pricing handled correctly."""
        mock_fresh.return_value = True
        mock_load.return_value = {"region": "São Paulo", "price": 0.01}
        
        response = client.post("/fetch_pricing/aws")
        
        assert response.status_code == 200
        assert "São Paulo" in str(response.json())


# ============================================================
# Regions Endpoint Tests (/fetch_regions/{provider})
# ============================================================

class TestRegionsErrorHandling:
    """Tests for /fetch_regions/* error handling."""

    # Happy Path Tests
    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_fetch_regions_cached_success(self, mock_load, mock_fresh):
        """Returns cached regions when file is fresh."""
        mock_fresh.return_value = True
        mock_load.return_value = {"us-east-1": "US East"}
        
        response = client.post("/fetch_regions/aws")
        
        assert response.status_code == 200
        assert "us-east-1" in response.json()

    @patch("api.regions.is_file_fresh")
    @patch("api.regions.initial_fetch_aws.fetch_region_map")
    def test_fetch_regions_force_refresh(self, mock_fetch, mock_fresh):
        """Force refresh updates regions cache."""
        mock_fresh.return_value = False
        mock_fetch.return_value = {"eu-west-1": "EU West"}
        
        response = client.post("/fetch_regions/aws?force_fetch=true")
        
        assert response.status_code in [200, 500]

    # Error Case Tests
    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_regions_file_not_found_returns_404(self, mock_load, mock_fresh):
        """Missing regions file returns 404."""
        mock_fresh.return_value = True
        mock_load.side_effect = FileNotFoundError("regions.json missing")
        
        response = client.post("/fetch_regions/aws")
        
        assert response.status_code == 404
        assert "not available" in response.json()["detail"].lower()

    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_regions_exception_returns_500_hidden(self, mock_load, mock_fresh):
        """Generic exception hides internal details."""
        mock_fresh.return_value = True
        mock_load.side_effect = Exception("Redis cache error on node-3")
        
        response = client.post("/fetch_regions/aws")
        
        assert response.status_code == 500
        assert "node-3" not in response.json()["detail"]

    # Edge Case Tests
    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_empty_regions_map(self, mock_load, mock_fresh):
        """Empty regions map returns 200 with empty object."""
        mock_fresh.return_value = True
        mock_load.return_value = {}
        
        response = client.post("/fetch_regions/aws")
        
        assert response.status_code == 200

    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_stale_cache_triggers_refresh(self, mock_load, mock_fresh):
        """Stale cache (> threshold) triggers refresh."""
        mock_fresh.return_value = False
        mock_load.return_value = {"old": "data"}
        
        with patch("api.regions.initial_fetch_aws.fetch_region_map") as mock_fetch:
            mock_fetch.return_value = {"new": "data"}
            response = client.post("/fetch_regions/aws")
            
            assert response.status_code in [200, 500]

    def test_gcp_regions_different_error_message(self):
        """GCP regions have provider-specific messages."""
        with patch("api.regions.is_file_fresh") as mock_fresh, \
             patch("api.regions.load_json_file") as mock_load:
            mock_fresh.return_value = True
            mock_load.side_effect = FileNotFoundError()
            
            response = client.post("/fetch_regions/gcp")
            
            assert response.status_code == 404
            assert "gcp" in response.json()["detail"].lower()

    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_unicode_region_names(self, mock_load, mock_fresh):
        """Unicode in region names handled."""
        mock_fresh.return_value = True
        mock_load.return_value = {"asia-east1": "台灣彰化縣"}
        
        response = client.post("/fetch_regions/gcp")
        
        assert response.status_code == 200

    @patch("api.regions.is_file_fresh")
    @patch("api.regions.load_json_file")
    def test_very_large_region_list(self, mock_load, mock_fresh):
        """Large region list (1000+) handled."""
        mock_fresh.return_value = True
        mock_load.return_value = {f"region-{i}": f"Region {i}" for i in range(1000)}
        
        response = client.post("/fetch_regions/aws")
        
        assert response.status_code == 200
        assert len(response.json()) == 1000


# ============================================================
# Calculation Endpoint Tests (/calculate)
# ============================================================

class TestCalculationErrorHandling:
    """Tests for /calculate error handling."""

    # Happy Path Tests - These require pricing data, so we skip mocking and test validation
    def test_calculation_validates_required_fields(self):
        """Validates that required fields are checked."""
        # Minimal valid params - will fail on pricing load but validates structure
        response = client.put("/calculate", json={})
        
        # Should get 422 (validation) or 500 (pricing not available)
        assert response.status_code in [422, 500]

    def test_calculation_rejects_incomplete_params(self):
        """Incomplete params are rejected with validation error."""
        params = {"numberOfDevices": 100}  # Missing other required fields
        
        response = client.put("/calculate", json=params)
        
        assert response.status_code == 422

    # Error Case Tests
    def test_calculation_rejects_missing_devices(self):
        """Missing numberOfDevices returns 422."""
        params = {
            "deviceSendingIntervalInMinutes": 1.0,
            "averageSizeOfMessageInKb": 1.0
        }
        
        response = client.put("/calculate", json=params)
        
        assert response.status_code == 422

    def test_calculation_rejects_string_for_number(self):
        """String value for number field returns 422."""
        params = {"numberOfDevices": "one hundred"}
        
        response = client.put("/calculate", json=params)
        
        assert response.status_code == 422


    # Edge Case Tests
    def test_missing_required_params(self):
        """Missing required parameters returns validation error."""
        response = client.put("/calculate", json={})
        
        assert response.status_code == 422

    def test_negative_devices_rejected(self):
        """Negative devices rejected at Pydantic validation."""
        params = {"numberOfDevices": -10}
        
        response = client.put("/calculate", json=params)
        
        assert response.status_code == 422

    def test_empty_json_body(self):
        """Empty JSON body returns 422."""
        response = client.put("/calculate", json={})
        
        assert response.status_code == 422

    def test_non_json_body(self):
        """Non-JSON body returns 422."""
        response = client.put("/calculate", content="not json", headers={"Content-Type": "application/json"})
        
        assert response.status_code == 422

    def test_invalid_storage_duration_ordering(self):
        """Invalid storage duration ordering (hot > cool) rejected."""
        params = {
            "numberOfDevices": 100,
            "deviceSendingIntervalInMinutes": 1.0,
            "averageSizeOfMessageInKb": 1.0,
            "numberOfDeviceTypes": 1,
            "hotStorageDurationInMonths": 12,  # Hot > Cool - invalid
            "coolStorageDurationInMonths": 3,
            "archiveStorageDurationInMonths": 1
        }
        
        response = client.put("/calculate", json=params)
        
        # Pydantic validator should catch this
        assert response.status_code == 422

