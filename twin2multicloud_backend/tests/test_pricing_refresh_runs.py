import json

from src.api.routes.pricing_refresh import get_optimizer_client
from src.main import app
from src.models.pricing_refresh_run import PricingRefreshRun
from src.models.cloud_connection import CloudConnection
from src.services.errors import ExternalServiceUnavailable


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload if payload is not None else {"status": "ok", "message": "done"}
        self.exc = exc
        self.calls = []

    async def refresh_pricing(self, provider, *, credentials=None, force_fetch=True):
        self.calls.append(
            {
                "provider": provider,
                "credentials": credentials or {},
                "force_fetch": force_fetch,
            }
        )
        if self.exc:
            raise self.exc
        return self.payload


def _override_optimizer():
    fake = FakeOptimizerClient()
    app.dependency_overrides[get_optimizer_client] = lambda: fake
    return fake


def _aws_request(display_name="AWS Pricing"):
    return {
        "provider": "aws",
        "purpose": "pricing",
        "display_name": display_name,
        "cloud_scope": {"account_id": "123456789012", "region": "eu-central-1"},
        "aws": {
            "access_key_id": "TEST_ACCESS_KEY_ID",
            "secret_access_key": "TEST_SECRET_ACCESS_KEY",
            "region": "eu-central-1",
        },
    }


def _gcp_request(display_name="GCP Pricing"):
    return {
        "provider": "gcp",
        "purpose": "pricing",
        "display_name": display_name,
        "cloud_scope": {"project_id": "demo-project", "region": "europe-west1"},
        "gcp": {
            "project_id": "demo-project",
            "billing_account": "012345-6789AB-CDEF01",
            "region": "europe-west1",
            "service_account_json": json.dumps(
                {
                    "type": "service_account",
                    "project_id": "demo-project",
                    "client_email": "pricing@demo-project.iam.gserviceaccount.com",
                    "private_key": "TEST_PRIVATE_KEY",
                }
            ),
        },
    }


