"""
Tests for /dashboard API endpoints.

Tests aggregate statistics for the dashboard overview.
"""

import pytest
from tests.conftest import create_test_twin


class TestDashboardStats:
    """Tests for /dashboard/stats endpoint."""

    def test_stats_empty(self, authenticated_client):
        """GET /dashboard/stats returns zeros for new user."""
        client, headers = authenticated_client
        
        response = client.get("/dashboard/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["deployed_count"] == 0
        assert data["draft_count"] == 0
        assert data["total_twins"] == 0
        assert data["estimated_monthly_cost"] == 0.0

    def test_stats_with_twins(self, authenticated_client):
        """Stats reflect created twins."""
        client, headers = authenticated_client
        
        # Create some twins (default state is draft)
        client.post("/twins/", json={"name": "Twin 1"}, headers=headers)
        client.post("/twins/", json={"name": "Twin 2"}, headers=headers)
        
        response = client.get("/dashboard/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_twins"] == 2
        assert data["draft_count"] == 2
        assert data["deployed_count"] == 0

    def test_stats_deployed_count(self, authenticated_client):
        """Stats correctly count deployed twins."""
        client, headers = authenticated_client
        
        # Create twin
        r = client.post("/twins/", json={"name": "Deployed Twin"}, headers=headers)
        twin_id = r.json()["id"]
        
        # Mark as deployed
        client.put(f"/twins/{twin_id}", json={"state": "deployed"}, headers=headers)
        
        response = client.get("/dashboard/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["deployed_count"] == 1
        assert data["draft_count"] == 0  # No longer draft

    def test_stats_draft_count(self, authenticated_client):
        """Stats correctly count draft twins separately from configured."""
        client, headers = authenticated_client
        
        # Create one draft and one configured twin
        client.post("/twins/", json={"name": "Draft Twin"}, headers=headers)
        r2 = client.post("/twins/", json={"name": "Configured Twin"}, headers=headers)
        client.put(f"/twins/{r2.json()['id']}", json={"state": "configured"}, headers=headers)
        
        response = client.get("/dashboard/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["draft_count"] == 1
        assert data["total_twins"] == 2
