import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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


def test_pricing_review_state_returns_typed_fresh_and_stale_states(authenticated_client):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={
                "age": "2 hours",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": True,
                "threshold_days": 7,
            },
            azure={
                "age": "10 days",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": False,
                "threshold_days": 7,
            },
            gcp={
                "age": "1 day",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": True,
                "threshold_days": 7,
            },
        )

        response = client.get("/optimizer/pricing-review-state", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "pricing-review-state.v1"
    assert body["providers"]["aws"]["state"] == "fresh"
    assert body["providers"]["aws"]["calculation_source"] == "fresh"
    assert body["providers"]["azure"]["state"] == "stale"
    assert body["providers"]["azure"]["calculation_source"] == "stale"
    assert body["providers"]["azure"]["review_required"] is False


def test_pricing_review_state_marks_incomplete_as_review_required(authenticated_client):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={
                "age": "2 hours",
                "status": "incomplete",
                "missing_keys": ["lambda.durationPrice"],
                "is_fresh": True,
                "threshold_days": 7,
            },
            azure={"status": "valid", "is_fresh": True},
            gcp={"status": "valid", "is_fresh": True},
        )

        response = client.get("/optimizer/pricing-review-state", headers=headers)

    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "review_required"
    assert aws["review_required"] is True
    assert aws["can_calculate"] is False
    assert aws["missing_keys"] == ["lambda.durationPrice"]
    assert aws["review_reasons"][0]["missing_keys"] == ["lambda.durationPrice"]


def test_pricing_review_state_marks_valid_fallback_payload_as_review_required(
    authenticated_client,
):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={
                "age": "2 hours",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": True,
                "threshold_days": 7,
                "quality_status": "review_required",
                "review_required": True,
                "fallback_fields": ["lambda.requestPrice"],
                "unsupported_fields": [],
            },
            azure={"status": "valid", "is_fresh": True},
            gcp={"status": "valid", "is_fresh": True},
        )

        response = client.get("/optimizer/pricing-review-state", headers=headers)

    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "review_required"
    assert aws["review_required"] is True
    assert aws["can_calculate"] is True
    assert aws["calculation_source"] == "fallback_static"
    assert aws["pricing_freshness"] == "unavailable"
    assert aws["review_reasons"][0]["status"] == "fallback_static"
    assert aws["review_reasons"][0]["missing_keys"] == ["lambda.requestPrice"]


def test_pricing_review_state_uses_last_known_good_for_missing_provider(
    auth_client,
    test_twin,
    db,
):
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
            aws={
                "age": "missing",
                "status": "missing",
                "missing_keys": [],
                "is_fresh": False,
                "threshold_days": 7,
            },
            azure={"status": "valid", "is_fresh": True},
            gcp={"status": "valid", "is_fresh": True},
        )

        response = auth_client.get(
            f"/optimizer/pricing-review-state?twin_id={test_twin.id}"
        )

    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "missing"
    assert aws["can_calculate"] is True
    assert aws["calculation_source"] == "last_known_good"
    assert aws["pricing_freshness"] == "last_known_good"
    assert aws["actions"] == ["refresh", "keep_last_known_good"]
    assert aws["last_known_good_updated_at"] == "2026-06-01T00:00:00+00:00"


def test_pricing_review_state_marks_downstream_error_as_failed(authenticated_client):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=[
                _optimizer_response({}, status_code=500),
                _optimizer_response({"status": "valid", "is_fresh": True}),
                _optimizer_response({"status": "valid", "is_fresh": True}),
            ]
        )

        response = client.get("/optimizer/pricing-review-state", headers=headers)

    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "failed"
    assert aws["review_required"] is True
    assert aws["can_calculate"] is False
    assert aws["review_reasons"][0]["reason"] == "Failed to fetch"


def test_pricing_review_state_passes_publication_decision_through(authenticated_client):
    client, headers = authenticated_client

    with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
        _mock_optimizer_statuses(
            mock_client,
            aws={
                "schema_version": "pricing-publication-decision.v1",
                "status": "review_required",
                "review_required": True,
                "can_calculate": True,
                "calculation_source": "last_known_good",
                "pricing_freshness": "stale",
                "review_reasons": [
                    {
                        "status": "ambiguous",
                        "intent_id": "api.request_million",
                        "reason": "Multiple provider pricing candidates match this intent.",
                    }
                ],
            },
            azure={"status": "valid", "is_fresh": True},
            gcp={"status": "valid", "is_fresh": True},
        )

        response = client.get("/optimizer/pricing-review-state", headers=headers)

    aws = response.json()["providers"]["aws"]
    assert aws["state"] == "review_required"
    assert aws["calculation_source"] == "last_known_good"
    assert aws["pricing_freshness"] == "stale"
    assert aws["review_reasons"][0]["status"] == "ambiguous"
    assert aws["review_reasons"][0]["intent_id"] == "api.request_million"
