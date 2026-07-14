"""
Unit tests for /twins/{id}/config API endpoints.

Tests credential management including:
- Happy path: store and retrieve config
- Security: credentials encrypted, never exposed in responses
- Edge cases: partial updates, multiple providers
"""

import json

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
        assert data["aws_configured"] is False
        assert data["azure_configured"] is False
        assert data["gcp_configured"] is False
        assert data["debug_mode"] is False
        assert data["twin_state"] == "draft"
        assert data["configured_providers"] == []
        assert data["credential_sources"] == {
            "aws": None,
            "azure": None,
            "gcp": None,
        }

    def test_update_config_rejects_direct_aws_credentials(self, authenticated_client, sample_aws_credentials):
        """PUT config rejects per-twin AWS credential storage."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"aws": sample_aws_credentials},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Cloud Connection" in response.json()["detail"]

    def test_update_config_rejects_direct_azure_credentials(self, authenticated_client, sample_azure_credentials):
        """PUT config rejects per-twin Azure credential storage."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"azure": sample_azure_credentials},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Cloud Connection" in response.json()["detail"]

    def test_update_config_rejects_direct_gcp_credentials(self, authenticated_client, sample_gcp_credentials):
        """PUT config rejects per-twin GCP credential storage."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"gcp": sample_gcp_credentials},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Cloud Connection" in response.json()["detail"]

    def test_config_read_model_reports_credential_sources(
        self,
        authenticated_client,
    ):
        """Read model exposes secret-safe source metadata for Flutter hydration."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        aws_connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS Dev Account",
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                },
            },
            headers=headers,
        ).json()
        azure_connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "azure",
                "display_name": "Azure Dev Account",
                "azure": {
                    "subscription_id": "subscription-id",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "tenant_id": "tenant-id",
                    "region": "westeurope",
                },
            },
            headers=headers,
        ).json()

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={
                "cloud_connections": {
                    "aws": aws_connection["id"],
                    "azure": azure_connection["id"],
                },
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["aws_configured"] is True
        assert data["aws_credential_source"] == "cloud_connection"
        assert data["azure_configured"] is True
        assert data["azure_credential_source"] == "cloud_connection"
        assert data["gcp_configured"] is False
        assert data["gcp_credential_source"] is None
        assert data["configured_providers"] == ["aws", "azure"]
        assert data["credential_sources"] == {
            "aws": "cloud_connection",
            "azure": "cloud_connection",
            "gcp": None,
        }
        assert data["cloud_connections"]["aws"]["id"] == aws_connection["id"]
        assert data["cloud_connections"]["aws"]["display_name"] == "AWS Dev Account"
        assert data["cloud_connections"]["aws"]["validation_status"] == "untested"

    def test_gcp_project_metadata_alone_is_not_configured(
        self,
        authenticated_client,
        db_session,
    ):
        """Public GCP project metadata must not hydrate as usable credentials."""
        from src.models.twin_config import TwinConfiguration

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.get(f"/twins/{twin_id}/config/", headers=headers)

        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        config.gcp_project_id = "metadata-only-project"
        config.gcp_region = "europe-west1"
        db_session.commit()

        response = client.get(f"/twins/{twin_id}/config/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["gcp_project_id"] == "metadata-only-project"
        assert data["gcp_configured"] is False
        assert data["gcp_credential_source"] is None
        assert "gcp" not in data["configured_providers"]

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
        assert get_response.json()["debug_mode"] is True

    # ============================================================
    # Security Tests
    # ============================================================

    def test_credentials_never_exposed(self, authenticated_client, sample_aws_credentials):
        """API responses should never contain actual credentials."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS Secret Safety",
                "aws": sample_aws_credentials,
            },
            headers=headers,
        ).json()
        client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"aws": connection["id"]}},
            headers=headers
        )
        
        # Get config
        response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        response_str = str(response.json())
        
        # Ensure secrets not in response
        assert sample_aws_credentials["access_key_id"] not in response_str
        assert sample_aws_credentials["secret_access_key"] not in response_str

    def test_credentials_stored_encrypted(self, authenticated_client, sample_aws_credentials, db_session):
        """CloudConnection credentials should be encrypted in database."""
        from src.models.cloud_connection import CloudConnection
        
        client, headers = authenticated_client
        
        response = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "display_name": "AWS Encrypted",
                "aws": sample_aws_credentials,
            },
            headers=headers
        )
        assert response.status_code == 200
        
        stored = db_session.query(CloudConnection).filter_by(id=response.json()["id"]).one()
        
        # Should be encrypted (starts with gAAAAA for Fernet)
        assert stored.encrypted_payload is not None
        assert stored.encrypted_payload.startswith("gAAAAA")
        assert sample_aws_credentials["access_key_id"] not in stored.encrypted_payload
        assert sample_aws_credentials["secret_access_key"] not in stored.encrypted_payload

    # ============================================================
    # Edge Case Tests
    # ============================================================

    def test_update_multiple_provider_connections(self, authenticated_client, sample_aws_credentials, sample_azure_credentials):
        """Update multiple CloudConnection bindings in single request."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        aws_connection = client.post(
            "/cloud-connections/",
            json={"provider": "aws", "display_name": "AWS", "aws": sample_aws_credentials},
            headers=headers,
        ).json()
        azure_connection = client.post(
            "/cloud-connections/",
            json={"provider": "azure", "display_name": "Azure", "azure": sample_azure_credentials},
            headers=headers,
        ).json()
        
        response = client.put(
            f"/twins/{twin_id}/config/",
            json={
                "cloud_connections": {
                    "aws": aws_connection["id"],
                    "azure": azure_connection["id"],
                }
            },
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        data = get_response.json()
        assert data["aws_configured"] is True
        assert data["azure_configured"] is True

    def test_partial_config_update(self, authenticated_client, sample_aws_credentials):
        """Update only AWS, other configs should remain unchanged."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        connection = client.post(
            "/cloud-connections/",
            json={"provider": "aws", "display_name": "AWS", "aws": sample_aws_credentials},
            headers=headers,
        ).json()
        
        # Set debug_mode first
        client.put(
            f"/twins/{twin_id}/config/",
            json={"debug_mode": True},
            headers=headers
        )
        
        # Now update AWS only
        client.put(
            f"/twins/{twin_id}/config/",
            json={"cloud_connections": {"aws": connection["id"]}},
            headers=headers
        )
        
        # Debug mode should still be true
        get_response = client.get(f"/twins/{twin_id}/config/", headers=headers)
        assert get_response.json()["debug_mode"] is True

    def test_omitted_provider_does_not_treat_legacy_columns_as_configured(
        self,
        authenticated_client,
        sample_aws_credentials,
        db_session,
    ):
        """Omitted provider fields mean unchanged, but legacy columns stay inactive."""
        from src.models.twin_config import TwinConfiguration
        from src.utils.crypto import encrypt

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.get(f"/twins/{twin_id}/config/", headers=headers)
        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        config.aws_access_key_id = encrypt(sample_aws_credentials["access_key_id"], "dev-user-id", twin_id)
        config.aws_secret_access_key = encrypt(sample_aws_credentials["secret_access_key"], "dev-user-id", twin_id)
        db_session.commit()

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"debug_mode": True},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["debug_mode"] is True
        assert data["aws_configured"] is False
        assert data["aws_credential_source"] is None

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
        from src.utils.crypto import encrypt

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.get(f"/twins/{twin_id}/config/", headers=headers)
        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        config.aws_access_key_id = encrypt(sample_aws_credentials["access_key_id"], "dev-user-id", twin_id)
        config.aws_secret_access_key = encrypt(sample_aws_credentials["secret_access_key"], "dev-user-id", twin_id)
        config.aws_session_token = encrypt("session-token", "dev-user-id", twin_id)
        db_session.commit()

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

    def test_explicit_null_clears_legacy_azure_credentials(
        self,
        authenticated_client,
        sample_azure_credentials,
        db_session,
    ):
        """Azure clear must remove all encrypted fields and region overrides."""
        from src.models.twin_config import TwinConfiguration
        from src.utils.crypto import encrypt

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.get(f"/twins/{twin_id}/config/", headers=headers)
        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        config.azure_subscription_id = encrypt(sample_azure_credentials["subscription_id"], "dev-user-id", twin_id)
        config.azure_client_id = encrypt(sample_azure_credentials["client_id"], "dev-user-id", twin_id)
        config.azure_client_secret = encrypt(sample_azure_credentials["client_secret"], "dev-user-id", twin_id)
        config.azure_tenant_id = encrypt(sample_azure_credentials["tenant_id"], "dev-user-id", twin_id)
        config.azure_region = sample_azure_credentials["region"]
        config.azure_region_iothub = "northeurope"
        config.azure_region_digital_twin = "switzerlandnorth"
        db_session.commit()

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"azure": None},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["azure_configured"] is False
        assert data["azure_validated"] is False
        assert data["azure_cloud_connection_id"] is None
        assert data["azure_region"] == "westeurope"
        assert data["azure_region_iothub"] is None
        assert data["azure_region_digital_twin"] is None

        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        assert config.azure_cloud_connection_id is None
        assert config.azure_subscription_id is None
        assert config.azure_client_id is None
        assert config.azure_client_secret is None
        assert config.azure_tenant_id is None
        assert config.azure_region == "westeurope"
        assert config.azure_region_iothub is None
        assert config.azure_region_digital_twin is None

    def test_explicit_null_clears_gcp_public_fields_and_secret(
        self,
        authenticated_client,
        sample_gcp_credentials,
        db_session,
    ):
        """GCP clear must remove public project metadata as well as secrets."""
        from src.models.twin_config import TwinConfiguration
        from src.utils.crypto import encrypt

        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.get(f"/twins/{twin_id}/config/", headers=headers)
        config = db_session.query(TwinConfiguration).filter_by(twin_id=twin_id).one()
        config.gcp_project_id = sample_gcp_credentials["project_id"]
        config.gcp_billing_account = encrypt(sample_gcp_credentials["billing_account"], "dev-user-id", twin_id)
        config.gcp_service_account_json = encrypt(sample_gcp_credentials["service_account_json"], "dev-user-id", twin_id)
        config.gcp_region = sample_gcp_credentials["region"]
        db_session.commit()

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

    def test_gcp_direct_credentials_are_rejected_before_storage(
        self,
        authenticated_client,
    ):
        """Direct GCP credentials are not stored on TwinConfiguration."""
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

        assert response.status_code == 400
        assert "Cloud Connection" in response.json()["detail"]

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

    def test_update_config_rejects_pricing_cloud_connection(self, authenticated_client):
        client, headers = authenticated_client
        connection = client.post(
            "/cloud-connections/",
            json={
                "provider": "aws",
                "purpose": "pricing",
                "display_name": "AWS Pricing",
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

        assert response.status_code == 400
        assert "cannot be bound" in response.json()["detail"]

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
