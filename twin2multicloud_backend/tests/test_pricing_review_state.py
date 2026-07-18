"""Pricing review projection tests for immutable catalog references."""

import json
from datetime import datetime, timezone

from pytest import MonkeyPatch

from src.models.optimizer_config import OptimizerConfiguration
from tests.pricing_catalog_test_data import catalog_status


class FakeCatalogContextService:
    def __init__(self, statuses):
        self.statuses = statuses
        self.calls = []

    async def status_for_user(self, user_id):
        self.calls.append(user_id)
        return self.statuses


def _patch_services(monkeypatch, *, aws, azure, gcp):
    context_service = FakeCatalogContextService(
        {"aws": aws, "azure": azure, "gcp": gcp}
    )
    monkeypatch.setattr(
        "src.api.routes.optimizer._pricing_catalog_context_service",
        lambda _db: context_service,
    )
    return context_service


def test_pricing_review_state_returns_typed_fresh_and_stale_states(
    authenticated_client,
):
    client, headers = authenticated_client

    with MonkeyPatch.context() as monkeypatch:
        context_service = _patch_services(
            monkeypatch,
            aws=catalog_status("aws"),
            azure=catalog_status("azure", is_fresh=False),
            gcp=catalog_status("gcp"),
        )
        response = client.get("/optimizer/pricing-review-state", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["aws"]["state"] == "fresh"
    assert body["providers"]["aws"]["calculation_source"] == "reviewed_baseline"
    assert body["providers"]["azure"]["state"] == "stale"
    assert body["providers"]["azure"]["can_calculate"] is False
    assert body["providers"]["azure"]["calculation_source"] == "unavailable"
    assert body["providers"]["azure"]["pricing_freshness"] == "stale"
    assert len(context_service.calls) == 1


def test_pricing_review_state_marks_incomplete_as_not_calculable(
    authenticated_client,
):
    client, headers = authenticated_client
    aws = catalog_status("aws")
    aws.update(
        {
            "status": "incomplete",
            "missing_keys": ["lambda.durationPrice"],
        }
    )

    with MonkeyPatch.context() as monkeypatch:
        _patch_services(
            monkeypatch,
            aws=aws,
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )
        response = client.get("/optimizer/pricing-review-state", headers=headers)

    state = response.json()["providers"]["aws"]
    assert state["state"] == "review_required"
    assert state["review_required"] is True
    assert state["can_calculate"] is False
    assert state["missing_keys"] == ["lambda.durationPrice"]


def test_pricing_review_state_keeps_fresh_reviewed_catalog_calculable(
    authenticated_client,
):
    client, headers = authenticated_client
    aws = catalog_status("aws")
    aws.update(
        {
            "fallback_fields": ["lambda.requestPrice"],
            "review_required": True,
        }
    )

    with MonkeyPatch.context() as monkeypatch:
        _patch_services(
            monkeypatch,
            aws=aws,
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )
        response = client.get("/optimizer/pricing-review-state", headers=headers)

    state = response.json()["providers"]["aws"]
    assert state["state"] == "review_required"
    assert state["can_calculate"] is True
    assert state["calculation_source"] == "reviewed_baseline"
    assert state["pricing_freshness"] == "fresh"
    assert state["review_reasons"][0]["status"] == "fallback_static"


def test_pricing_review_state_ignores_legacy_full_snapshot(
    auth_client,
    test_twin,
    db,
):
    db.add(
        OptimizerConfiguration(
            twin_id=test_twin.id,
            pricing_aws_snapshot=json.dumps({"legacy": "must-not-authorize"}),
            pricing_aws_updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    with MonkeyPatch.context() as monkeypatch:
        _patch_services(
            monkeypatch,
            aws={
                "age": "missing",
                "status": "missing",
                "is_fresh": False,
                "active_reference": None,
            },
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )
        response = auth_client.get("/optimizer/pricing-review-state")

    state = response.json()["providers"]["aws"]
    assert state["state"] == "missing"
    assert state["can_calculate"] is False
    assert state["calculation_source"] == "unavailable"
    assert state["last_known_good_updated_at"] is None
    assert state["actions"] == ["refresh"]


def test_pricing_review_state_marks_downstream_error_as_failed(
    authenticated_client,
):
    client, headers = authenticated_client

    with MonkeyPatch.context() as monkeypatch:
        _patch_services(
            monkeypatch,
            aws={"error": "Failed to fetch"},
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )
        response = client.get("/optimizer/pricing-review-state", headers=headers)

    state = response.json()["providers"]["aws"]
    assert state["state"] == "failed"
    assert state["can_calculate"] is False
    assert state["review_reasons"][0]["reason"] == "Failed to fetch"


def test_pricing_review_state_fails_closed_for_invalid_active_reference(
    authenticated_client,
):
    client, headers = authenticated_client
    aws = catalog_status("aws")
    aws["active_reference"] = {"provider": "aws", "snapshotId": "latest"}

    with MonkeyPatch.context() as monkeypatch:
        _patch_services(
            monkeypatch,
            aws=aws,
            azure=catalog_status("azure"),
            gcp=catalog_status("gcp"),
        )
        response = client.get("/optimizer/pricing-review-state", headers=headers)

    state = response.json()["providers"]["aws"]
    assert state["state"] == "failed"
    assert state["can_calculate"] is False
    assert "invalid active pricing reference" in state["review_reasons"][0]["reason"]
