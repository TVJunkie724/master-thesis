"""
Tests for the can-redeploy endpoint.

Tests the /twins/{id}/can-redeploy endpoint that proxies to Deployer API
for GCP Firestore cooldown checking.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from tests.conftest import create_test_twin
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState


class TestCanRedeploy:
    """Tests for GET /twins/{id}/can-redeploy endpoint."""
    
    # =========== HAPPY PATH (2) ===========
    
    def test_first_deploy_no_destroyed_at(self, authenticated_client):
        """First deployment (no destroyed_at) → ready immediately."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownHappy1")
        
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
        assert data["remaining_seconds"] == 0
    
    def test_non_gcp_provider_always_ready(self, authenticated_client):
        """Non-GCP L3 hot provider → always ready (no cooldown)."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownHappy2")
        
        # Even with destroyed_at set, non-GCP should be ready
        # (but destroyed_at is None by default, so this just tests the path)
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
    
    # =========== ERROR CASES (2) ===========
    
    def test_twin_not_found_returns_404(self, authenticated_client):
        """Non-existent twin_id → 404."""
        client, headers = authenticated_client
        
        response = client.get("/twins/nonexistent-id-12345/can-redeploy", headers=headers)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_other_users_twin_returns_404(self, authenticated_client):
        """Trying to access another user's twin → 404 (not exposed)."""
        client, headers = authenticated_client
        
        # Try to access a random UUID that doesn't belong to this user
        response = client.get("/twins/00000000-0000-0000-0000-000000000000/can-redeploy", headers=headers)
        
        # Should be 404 (twin not found for this user)
        assert response.status_code == 404
    
    # =========== EDGE CASES (5) ===========
    
    def test_twin_without_deployer_config_ready(self, authenticated_client):
        """Twin without deployer config → defaults to ready."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownEdge1")
        
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        assert response.status_code == 200
        assert response.json()["ready"] == True
    
    def test_deleted_twin_returns_404(self, authenticated_client):
        """Soft-deleted twin → 404."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownEdge2")
        
        # Delete the twin
        client.delete(f"/twins/{twin_id}", headers=headers)
        
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        # Deleted twins are filtered out, so should be 404
        assert response.status_code == 404
    
    def test_response_includes_remaining_seconds(self, authenticated_client):
        """Response always includes remaining_seconds field."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownEdge3")
        
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "remaining_seconds" in data
    
    def test_ready_is_boolean(self, authenticated_client):
        """ready field is always a boolean."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownEdge4")
        
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        assert response.status_code == 200
        assert isinstance(response.json()["ready"], bool)
    
    def test_remaining_seconds_is_integer(self, authenticated_client):
        """remaining_seconds field is always an integer."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers, "Test Twin CooldownEdge5")
        
        response = client.get(f"/twins/{twin_id}/can-redeploy", headers=headers)
        
        assert response.status_code == 200
        assert isinstance(response.json()["remaining_seconds"], int)

    @pytest.mark.asyncio
    async def test_gcp_firestore_twin_proxies_cooldown_check(self, auth_client, db, test_twin):
        """GCP L3 hot twins with destroyed_at use the Deployer cooldown check."""
        test_twin.state = TwinState.DESTROYED
        test_twin.destroyed_at = datetime.utcnow() - timedelta(minutes=1)
        db.add(
            OptimizerConfiguration(
                twin_id=test_twin.id,
                cheapest_l3_hot="GCP",
            )
        )
        db.commit()

        async def fake_check_cooldown(self, destroyed_at, uses_gcp_firestore):
            assert destroyed_at == test_twin.destroyed_at
            assert uses_gcp_firestore is True
            return {"ready": False, "remaining_seconds": 111}

        with patch(
            "src.clients.deployer_client.DeployerClient.check_cooldown",
            new=fake_check_cooldown,
        ):
            response = auth_client.get(f"/twins/{test_twin.id}/can-redeploy")

        assert response.status_code == 200
        assert response.json() == {"ready": False, "remaining_seconds": 111}
