"""
Unit tests for /twins/{id}/config API endpoints.

Tests credential management including:
- Happy path: store and retrieve config
- Security: credentials encrypted, never exposed in responses
- Edge cases: partial updates, multiple providers
"""

import pytest
from tests.conftest import create_test_twin


class TestConfigRoutes:
    """Tests for /twins/{id}/config endpoints."""

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_get_config_creates_default(self, authenticated_client):
        """GET config auto-creates default config if missing."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["aws_configured"] == False
        assert data["azure_configured"] == False
        assert data["gcp_configured"] == False
        assert data["debug_mode"] == False

    def test_update_config_aws(self, authenticated_client, sample_aws_credentials):
        """PUT config stores AWS credentials."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Verify config updated
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        assert get_response.json()["aws_configured"] == True

    def test_update_config_azure(self, authenticated_client, sample_azure_credentials):
        """PUT config stores Azure credentials."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"azure": sample_azure_credentials},
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        assert get_response.json()["azure_configured"] == True

    def test_update_config_gcp(self, authenticated_client, sample_gcp_credentials):
        """PUT config stores GCP credentials."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"gcp": sample_gcp_credentials},
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        assert get_response.json()["gcp_configured"] == True

    def test_update_debug_mode(self, authenticated_client):
        """PUT config updates debug_mode flag."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"debug_mode": True},
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        assert get_response.json()["debug_mode"] == True

    # ============================================================
    # Security Tests
    # ============================================================

    def test_credentials_never_exposed(self, authenticated_client, sample_aws_credentials):
        """API responses should never contain actual credentials."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        # Store credentials
        client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers
        )
        
        # Get config
        response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        response_str = str(response.json())
        
        # Ensure secrets not in response
        assert sample_aws_credentials["access_key_id"] not in response_str
        assert sample_aws_credentials["secret_access_key"] not in response_str

    def test_credentials_stored_encrypted(self, authenticated_client, sample_aws_credentials, db_session):
        """Credentials should be encrypted in database."""
        from src.models.twin_config import TwinConfiguration
        from src.models.user import User
        
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        # Store credentials
        client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers
        )
        
        # Check raw database value
        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).first()
        
        # Should be encrypted (starts with gAAAAA for Fernet)
        assert config.aws_access_key_id is not None
        assert config.aws_access_key_id != sample_aws_credentials["access_key_id"]
        assert config.aws_access_key_id.startswith("gAAAAA")

    # ============================================================
    # Edge Case Tests
    # ============================================================

    def test_update_multiple_providers(self, authenticated_client, sample_aws_credentials, sample_azure_credentials):
        """Update multiple providers in single request."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={
                "aws": sample_aws_credentials,
                "azure": sample_azure_credentials
            },
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        data = get_response.json()
        assert data["aws_configured"] == True
        assert data["azure_configured"] == True

    def test_partial_config_update(self, authenticated_client, sample_aws_credentials):
        """Update only AWS, other configs should remain unchanged."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        # Set debug_mode first
        client.put(
            f"/twins/{twin_id}/config/",
            json={"debug_mode": True},
            headers=headers
        )
        
        # Now update AWS only
        client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers
        )
        
        # Debug mode should still be true
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        assert get_response.json()["debug_mode"] == True

    # ============================================================
    # Error Case Tests
    # ============================================================

    def test_config_not_found(self, authenticated_client):
        """GET config for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.get("/twins/non-existent-id/config/", headers=headers)
        
        assert response.status_code == 404

    def test_update_config_twin_not_found(self, authenticated_client, sample_aws_credentials):
        """PUT config for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.put(
            "/twins/non-existent-id/config/",
            json={"aws": sample_aws_credentials},
            headers=headers
        )
        
        assert response.status_code == 404