def test_start_azure_pricing_refresh_creates_public_run(authenticated_client, db_session):
    client, headers = authenticated_client
    fake = _override_optimizer()

    response = client.post(
        "/optimizer/pricing-refresh/azure",
        json={"force": False},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "pricing-refresh-run.v1"
    assert body["provider"] == "azure"
    assert body["status"] == "succeeded"
    assert body["force"] is False
    assert body["credential_summary"] == {
        "connection_id": None,
        "identity_label": "Azure Retail Prices API",
        "scope": "public",
        "provider_account_id": None,
        "provider_project_id": None,
        "provider_subscription_id": None,
    }
    assert body["sse_url"] == f"/optimizer/pricing-refresh/runs/{body['refresh_run_id']}/stream"
    assert fake.calls == [{"provider": "azure", "credentials": {}, "force_fetch": False}]

    stored = db_session.query(PricingRefreshRun).filter_by(id=body["refresh_run_id"]).one()
    assert stored.status == "succeeded"

    detail = client.get(
        f"/optimizer/pricing-refresh/runs/{body['refresh_run_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["refresh_run_id"] == body["refresh_run_id"]


def test_start_aws_pricing_refresh_requires_explicit_connection(authenticated_client):
    client, headers = authenticated_client
    _override_optimizer()

    response = client.post(
        "/optimizer/pricing-refresh/aws",
        json={"force": True},
        headers=headers,
    )

    assert response.status_code == 400
    assert "requires an explicitly confirmed CloudConnection" in response.json()["detail"]


def test_start_aws_pricing_refresh_uses_user_owned_connection_without_secret_output(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    fake = _override_optimizer()
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    connection = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    connection.validation_status = "valid"
    db_session.commit()

    response = client.post(
        "/optimizer/pricing-refresh/aws",
        json={"pricing_connection_id": created["id"], "force": True},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "aws"
    assert body["status"] == "succeeded"
    assert body["credential_summary"]["connection_id"] == created["id"]
    assert body["credential_summary"]["identity_label"] == "AWS Pricing"
    assert body["credential_summary"]["provider_account_id"] == "123456789012"
    assert fake.calls[0]["credentials"]["aws_access_key_id"] == "TEST_ACCESS_KEY_ID"
    assert fake.calls[0]["credentials"]["aws_secret_access_key"] == "TEST_SECRET_ACCESS_KEY"

    response_text = response.text
    assert "TEST_ACCESS_KEY_ID" not in response_text
    assert "TEST_SECRET_ACCESS_KEY" not in response_text
    assert "secret_access_key" not in response_text


def test_start_gcp_pricing_refresh_maps_service_account_payload(authenticated_client, db_session):
    client, headers = authenticated_client
    fake = _override_optimizer()
    created = client.post("/cloud-connections/", json=_gcp_request(), headers=headers).json()
    connection = db_session.query(CloudConnection).filter_by(id=created["id"]).one()
    connection.validation_status = "valid"
    db_session.commit()

    response = client.post(
        "/optimizer/pricing-refresh/gcp",
        json={"pricing_connection_id": created["id"], "force": True},
        headers=headers,
    )

    assert response.status_code == 200
    call = fake.calls[0]
    assert call["provider"] == "gcp"
    assert call["credentials"]["gcp_service_account_json"]
    assert call["credentials"]["gcp_project_id"] == "demo-project"
    assert call["credentials"]["gcp_billing_account"] == "012345-6789AB-CDEF01"
    assert "gcp_credentials_file" not in call["credentials"]
    assert "TEST_PRIVATE_KEY" not in response.text
    db_session.refresh(connection)
    assert connection.last_used_at is not None


def test_start_pricing_refresh_rejects_deployment_connection(authenticated_client):
    client, headers = authenticated_client
    _override_optimizer()
    payload = _aws_request()
    payload["purpose"] = "deployment"
    payload["permission_set_version"] = "thesis-demo-v1"
    created = client.post("/cloud-connections/", json=payload, headers=headers).json()

    response = client.post(
        "/optimizer/pricing-refresh/aws",
        json={"pricing_connection_id": created["id"], "force": True},
        headers=headers,
    )

    assert response.status_code == 400
    assert "not configured for pricing" in response.json()["detail"]


def test_start_pricing_refresh_rejects_unvalidated_pricing_connection(authenticated_client):
    client, headers = authenticated_client
    _override_optimizer()
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    response = client.post(
        "/optimizer/pricing-refresh/aws",
        json={"pricing_connection_id": created["id"], "force": True},
        headers=headers,
    )

    assert response.status_code == 400
    assert "must be validated" in response.json()["detail"]


def test_start_pricing_refresh_rejects_provider_mismatch(authenticated_client):
    client, headers = authenticated_client
    _override_optimizer()
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    response = client.post(
        "/optimizer/pricing-refresh/gcp",
        json={"pricing_connection_id": created["id"], "force": True},
        headers=headers,
    )

    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_failed_optimizer_refresh_is_persisted(authenticated_client, db_session):
    client, headers = authenticated_client
    app.dependency_overrides[get_optimizer_client] = lambda: FakeOptimizerClient(
        exc=ExternalServiceUnavailable("Optimizer API unavailable")
    )

    response = client.post(
        "/optimizer/pricing-refresh/azure",
        json={"force": True},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "OPTIMIZER_UNAVAILABLE"
    assert "unavailable" in body["error_message"].lower()

    stored = db_session.query(PricingRefreshRun).filter_by(id=body["refresh_run_id"]).one()
    assert stored.status == "failed"
    assert stored.error_code == "OPTIMIZER_UNAVAILABLE"


def test_pricing_refresh_run_is_user_scoped(authenticated_client, db_session):
    client, headers = authenticated_client
    _override_optimizer()
    response = client.post(
        "/optimizer/pricing-refresh/azure",
        json={"force": True},
        headers=headers,
    )
    run_id = response.json()["refresh_run_id"]

    db_session.query(PricingRefreshRun).filter_by(id=run_id).one().user_id = "other-user"
    db_session.commit()

    response = client.get(f"/optimizer/pricing-refresh/runs/{run_id}", headers=headers)

    assert response.status_code == 404


def test_pricing_refresh_stream_returns_final_run_state(authenticated_client):
    client, headers = authenticated_client
    _override_optimizer()
    created = client.post(
        "/optimizer/pricing-refresh/azure",
        json={"force": True},
        headers=headers,
    ).json()

    response = client.get(
        f"/optimizer/pricing-refresh/runs/{created['refresh_run_id']}/stream",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    text = response.content.decode()
    assert "event: refresh_status" in text
    assert "event: complete" in text
    assert created["refresh_run_id"] in text
