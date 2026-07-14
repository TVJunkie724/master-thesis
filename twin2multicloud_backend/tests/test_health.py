"""
Unit tests for /health endpoint.

Tests API health monitoring including:
- Service availability
- Response format
"""

from src.main import app
from src.models.database import get_db


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

    def test_unhealthy_database_returns_503_without_internal_error_text(self, client):
        class FailingSession:
            def execute(self, _statement):
                raise RuntimeError("password=DO-NOT-EXPOSE database-host.internal")

        def override_failing_db():
            yield FailingSession()

        app.dependency_overrides[get_db] = override_failing_db

        response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {"status": "unhealthy", "database": "unavailable"}
        assert "DO-NOT-EXPOSE" not in response.text
        assert "database-host.internal" not in response.text
