"""
Unit tests for /health endpoint.

Tests API health monitoring including:
- Service availability
- Response format
"""

import pytest


class TestHealthRoutes:
    """Tests for /health endpoint."""

    def test_health_check(self, client):
        """GET /health returns 200 and status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_no_auth_required(self, client):
        """Health endpoint should not require authentication."""
        # Call without auth headers
        response = client.get("/health")
        
        assert response.status_code == 200
