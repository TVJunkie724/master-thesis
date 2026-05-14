"""
Unit tests for /twins/{id}/config API endpoints.

Tests credential management including:
- Happy path: store and retrieve config
- Security: credentials encrypted, never exposed in responses
- Edge cases: partial updates, multiple providers
"""

import json

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

    def test_omitted_provider_keeps_existing_legacy_credentials(
        self,
        authenticated_client,
        sample_aws_credentials,
        db_session,
    ):
        """Omitted provider fields mean unchanged, not cleared."""
        from src.models.twin_config import TwinConfiguration

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers,
        )

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"debug_mode": True},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["debug_mode"] is True
        assert data["aws_configured"] is True

        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        assert config.aws_access_key_id is not None
        assert config.aws_secret_access_key is not None

    def test_explicit_null_clears_legacy_aws_credentials(
        self,
        authenticated_client,
        sample_aws_credentials,
        db_session,
    ):
        """Explicit provider null means clear stored legacy credentials."""
        from src.models.twin_config import TwinConfiguration

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers,
        )

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": None},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["aws_configured"] is False
        assert data["aws_validated"] is False
        assert data["aws_cloud_connection_id"] is None

        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        assert config.aws_cloud_connection_id is None
        assert config.aws_access_key_id is None
        assert config.aws_secret_access_key is None
        assert config.aws_session_token is None
        assert config.aws_region == "eu-central-1"

    def test_explicit_null_clears_gcp_public_fields_and_secret(
        self,
        authenticated_client,
        sample_gcp_credentials,
        db_session,
    ):
        """GCP clear must remove public project metadata as well as secrets."""
        from src.models.twin_config import TwinConfiguration

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.put(
            f"/twins/{twin_id}/config/",
            json={"gcp": sample_gcp_credentials},
            headers=headers,
        )

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"gcp": None},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["gcp_configured"] is False
        assert data["gcp_validated"] is False
        assert data["gcp_project_id"] is None
        assert data["gcp_billing_account_configured"] is False

        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        assert config.gcp_cloud_connection_id is None
        assert config.gcp_project_id is None
        assert config.gcp_billing_account is None
        assert config.gcp_service_account_json is None
        assert config.gcp_region == "europe-west1"

    def test_gcp_legacy_credentials_require_service_account_json(
        self,
        authenticated_client,
    ):
        """Legacy GCP credentials must include the key used by deploy/validation."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={
                "gcp": {
                    "project_id": "my-project-12345",
                    "billing_account": "012345-6789AB-CDEF01",
                    "region": "europe-west1",
                }
            },
            headers=headers,
        )

        assert response.status_code == 422

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

    def test_update_config_binds_cloud_connection(self, authenticated_client, db_session):
        """PUT config can bind a twin to a user-owned CloudConnection."""
        from src.models.twin_config import TwinConfiguration

        client, headers = authenticated_client
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS SSOT",
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                },
            },
            headers=headers,
        ).json()
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"aws": connection["id"]}},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["aws_configured"] is True
        assert data["aws_cloud_connection_id"] == connection["id"]
        assert data["aws_region"] == "eu-central-1"

        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        assert config.aws_cloud_connection_id == connection["id"]
        assert config.aws_access_key_id is None
        assert config.aws_secret_access_key is None

    def test_update_config_rejects_wrong_provider_cloud_connection(self, authenticated_client):
        """Provider binding must match the selected CloudConnection provider."""
        client, headers = authenticated_client
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS SSOT",
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                },
            },
            headers=headers,
        ).json()
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"azure": connection["id"]}},
            headers=headers,
        )

        assert response.status_code == 400

    def test_update_config_rejects_unowned_cloud_connection(self, authenticated_client, db_session):
        """A twin cannot bind to another user's CloudConnection."""
        from src.models.cloud_connection import CloudConnection

        client, headers = authenticated_client
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS SSOT",
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                },
            },
            headers=headers,
        ).json()
        stored = db_session.query(CloudConnection).filter_by(id=connection["id"]).one()
        stored.user_id = "other-user"
        db_session.commit()
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"aws": connection["id"]}},
            headers=headers,
        )

        assert response.status_code == 404

    def test_validate_stored_dual_uses_bound_cloud_connection(self, authenticated_client, monkeypatch):
        """Stored dual validation should read credentials from the bound CloudConnection."""
        client, headers = authenticated_client
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS SSOT",
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                },
            },
            headers=headers,
        ).json()
        twin_id = create_test_twin(client, headers)
        client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"aws": connection["id"]}},
            headers=headers,
        )
        seen = {}

        async def fake_dual_validation(provider, optimizer_creds, deployer_creds):
            seen["provider"] = provider
            seen["optimizer_creds"] = optimizer_creds
            seen["deployer_creds"] = deployer_creds
            return {
                "provider": provider,
                "valid": True,
                "optimizer": {"valid": True, "message": "optimizer ok"},
                "deployer": {"valid": True, "message": "deployer ok", "permissions": []},
            }

        monkeypatch.setattr(
            "src.api.routes.config._perform_dual_validation",
            fake_dual_validation,
        )

        response = client.post(f"/twins/{twin_id}/config/validate-stored/aws", headers=headers)

        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert seen["provider"] == "aws"
        assert seen["optimizer_creds"]["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
        assert seen["deployer_creds"]["aws_secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    def test_validate_stored_gcp_cloud_connection_uses_resolver_without_placeholder(
        self,
        authenticated_client,
        monkeypatch,
    ):
        client, headers = authenticated_client
        service_account = {
            "type": "service_account",
            "project_id": "service-account-project",
            "client_email": "deployer@service-account-project.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----\\n",
        }
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "gcp",
                "display_name": "GCP Dev",
                "cloud_scope": {"billing_account": "012345-6789AB-CDEF01"},
                "gcp": {
                    "billing_account": "012345-6789AB-CDEF01",
                    "region": "europe-west1",
                    "service_account_json": json.dumps(service_account),
                },
            },
            headers=headers,
        ).json()
        twin_id = create_test_twin(client, headers)
        client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"gcp": connection["id"]}},
            headers=headers,
        )
        seen = {}

        async def fake_dual_validation(provider, optimizer_creds, deployer_creds):
            seen["provider"] = provider
            seen["optimizer_creds"] = optimizer_creds
            seen["deployer_creds"] = deployer_creds
            return {
                "provider": provider,
                "valid": True,
                "optimizer": {"valid": True, "message": "optimizer ok"},
                "deployer": {"valid": True, "message": "deployer ok", "permissions": []},
            }

        monkeypatch.setattr(
            "src.api.routes.config._perform_dual_validation",
            fake_dual_validation,
        )

        response = client.post(f"/twins/{twin_id}/config/validate-stored/gcp", headers=headers)

        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert seen["provider"] == "gcp"
        assert seen["optimizer_creds"]["gcp_project_id"] == "service-account-project"
        assert seen["deployer_creds"]["gcp_project_id"] == "service-account-project"
        assert "placeholder-project" not in str(seen)

    def test_validate_dual_gcp_plaintext_uses_resolver_without_placeholder(
        self,
        authenticated_client,
        monkeypatch,
    ):
        client, headers = authenticated_client
        service_account = {
            "type": "service_account",
            "project_id": "service-account-project",
            "client_email": "deployer@service-account-project.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----\\n",
        }
        seen = {}

        async def fake_dual_validation(provider, optimizer_creds, deployer_creds):
            seen["provider"] = provider
            seen["optimizer_creds"] = optimizer_creds
            seen["deployer_creds"] = deployer_creds
            return {
                "provider": provider,
                "valid": True,
                "optimizer": {"valid": True, "message": "optimizer ok"},
                "deployer": {"valid": True, "message": "deployer ok", "permissions": []},
            }

        monkeypatch.setattr(
            "src.api.routes.config._perform_dual_validation",
            fake_dual_validation,
        )

        response = client.post(
            "/config/validate-dual",
            json={
                "provider": "gcp",
                "gcp": {
                    "billing_account": "012345-6789AB-CDEF01",
                    "region": "europe-west1",
                    "service_account_json": json.dumps(service_account),
                },
            },
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert seen["provider"] == "gcp"
        assert seen["optimizer_creds"]["gcp_project_id"] == "service-account-project"
        assert seen["deployer_creds"]["gcp_project_id"] == "service-account-project"
        assert "placeholder-project" not in str(seen)

    def test_validate_inline_gcp_plaintext_missing_service_account_returns_structured_error(
        self,
        authenticated_client,
    ):
        client, headers = authenticated_client

        response = client.post(
            "/config/validate-inline",
            json={
                "provider": "gcp",
                "gcp": {
                    "project_id": "demo-project",
                    "region": "europe-west1",
                },
            },
            headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == {
            "code": "CREDENTIAL_RESOLUTION_FAILED",
            "message": "Cannot resolve deployment credentials",
            "errors": [
                {
                    "provider": "gcp",
                    "code": "MISSING_CREDENTIAL_FIELD",
                    "field": "gcp_credentials_file",
                    "message": "Missing required credential field: gcp_credentials_file",
                }
            ],
        }
