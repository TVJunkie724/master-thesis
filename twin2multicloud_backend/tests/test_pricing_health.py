import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.optimizer_config import OptimizerConfiguration
from src.services.errors import ExternalServiceError
from tests.pricing_catalog_test_data import catalog_status


def _mock_catalog_context(mock_factory, aws: dict, azure: dict, gcp: dict):
    service = MagicMock()
    service.status_for_user = AsyncMock(
        return_value={"aws": aws, "azure": azure, "gcp": gcp}
    )
    mock_factory.return_value = service


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

    with patch(
        "src.api.routes.optimizer._pricing_catalog_context_service"
    ) as mock_context:
        _mock_catalog_context(
            mock_context,
            aws=catalog_status("aws"),
            azure=catalog_status("azure", is_fresh=False),
            gcp={
                **catalog_status("gcp"),
                "status": "incomplete",
                "missing_keys": ["gcp.iot.unit"],
            },
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


def test_pricing_health_ignores_legacy_snapshot_timestamp(auth_client, test_twin, db):
    config = OptimizerConfiguration(
        twin_id=test_twin.id,
        pricing_aws_snapshot=json.dumps({"aws": {"lambda": {"requestPrice": 0.2}}}),
        pricing_aws_updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db.add(config)
    db.commit()

    with patch(
        "src.api.routes.optimizer._pricing_catalog_context_service"
    ) as mock_context:
        _mock_catalog_context(
            mock_context,
            aws={
                "age": "missing",
                "status": "missing",
                "is_fresh": False,
                "active_reference": None,
            },
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )

        response = auth_client.get("/optimizer/pricing-health")

    assert response.status_code == 200
    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "missing"
    assert aws["severity"] == "error"
    assert aws["can_calculate"] is False
    assert aws["calculation_source"] == "unavailable"
    assert aws["pricing_freshness"] == "unavailable"
    assert aws["last_fetched_at"] is None
    assert "keep_last_known_good" not in aws["actions"]


def test_pricing_health_response_is_secret_free(authenticated_client):
    client, headers = authenticated_client
    create_response = client.post(
        "/cloud-connections/",
        json=_aws_connection_request(),
        headers=headers,
    )
    assert create_response.status_code == 200

    with patch(
        "src.api.routes.optimizer._pricing_catalog_context_service"
    ) as mock_context:
        _mock_catalog_context(
            mock_context,
            aws=catalog_status("aws"),
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )

        response = client.get("/optimizer/pricing-health", headers=headers)

    assert response.status_code == 200
    response_text = response.text
    assert "TEST_ACCESS_KEY_ID" not in response_text
    assert "TEST_SECRET_ACCESS_KEY" not in response_text
    assert "secret_access_key" not in response_text


def test_pricing_health_propagates_optimizer_connect_error(authenticated_client):
    client, headers = authenticated_client

    with patch(
        "src.api.routes.optimizer._pricing_catalog_context_service"
    ) as mock_context:
        service = MagicMock()
        service.status_for_user = AsyncMock(
            side_effect=ExternalServiceError(
                "Optimizer request failed",
                upstream_status_code=502,
                public_detail="Optimizer request failed",
            )
        )
        mock_context.return_value = service

        response = client.get("/optimizer/pricing-health", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "Optimizer request failed"
