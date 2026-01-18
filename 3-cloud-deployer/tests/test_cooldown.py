"""
Tests for the cooldown-check endpoint.

Tests the GCP Firestore 5-minute deployment cooldown check.
"""

import pytest
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from fastapi.testclient import TestClient

import rest_api

client = TestClient(rest_api.app)


class TestCooldownCheck:
    """Tests for GET /infrastructure/cooldown-check endpoint."""
    
    # =========== HAPPY PATH (2) ===========
    
    def test_first_deployment_no_prior_destroy(self):
        """First deployment with no destroyed_at → ready immediately."""
        response = client.get("/infrastructure/cooldown-check")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
        assert data["remaining_seconds"] == 0
    
    def test_redeploy_after_cooldown_elapsed(self):
        """Redeploy 6 minutes after destroy → ready."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        response = client.get(f"/infrastructure/cooldown-check?destroyed_at={quote(old_time)}")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
        assert data["remaining_seconds"] == 0
    
    # =========== ERROR CASES (2) ===========
    
    def test_redeploy_within_cooldown_returns_not_ready(self):
        """Redeploy 2 minutes after destroy → not ready, shows remaining."""
        recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        response = client.get(f"/infrastructure/cooldown-check?destroyed_at={quote(recent)}")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == False
        # Should be roughly 3 minutes remaining (180 seconds)
        assert 170 <= data["remaining_seconds"] <= 190
        assert "reason" in data
    
    def test_redeploy_immediately_after_destroy(self):
        """Redeploy 10 seconds after destroy → not ready, ~5 min remaining."""
        just_now = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        response = client.get(f"/infrastructure/cooldown-check?destroyed_at={quote(just_now)}")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == False
        assert 280 <= data["remaining_seconds"] <= 300
    
    # =========== EDGE CASES (5) ===========
    
    def test_invalid_timestamp_format_returns_ready(self):
        """Malformed timestamp → safe fallback, ready."""
        response = client.get("/infrastructure/cooldown-check?destroyed_at=not-a-date")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
        assert data["remaining_seconds"] == 0
    
    def test_empty_string_timestamp_returns_ready(self):
        """Empty string timestamp → treated as no prior destroy."""
        response = client.get("/infrastructure/cooldown-check?destroyed_at=")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
    
    def test_no_gcp_firestore_skips_cooldown(self):
        """uses_gcp_firestore=false → always ready, no cooldown."""
        just_now = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        response = client.get(
            f"/infrastructure/cooldown-check?destroyed_at={quote(just_now)}&uses_gcp_firestore=false"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
        assert data["remaining_seconds"] == 0
    
    def test_exactly_at_cooldown_boundary(self):
        """Exactly 5 minutes after destroy → ready."""
        exact_5min = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        response = client.get(f"/infrastructure/cooldown-check?destroyed_at={quote(exact_5min)}")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] == True
        assert data["remaining_seconds"] == 0
    
    def test_future_timestamp_returns_not_ready(self):
        """Future timestamp (clock skew) → not ready."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
        response = client.get(f"/infrastructure/cooldown-check?destroyed_at={quote(future)}")
        assert response.status_code == 200
        data = response.json()
        # Negative elapsed means we're before the destroy time
        # The cooldown calculation should handle this gracefully
        assert data["ready"] == False
