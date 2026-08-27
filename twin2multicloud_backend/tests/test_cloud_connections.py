import json

import pytest

from src.models.cloud_connection import CloudConnection
from src.models.user import User
from src.services.cloud_connection_service import CloudConnectionService
from src.services.cloud_credential_validation_service import (
    build_preflight_result,
    perform_deployer_validation,
)
from src.services.errors import ExternalServiceError


def test_preflight_preserves_typed_deployer_repair_checks():
    result = build_preflight_result(
        "gcp",
        {
            "deployer": {
                "valid": False,
                "message": "GCP deployment preflight failed",
                "checks": [
                    {
                        "name": "enabled_apis",
                        "status": "failed",
                        "code": "MISSING_APIS",
                        "message": "One graph-required API is disabled.",
                        "action": "Review and enable the API.",
                        "apis": ["run.googleapis.com"],
                    }
                ],
            },
        },
    )

    assert result["ready"] is False
    assert result["checks"][0] == {
        "component": "deployer.enabled_apis",
        "status": "failed",
        "code": "MISSING_APIS",
        "message": "One graph-required API is disabled.",
        "action": "Review and enable the API.",
        "permissions": ["run.googleapis.com"],
    }


def _aws_request(display_name="AWS Dev"):
    return {
        "provider": "aws",
        "display_name": display_name,
        "cloud_scope": {"account_id": "123456789012", "region": "eu-central-1"},
        "aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "eu-central-1",
        },
    }


def _gcp_request():
    return {
        "provider": "gcp",
        "display_name": "GCP Dev",
        "cloud_scope": {"project_id": "demo-project"},
        "gcp": {
            "project_id": "demo-project",
            "region": "europe-west1",
            "service_account_json": json.dumps(
                {
                    "type": "service_account",
                    "client_email": "deployer@demo-project.iam.gserviceaccount.com",
                    "private_key": "-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----\\n",
                }
            ),
        },
    }


def test_create_cloud_connection_masks_secret_response(
    authenticated_client, db_session
):
    client, headers = authenticated_client
    payload = _aws_request()

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "aws"
    assert data["purpose"] == "deployment"
    assert data["scope"] == "user"
    assert data["display_name"] == "AWS Dev"
    assert data["auth_type"] == "access_key"
    assert data["validation_status"] == "untested"
    assert data["cloud_scope"] == {
        "account_id": "123456789012",
        "region": "eu-central-1",
    }
    assert data["payload_summary"] == {
        "account_identity_configured": True,
        "region": "eu-central-1",
        "uses_session_token": False,
    }

    response_text = response.text
    assert payload["aws"]["access_key_id"] not in response_text
    assert payload["aws"]["secret_access_key"] not in response_text

    stored = db_session.query(CloudConnection).filter_by(id=data["id"]).one()
    assert stored.encrypted_payload.startswith("gAAAAA")
    assert payload["aws"]["access_key_id"] not in stored.encrypted_payload
    assert payload["aws"]["secret_access_key"] not in stored.encrypted_payload


def test_list_and_filter_cloud_connections(authenticated_client):
    client, headers = authenticated_client

    client.post("/cloud-connections/", json=_aws_request(), headers=headers)
    client.post("/cloud-connections/", json=_gcp_request(), headers=headers)

    all_response = client.get("/cloud-connections/", headers=headers)
    aws_response = client.get("/cloud-connections/?provider=aws", headers=headers)

    assert all_response.status_code == 200
    assert len(all_response.json()) == 2
    assert aws_response.status_code == 200
    assert [item["provider"] for item in aws_response.json()] == ["aws"]


