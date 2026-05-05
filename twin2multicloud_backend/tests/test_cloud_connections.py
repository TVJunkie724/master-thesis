import json

from src.models.cloud_connection import CloudConnection
from src.models.user import User
from src.services.cloud_connection_service import CloudConnectionService


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
            "billing_account": "012345-6789AB-CDEF01",
            "region": "europe-west1",
            "service_account_json": json.dumps({
                "type": "service_account",
                "client_email": "deployer@demo-project.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----\\n",
            }),
        },
    }


def test_create_cloud_connection_masks_secret_response(authenticated_client, db_session):
    client, headers = authenticated_client
    payload = _aws_request()

    response = client.post("/cloud-connections/", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "aws"
    assert data["display_name"] == "AWS Dev"
    assert data["auth_type"] == "access_key"
    assert data["validation_status"] == "untested"
    assert data["cloud_scope"] == {"account_id": "123456789012", "region": "eu-central-1"}
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

    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    response = client.patch(
        f"/cloud-connections/{created['id']}",
        json={"display_name": "AWS Production", "cloud_scope": {"account_id": "123456789012"}},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "AWS Production"
    assert data["cloud_scope"] == {"account_id": "123456789012"}


def test_cloud_connection_payload_is_user_scoped(authenticated_client, db_session):
    client, headers = authenticated_client
    user = db_session.query(User).first()

    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    connection = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    service = CloudConnectionService(db_session)

    deployer_payload = service.build_deployer_credentials(connection, user.id)

    assert deployer_payload["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
    assert deployer_payload["aws_secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def test_gcp_optimizer_credentials_extract_project_from_service_account(authenticated_client, db_session):
    client, headers = authenticated_client
    user = db_session.query(User).first()
    payload = _gcp_request()
    payload["gcp"].pop("project_id")
    service_account = json.loads(payload["gcp"]["service_account_json"])
    service_account["project_id"] = "service-account-project"
    payload["gcp"]["service_account_json"] = json.dumps(service_account)

    created = client.post("/cloud-connections/", json=payload, headers=headers).json()
    connection = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    service = CloudConnectionService(db_session)

    optimizer_payload = service.build_optimizer_credentials(connection, user.id)

    assert optimizer_payload["gcp_project_id"] == "service-account-project"
    assert "placeholder-project" not in str(optimizer_payload)


def test_cloud_connection_cannot_be_read_by_another_user(authenticated_client, db_session):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    stored.user_id = "other-user"
    db_session.commit()

    response = client.get(f"/cloud-connections/{created['id']}", headers=headers)

    assert response.status_code == 404


def test_delete_cloud_connection(authenticated_client, db_session):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    response = client.delete(f"/cloud-connections/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert db_session.query(CloudConnection).filter_by(id=created["id"]).first() is None


def test_delete_bound_cloud_connection_returns_conflict(authenticated_client, db_session):
    from src.models.twin_config import TwinConfiguration

    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    config = TwinConfiguration(
        twin_id="bound-twin",
        aws_cloud_connection_id=created["id"],
    )
    db_session.add(config)
    db_session.commit()

    response = client.delete(f"/cloud-connections/{created['id']}", headers=headers)

    assert response.status_code == 409
    assert db_session.query(CloudConnection).filter_by(id=created["id"]).first() is not None


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


def test_gcp_summary_extracts_service_account_email(authenticated_client):
    client, headers = authenticated_client

    response = client.post("/cloud-connections/", json=_gcp_request(), headers=headers)

    assert response.status_code == 200
    summary = response.json()["payload_summary"]
    assert summary["service_account_configured"] is True
    assert summary["service_account_email"] == "deployer@demo-project.iam.gserviceaccount.com"
    assert "private_key" not in response.text


def test_validate_cloud_connection_updates_status(authenticated_client, db_session, monkeypatch):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    seen = {}

    async def fake_validate(provider, optimizer_creds, deployer_creds):
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
        "src.api.routes.cloud_connections.perform_dual_validation",
        fake_validate,
    )

    response = client.post(f"/cloud-connections/{created['id']}/validate", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["validation_status"] == "valid"
    assert data["message"] == "Optimizer and Deployer validation passed"
    assert seen["provider"] == "aws"
    assert seen["optimizer_creds"]["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
    assert seen["deployer_creds"]["aws_secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    assert stored.validation_status == "valid"
    assert stored.last_validated_at is not None


def test_validate_cloud_connection_persists_invalid_status(authenticated_client, monkeypatch):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    async def fake_validate(provider, optimizer_creds, deployer_creds):
        return {
            "provider": provider,
            "valid": False,
            "optimizer": {"valid": True, "message": "optimizer ok"},
            "deployer": {"valid": False, "message": "missing permission", "permissions": ["lambda:CreateFunction"]},
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_dual_validation",
        fake_validate,
    )

    response = client.post(f"/cloud-connections/{created['id']}/validate", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["validation_status"] == "invalid"
    assert data["message"] == "optimizer ok | missing permission"


def test_validate_cloud_connection_redacts_downstream_secret_echo(authenticated_client, db_session, monkeypatch):
    client, headers = authenticated_client
    secret = _aws_request()["aws"]["secret_access_key"]
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    async def fake_validate(provider, optimizer_creds, deployer_creds):
        return {
            "provider": provider,
            "valid": False,
            "optimizer": {"valid": False, "message": f"bad credential {optimizer_creds['aws_access_key_id']}"},
            "deployer": {"valid": False, "message": f"bad secret {secret}", "echoed_secret": secret},
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_dual_validation",
        fake_validate,
    )

    response = client.post(f"/cloud-connections/{created['id']}/validate", headers=headers)

    assert response.status_code == 200
    response_text = response.text
    assert secret not in response_text
    assert "AKIAIOSFODNN7EXAMPLE" not in response_text
    assert "[REDACTED]" in response_text

    stored = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    assert secret not in stored.validation_message
    assert "AKIAIOSFODNN7EXAMPLE" not in stored.validation_message
