import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.models.optimizer_config import OptimizerConfiguration


def _optimizer_response(payload: dict, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def _mock_optimizer_statuses(mock_client, aws: dict, azure: dict, gcp: dict):
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(
        side_effect=[
            _optimizer_response(aws),
            _optimizer_response(azure),
            _optimizer_response(gcp),
        ]
    )


def _aws_connection_request():
    return {
        "provider": "aws",
        "display_name": "AWS Deployment",
        "permission_set_version": "thesis-demo-v1",
        "cloud_scope": {"account_id": "123456789012", "region": "eu-central-1"},
        "aws": {
            "access_key_id": "TEST_ACCESS_KEY_ID",
            "secret_access_key": "TEST_SECRET_ACCESS_KEY",
            "region": "eu-central-1",
        },
    }


def test_pricing_health_returns_dashboard_ready_provider_cards(authenticated_client):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={"age": "2 hours", "status": "valid", "is_fresh": True},
            azure={"age": "10 days", "status": "valid", "is_fresh": False},
            gcp={"status": "incomplete", "missing_keys": ["gcp.iot.unit"]},
        )

        response = client.get("/optimizer/pricing-health", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "pricing-health.v1"

    aws = body["providers"]["aws"]
    assert aws["state"] == "fresh"
    assert aws["severity"] == "warning"
    assert aws["review_required"] is True
    assert aws["can_calculate"] is True
    assert aws["source_label"] == "AWS pricing access not configured"
    assert aws["credential_summary"] == {
        "connection_id": None,
        "provider": "aws",
        "purpose": "pricing",
        "scope": "user",
        "identity_label": "AWS pricing access not configured",
        "status": "missing",
        "provider_account_id": None,
        "provider_project_id": None,
        "provider_subscription_id": None,
    }
    assert "configure_pricing_connection" in aws["actions"]
    assert "open_pricing_review" in aws["actions"]
    assert len(aws["actions"]) == len(set(aws["actions"]))

    azure = body["providers"]["azure"]
    assert azure["state"] == "stale"
    assert azure["severity"] == "warning"
    assert azure["source_label"] == "Azure Retail Prices API"
    assert azure["credential_summary"]["scope"] == "public"
    assert azure["credential_summary"]["status"] == "active"
    assert "configure_pricing_connection" not in azure["actions"]

    gcp = body["providers"]["gcp"]
    assert gcp["state"] == "review_required"
    assert gcp["severity"] == "warning"
    assert gcp["primary_message"] == "Pricing refresh requires a user-scoped pricing credential."


def test_pricing_health_uses_last_known_good_timestamp(auth_client, test_twin, db):
    config = OptimizerConfiguration(
        twin_id=test_twin.id,
        pricing_aws_snapshot=json.dumps({"aws": {"lambda": {"requestPrice": 0.2}}}),
        pricing_aws_updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db.add(config)
    db.commit()

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={"age": "missing", "status": "missing", "is_fresh": False},
            azure={"status": "valid", "is_fresh": True},
            gcp={"status": "valid", "is_fresh": True},
        )

        response = auth_client.get(f"/optimizer/pricing-health?twin_id={test_twin.id}")

    assert response.status_code == 200
    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "missing"
    assert aws["severity"] == "error"
    assert aws["can_calculate"] is True
    assert aws["calculation_source"] == "last_known_good"
    assert aws["pricing_freshness"] == "last_known_good"
    assert aws["last_fetched_at"] == "2026-06-01T00:00:00+00:00"
    assert "keep_last_known_good" in aws["actions"]


def test_pricing_health_response_is_secret_free(authenticated_client):
    client, headers = authenticated_client
    create_response = client.post(
        "/cloud-connections/",
        json=_aws_connection_request(),
        headers=headers,
    )
    assert create_response.status_code == 200

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={"age": "1 day", "status": "valid", "is_fresh": True},
            azure={"status": "valid", "is_fresh": True},
            gcp={"status": "valid", "is_fresh": True},
        )

        response = client.get("/optimizer/pricing-health", headers=headers)

    assert response.status_code == 200
    response_text = response.text
    assert "TEST_ACCESS_KEY_ID" not in response_text
    assert "TEST_SECRET_ACCESS_KEY" not in response_text
    assert "secret_access_key" not in response_text


def test_pricing_health_propagates_optimizer_connect_error(authenticated_client):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.RequestError("optimizer down")
        )

        response = client.get("/optimizer/pricing-health", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "Request failed: RequestError"
