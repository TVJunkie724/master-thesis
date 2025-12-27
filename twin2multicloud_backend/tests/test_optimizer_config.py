"""
Unit tests for /twins/{id}/optimizer-config API endpoints.

Tests optimizer configuration persistence including:
- Happy path: save/load params and results
- Edge cases: partial saves, overwriting
- Error cases: invalid data, not found
"""

import pytest
from tests.conftest import create_test_twin


class TestOptimizerConfigRoutes:
    """Tests for /twins/{id}/optimizer-config endpoints."""

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_get_optimizer_config_default(self, authenticated_client):
        """GET optimizer-config returns empty defaults for new twin."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.get(f"/twins/{twin_id}/optimizer-config/", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["params"] is None
        assert data["result"] is None
        assert data["cheapest_path"] is None

    def test_save_optimizer_params(self, authenticated_client, sample_calc_params):
        """PUT optimizer-config/params saves calculation parameters."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/optimizer-config/", headers=headers)
        assert get_response.json()["params"] is not None

    def test_overwrite_params(self, authenticated_client, sample_calc_params):
        """Saving params multiple times overwrites previous."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers
        )
        
        updated_params = {**sample_calc_params, "numberOfDevices": 500}
        client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": updated_params},
            headers=headers
        )
        
        get_response = client.get(f"/twins/{twin_id}/optimizer-config/", headers=headers)
        saved_params = get_response.json()["params"]
        assert saved_params["numberOfDevices"] == 500

    # ============================================================
    # Error Case Tests
    # ============================================================

    def test_get_optimizer_config_not_found(self, authenticated_client):
        """GET optimizer-config for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.get("/twins/non-existent-id/optimizer-config/", headers=headers)
        
        assert response.status_code == 404

    def test_save_params_twin_not_found(self, authenticated_client, sample_calc_params):
        """PUT params for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.put(
            "/twins/non-existent-id/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers
        )
        
        assert response.status_code == 404