def test_update_cloud_connection_metadata(authenticated_client):
    client, headers = authenticated_client

    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()
    response = client.patch(
        f"/cloud-connections/{created['id']}",
        json={
            "display_name": "AWS Production",
            "cloud_scope": {"account_id": "123456789012"},
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "AWS Production"
    assert data["cloud_scope"] == {
        "account_id": "123456789012",
        "region": "eu-central-1",
    }


def test_create_aws_connection_normalizes_safe_region_metadata(
    authenticated_client,
):
    client, headers = authenticated_client
    payload = _aws_request()
    payload["cloud_scope"] = {"account_id": "123456789012"}

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["cloud_scope"] == {
        "account_id": "123456789012",
        "region": "eu-central-1",
    }


@pytest.mark.parametrize(
    "cloud_scope",
    [
        {"account_id": "not-an-account", "region": "eu-central-1"},
        {"account_id": "123456789012", "region": "us-east-1"},
    ],
)
def test_create_aws_connection_rejects_invalid_safe_scope_metadata(
    authenticated_client,
    cloud_scope,
):
    client, headers = authenticated_client
    payload = _aws_request()
    payload["cloud_scope"] = cloud_scope

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 422


def test_update_cloud_scope_invalidates_previous_credential_validation(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/",
        json=_aws_request(),
        headers=headers,
    ).json()
    connection = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    connection.validation_status = "valid"
    connection.validation_message = "Previous validation"
    db_session.commit()

    response = client.patch(
        f"/cloud-connections/{created['id']}",
        json={"cloud_scope": {"account_id": "999999999999"}},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["validation_status"] == "untested"
    assert response.json()["validation_message"] is None
    assert response.json()["cloud_scope"]["region"] == "eu-central-1"


def test_cloud_connection_payload_is_user_scoped(authenticated_client, db_session):
    client, headers = authenticated_client
    user = db_session.query(User).first()

    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()
    connection = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    service = CloudConnectionService(db_session)

    deployer_payload = service.build_deployer_credentials(connection, user.id)

    assert deployer_payload["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
    assert (
        deployer_payload["aws_secret_access_key"]
        == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    )


def test_gcp_cloud_connection_requires_explicit_deployment_project(
    authenticated_client,
):
    client, headers = authenticated_client
    payload = _gcp_request()
    payload["gcp"].pop("project_id")
    service_account = json.loads(payload["gcp"]["service_account_json"])
    service_account["project_id"] = "service-account-project"
    payload["gcp"]["service_account_json"] = json.dumps(service_account)

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 422
    assert "project_id" in response.text


@pytest.mark.asyncio
async def test_cloud_credential_validation_uses_typed_deployer_client():
    class FakeDeployerClient:
        def __init__(self):
            self.calls = []

        async def verify_permissions(self, provider, credentials):
            self.calls.append((provider, credentials))
            return {"valid": True, "message": "deployer ok", "missing_permissions": []}

    deployer_client = FakeDeployerClient()

    result = await perform_deployer_validation(
        "aws",
        {"aws_region": "eu-central-1"},
        deployer_client=deployer_client,
    )

    assert result["valid"] is True
    assert result["deployer"]["permissions"] == []
    assert deployer_client.calls == [
        ("aws", {"aws_region": "eu-central-1"}),
    ]


@pytest.mark.asyncio
async def test_cloud_credential_validation_redacts_deployer_errors():
    secret = "CLOUD-VALIDATION-SECRET"

    class FailingDeployerClient:
        async def verify_permissions(self, provider, credentials):
            raise ExternalServiceError(
                f"Deployer API returned 500: client_secret={secret}",
                upstream_status_code=500,
                public_detail=f"client_secret={secret}",
            )

    result = await perform_deployer_validation(
        "aws",
        {"aws_secret_access_key": secret},
        deployer_client=FailingDeployerClient(),
    )

    assert result["valid"] is False
    assert secret not in str(result)
    assert result["deployer"]["message"] == "Deployer API error: 500"


def test_cloud_connection_cannot_be_read_by_another_user(
    authenticated_client, db_session
):
    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()

    other_user = User(email="other-cloud-owner@example.test", name="Other Owner")
    db_session.add(other_user)
    db_session.commit()
    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    stored.user_id = other_user.id
    db_session.commit()

    response = client.get(f"/cloud-connections/{created['id']}", headers=headers)

    assert response.status_code == 404


def test_delete_cloud_connection(authenticated_client, db_session):
    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()

    response = client.delete(f"/cloud-connections/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert db_session.query(CloudConnection).filter_by(id=created["id"]).first() is None


def test_delete_bound_cloud_connection_returns_conflict(
    authenticated_client, db_session
):
    from src.models.twin_config import TwinConfiguration

    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()
    twin_id = client.post(
        "/twins/", json={"name": "Bound Twin"}, headers=headers
    ).json()["id"]
    config = TwinConfiguration(
        twin_id=twin_id,
        aws_cloud_connection_id=created["id"],
    )
    db_session.add(config)
    db_session.commit()

    response = client.delete(f"/cloud-connections/{created['id']}", headers=headers)

    assert response.status_code == 409
    assert (
        db_session.query(CloudConnection).filter_by(id=created["id"]).first()
        is not None
    )


def test_rejects_mismatched_provider_payload(authenticated_client):
    client, headers = authenticated_client
    payload = _aws_request()
    payload["provider"] = "azure"

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 422


def test_rejects_unsupported_auth_type_for_provider(authenticated_client):
    client, headers = authenticated_client
    payload = _aws_request()
    payload["auth_type"] = "service_principal"

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 422


def test_rejects_gcp_connection_without_service_account_json(authenticated_client):
    client, headers = authenticated_client
    payload = _gcp_request()
    payload["gcp"].pop("service_account_json")

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 422


def test_rejects_persisted_azure_pricing_connection(
    authenticated_client, sample_azure_credentials
):
    client, headers = authenticated_client
    response = client.post(
        "/cloud-connections/",
        json={
            "provider": "azure",
            "purpose": "pricing",
            "display_name": "Azure Pricing",
            "azure": sample_azure_credentials,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_gcp_summary_extracts_service_account_email(authenticated_client):
    client, headers = authenticated_client

    response = client.post("/cloud-connections/", json=_gcp_request(), headers=headers)

    assert response.status_code == 200
    summary = response.json()["payload_summary"]
    assert summary["service_account_configured"] is True
    assert (
        summary["service_account_email"]
        == "deployer@demo-project.iam.gserviceaccount.com"
    )
    assert "private_key" not in response.text


def test_validate_cloud_connection_updates_status(
    authenticated_client, db_session, monkeypatch
):
    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()
    seen = {}

    async def fake_validate(provider, deployer_creds):
        seen["provider"] = provider
        seen["deployer_creds"] = deployer_creds
        return {
            "provider": provider,
            "valid": True,
            "deployer": {"valid": True, "message": "deployer ok", "permissions": []},
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_deployer_validation",
        fake_validate,
    )

    response = client.post(
        f"/cloud-connections/{created['id']}/validate", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["validation_status"] == "valid"
    assert data["message"] == "Deployer validation passed"
    assert seen["provider"] == "aws"
    assert (
        seen["deployer_creds"]["aws_secret_access_key"]
        == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    )

    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    assert stored.validation_status == "valid"
    assert stored.last_validated_at is not None


def test_validate_cloud_connection_persists_invalid_status(
    authenticated_client, monkeypatch
):
    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()

    async def fake_validate(provider, deployer_creds):
        return {
            "provider": provider,
            "valid": False,
            "deployer": {
                "valid": False,
                "message": "missing permission",
                "permissions": ["lambda:CreateFunction"],
            },
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_deployer_validation",
        fake_validate,
    )

    response = client.post(
        f"/cloud-connections/{created['id']}/validate", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["validation_status"] == "invalid"
    assert data["message"] == "missing permission"


def test_validate_cloud_connection_redacts_downstream_secret_echo(
    authenticated_client, db_session, monkeypatch
):
    client, headers = authenticated_client
    secret = _aws_request()["aws"]["secret_access_key"]
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()

    async def fake_validate(provider, deployer_creds):
        return {
            "provider": provider,
            "valid": False,
            "deployer": {
                "valid": False,
                "message": (
                    f"bad credential {deployer_creds['aws_access_key_id']} "
                    f"and secret {secret}"
                ),
                "echoed_secret": secret,
            },
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_deployer_validation",
        fake_validate,
    )

    response = client.post(
        f"/cloud-connections/{created['id']}/validate", headers=headers
    )

    assert response.status_code == 200
    response_text = response.text
    assert secret not in response_text
    assert "AKIAIOSFODNN7EXAMPLE" not in response_text
    assert "[REDACTED]" in response_text

    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    assert secret not in stored.validation_message
    assert "AKIAIOSFODNN7EXAMPLE" not in stored.validation_message


def test_preflight_cloud_connection_returns_actionable_checks(
    authenticated_client, db_session, monkeypatch
):
    client, headers = authenticated_client
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()

    async def fake_validate(provider, deployer_creds):
        return {
            "provider": provider,
            "valid": False,
            "deployer": {
                "valid": False,
                "message": "missing permission",
                "permissions": ["lambda:CreateFunction"],
            },
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_deployer_validation",
        fake_validate,
    )

    response = client.post(
        f"/cloud-connections/{created['id']}/preflight", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["summary"] == "Cloud connection preflight failed"
    assert data["checks"] == [
        {
            "component": "deployer",
            "status": "failed",
            "code": "MISSING_PERMISSIONS",
            "message": "missing permission",
            "action": "Grant the listed provider permissions to the deployment identity, then run preflight again.",
            "permissions": ["lambda:CreateFunction"],
        },
    ]

    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    assert stored.validation_status == "untested"


def test_preflight_cloud_connection_redacts_secret_echo(
    authenticated_client, monkeypatch
):
    client, headers = authenticated_client
    secret = _aws_request()["aws"]["secret_access_key"]
    created = client.post(
        "/cloud-connections/", json=_aws_request(), headers=headers
    ).json()

    async def fake_validate(provider, deployer_creds):
        return {
            "provider": provider,
            "valid": False,
            "deployer": {
                "valid": False,
                "message": (
                    f"bad key {deployer_creds['aws_access_key_id']} "
                    f"and secret {secret}"
                ),
            },
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_deployer_validation",
        fake_validate,
    )

    response = client.post(
        f"/cloud-connections/{created['id']}/preflight", headers=headers
    )

    assert response.status_code == 200
    response_text = response.text
    assert secret not in response_text
    assert "AKIAIOSFODNN7EXAMPLE" not in response_text
    assert "[REDACTED]" in response_text
