from src.models.cloud_connection import CloudConnection


def test_aws_bootstrap_plan_is_dry_run_only(authenticated_client):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-bootstrap/aws/plan",
        headers=headers,
        json={
            "display_name": "thesis-demo",
            "account_id": "123456789012",
            "region": "eu-central-1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "aws"
    assert data["mode"] == "manual_static_script"
    assert data["dry_run_command"][0] == "bootstrap/aws/bootstrap_deployment_identity.sh"
    assert "--apply" not in data["dry_run_command"]
    assert "--apply" in data["apply_command"]
    assert data["rotation_flag"] == "--rotate-access-keys"
    assert data["output_auth_type"] == "access_key"
    assert data["cloud_scope"] == {
        "account_id": "123456789012",
        "region": "eu-central-1",
        "identity_name": "thesis-demo",
    }


def test_bootstrap_plan_rejects_admin_material(authenticated_client):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-bootstrap/aws/plan",
        headers=headers,
        json={
            "display_name": "thesis-demo",
            "account_id": "123456789012",
            "admin_secret_access_key": "must-not-enter-api",
        },
    )

    assert response.status_code == 422


def test_gcp_bootstrap_plan_uses_provider_defaults(authenticated_client):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-bootstrap/gcp/plan",
        headers=headers,
        json={
            "display_name": "thesis-demo",
            "project_id": "thesis-project",
            "billing_account": "000000-000000-000000",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["required_tool"] == "gcloud"
    assert data["output_auth_type"] == "service_account_key"
    assert data["rotation_flag"] == "--rotate-service-account-keys"
    assert data["cloud_scope"]["region"] == "europe-west1"
    assert data["dry_run_command"] == [
        "bootstrap/gcp/bootstrap_deployment_identity.sh",
        "--project-id",
        "thesis-project",
        "--billing-account",
        "000000-000000-000000",
        "--name",
        "thesis-demo",
        "--region",
        "europe-west1",
    ]


def test_bootstrap_plan_requires_provider_scope(authenticated_client):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-bootstrap/azure/plan",
        headers=headers,
        json={
            "display_name": "thesis-demo",
            "subscription_id": "sub-123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tenant_id is required"


def test_import_bootstrap_connection_persists_masked_cloud_connection(authenticated_client, db_session):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-bootstrap/import",
        headers=headers,
        json={
            "source": "bootstrap_script",
            "connection": {
                "provider": "aws",
                "display_name": "bootstrap-generated",
                "auth_type": "access_key",
                "cloud_scope": {
                    "account_id": "123456789012",
                    "region": "eu-central-1",
                },
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                },
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["connection"]
    assert data["provider"] == "aws"
    assert data["payload_summary"] == {
        "account_identity_configured": True,
        "region": "eu-central-1",
        "uses_session_token": False,
    }
    assert "secret_access_key" not in str(data)

    stored = db_session.query(CloudConnection).filter_by(id=data["id"]).one()
    assert stored.encrypted_payload.startswith("gAAAAA")
    assert "wJalrXUtnFEMI" not in stored.encrypted_payload


def test_import_bootstrap_connection_rejects_unexpected_secret_fields(authenticated_client):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-bootstrap/import",
        headers=headers,
        json={
            "source": "bootstrap_script",
            "connection": {
                "provider": "aws",
                "display_name": "bootstrap-generated",
                "auth_type": "access_key",
                "cloud_scope": {"account_id": "123456789012"},
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "region": "eu-central-1",
                    "admin_secret_access_key": "must-not-be-ignored",
                },
            },
        },
    )

    assert response.status_code == 422
