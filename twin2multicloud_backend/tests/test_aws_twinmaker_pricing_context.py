"""Trust-boundary tests for user-scoped AWS TwinMaker pricing context."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from src.models.cloud_connection import CloudConnection
from src.models.pricing_refresh_run import PricingRefreshRun
from src.models.user import User
from src.services.aws_twinmaker_pricing_context_service import (
    ACCOUNT_CONTEXT_KEY,
    CATALOG_DIGEST_MISMATCH,
    CATALOG_REGION_MISMATCH,
    PLAN_ACCOUNT_MISMATCH,
    PLAN_CONNECTION_CHANGED,
    PLAN_RESPONSE_INVALID,
    PLAN_STALE,
    PLAN_UNOBSERVED,
    AwsTwinMakerPricingContextService,
    _canonical_snapshot_digest,
)


NOW = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)


class FakeOptimizerClient:
    def __init__(self, catalog):
        self.catalog = catalog
        self.calls = []

    async def export_pricing_snapshot(self, provider):
        self.calls.append(provider)
        return deepcopy(self.catalog)


def _catalog(region="eu-central-1"):
    pricing = {
        "__schema__": {
            "schema_version": "pricing-provider-schema.v1",
            "contract_version": "2026.07.17",
            "provider": "aws",
            "pricing_region": region,
            "generated_at": NOW.isoformat(),
        },
        "iotTwinMaker": {
            "usageRates": {
                "entityPricePerMonth": 0.0525,
                "queryPrice": 0.0000525,
                "unifiedDataAccessApiCallPrice": 0.00000165,
            }
        },
    }
    pricing["__schema__"]["snapshot_digest"] = _canonical_snapshot_digest(pricing)
    return {
        "provider": "aws",
        "updated_at": NOW.isoformat(),
        "pricing": pricing,
    }


def _observed_context(digest, *, observed_at=NOW, account_id="123456789012"):
    return {
        "schema_version": "aws-twinmaker-account-pricing-context.v1",
        "provider": "aws",
        "service": "iot_twinmaker",
        "region": "eu-central-1",
        "verified_account_id": account_id,
        "catalog_snapshot_digest": digest,
        "observed_at": observed_at.isoformat(),
        "current_plan": {
            "mode": "STANDARD",
            "billable_entity_count": 42,
            "effective_at": None,
            "updated_at": None,
            "update_reason": None,
            "bundle": None,
        },
        "pending_plan": None,
    }


def _seed_context(
    db,
    *,
    observed_at=NOW,
    account_id="123456789012",
    status="succeeded",
):
    user = User(email=f"context-{id(db)}@example.test", name="Context Owner")
    db.add(user)
    db.flush()
    connection = CloudConnection(
        user_id=user.id,
        provider="aws",
        purpose="pricing",
        scope="user",
        is_default_for_pricing=True,
        display_name="AWS Pricing",
        cloud_scope=json.dumps(
            {"account_id": "123456789012", "region": "eu-central-1"}
        ),
        auth_type="access_key",
        encrypted_payload="unused",
        payload_fingerprint="a" * 64,
        validation_status="valid",
    )
    db.add(connection)
    db.flush()
    catalog = _catalog()
    service = AwsTwinMakerPricingContextService(
        db,
        optimizer_client=FakeOptimizerClient(catalog),
        now=NOW,
    )
    bound = service.bind_refresh_result(
        connection,
        {
            ACCOUNT_CONTEXT_KEY: _observed_context(
                catalog["pricing"]["__schema__"]["snapshot_digest"],
                observed_at=observed_at,
                account_id=account_id,
            )
        },
    )
    run = PricingRefreshRun(
        user_id=user.id,
        provider="aws",
        status=status,
        pricing_connection_id=connection.id,
        force=True,
        credential_summary_json="{}",
        result_summary_json=json.dumps(bound),
        created_at=observed_at,
        started_at=observed_at,
        completed_at=observed_at,
    )
    db.add(run)
    db.commit()
    return user, connection, run, catalog


@pytest.mark.asyncio
async def test_resolve_returns_exact_server_owned_context(db_session):
    user, connection, run, catalog = _seed_context(db_session)
    client = FakeOptimizerClient(catalog)
    service = AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    )

    resolved = await service.resolve(user.id)

    assert resolved.available is True
    assert resolved.source_refresh_run_id == run.id
    assert resolved.payload == {
        "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
        "status": "available",
        "sourceRefreshRunId": run.id,
        "connectionFingerprint": f"sha256:{connection.payload_fingerprint}",
        "providerAccountId": "123456789012",
        "pricingRegion": "eu-central-1",
        "catalogSnapshotDigest": catalog["pricing"]["__schema__"][
            "snapshot_digest"
        ],
        "observedAt": "2026-07-17T12:00:00Z",
        "currentPlan": {
            "mode": "STANDARD",
            "billableEntityCount": 42,
            "effectiveAt": None,
            "updatedAt": None,
            "updateReason": None,
            "bundle": None,
        },
        "pendingPlan": None,
    }
    assert client.calls == ["aws"]


@pytest.mark.asyncio
async def test_resolve_is_owner_scoped_and_does_not_probe_catalog(db_session):
    _user, _connection, _run, catalog = _seed_context(db_session)
    other = User(email="context-other@example.test", name="Other")
    db_session.add(other)
    db_session.commit()
    client = FakeOptimizerClient(catalog)

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve(other.id)

    assert resolved.payload == {
        "status": "unavailable",
        "reasonCode": PLAN_UNOBSERVED,
    }
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda connection, _run: setattr(
                connection,
                "payload_fingerprint",
                "b" * 64,
            ),
            PLAN_CONNECTION_CHANGED,
        ),
        (
            lambda connection, _run: setattr(
                connection,
                "cloud_scope",
                json.dumps(
                    {
                        "account_id": "999999999999",
                        "region": "eu-central-1",
                    }
                ),
            ),
            PLAN_ACCOUNT_MISMATCH,
        ),
        (
            lambda connection, _run: setattr(
                connection,
                "cloud_scope",
                json.dumps(
                    {
                        "account_id": "123456789012",
                        "region": "us-east-1",
                    }
                ),
            ),
            CATALOG_REGION_MISMATCH,
        ),
        (
            lambda _connection, run: setattr(
                run,
                "result_summary_json",
                json.dumps({ACCOUNT_CONTEXT_KEY: {"invalid": True}}),
            ),
            PLAN_RESPONSE_INVALID,
        ),
    ],
)
async def test_resolve_fails_closed_when_bound_state_changes(
    db_session,
    mutate,
    reason,
):
    user, connection, run, catalog = _seed_context(db_session)
    mutate(connection, run)
    db_session.commit()
    client = FakeOptimizerClient(catalog)

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve(user.id)

    assert resolved.payload["status"] == "unavailable"
    assert resolved.payload["reasonCode"] == reason
    assert client.calls == []


@pytest.mark.asyncio
async def test_resolve_rejects_stale_observation_before_catalog_call(db_session):
    user, _connection, _run, catalog = _seed_context(
        db_session,
        observed_at=NOW - timedelta(days=7, seconds=1),
    )
    client = FakeOptimizerClient(catalog)

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve(user.id)

    assert resolved.payload["reasonCode"] == PLAN_STALE
    assert client.calls == []


@pytest.mark.asyncio
async def test_resolve_accepts_exact_seven_day_freshness_boundary(db_session):
    user, _connection, _run, catalog = _seed_context(
        db_session,
        observed_at=NOW - timedelta(days=7),
    )
    client = FakeOptimizerClient(catalog)

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve(user.id)

    assert resolved.available is True
    assert client.calls == ["aws"]


@pytest.mark.asyncio
async def test_resolve_recomputes_catalog_digest_and_rejects_tampering(db_session):
    user, _connection, _run, catalog = _seed_context(db_session)
    catalog["pricing"]["iotTwinMaker"]["usageRates"][
        "entityPricePerMonth"
    ] = 999.0
    client = FakeOptimizerClient(catalog)

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve(user.id)

    assert resolved.payload["reasonCode"] == CATALOG_DIGEST_MISMATCH
    assert client.calls == ["aws"]


@pytest.mark.asyncio
async def test_resolve_rejects_catalog_region_mismatch(db_session):
    user, _connection, _run, _catalog_payload = _seed_context(db_session)
    client = FakeOptimizerClient(_catalog("us-east-1"))

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve(user.id)

    assert resolved.payload["reasonCode"] == CATALOG_REGION_MISMATCH


def test_bind_refresh_result_rejects_account_mismatch(db_session):
    _user, connection, _run, catalog = _seed_context(db_session)
    service = AwsTwinMakerPricingContextService(
        db_session,
        optimizer_client=FakeOptimizerClient(catalog),
        now=NOW,
    )
    context = _observed_context(
        catalog["pricing"]["__schema__"]["snapshot_digest"],
        account_id="999999999999",
    )

    with pytest.raises(ValueError, match=PLAN_ACCOUNT_MISMATCH):
        service.bind_refresh_result(
            connection,
            {ACCOUNT_CONTEXT_KEY: context},
        )
