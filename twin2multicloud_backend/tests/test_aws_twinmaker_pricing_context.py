"""Trust-boundary tests for user-scoped AWS TwinMaker pricing context."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import uuid

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
)
from tests.pricing_catalog_test_data import catalog_reference


NOW = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)


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
    user = User(email=f"context-{uuid.uuid4()}@example.test", name="Context Owner")
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
    reference = catalog_reference("aws")
    service = AwsTwinMakerPricingContextService(db, now=NOW)
    bound = service.bind_refresh_result(
        connection,
        {
            "activeCalculationReference": reference.to_http_dict(),
            ACCOUNT_CONTEXT_KEY: _observed_context(
                reference.content_digest,
                observed_at=observed_at,
                account_id=account_id,
            ),
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
    return user, connection, run, reference


@pytest.mark.asyncio
async def test_resolve_returns_exact_server_owned_context(db_session):
    user, connection, run, reference = _seed_context(db_session)

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(user.id, reference)

    assert resolved.available is True
    assert resolved.source_refresh_run_id == run.id
    assert resolved.payload["connectionFingerprint"] == (
        f"sha256:{connection.payload_fingerprint}"
    )
    assert resolved.payload["providerAccountId"] == "123456789012"
    assert resolved.payload["pricingRegion"] == "eu-central-1"
    assert resolved.payload["catalogSnapshotDigest"] == reference.content_digest
    assert resolved.payload["currentPlan"]["mode"] == "STANDARD"


@pytest.mark.asyncio
async def test_resolve_is_owner_scoped(db_session):
    _user, _connection, _run, reference = _seed_context(db_session)
    other = User(email="context-other@example.test", name="Other")
    db_session.add(other)
    db_session.commit()

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(other.id, reference)

    assert resolved.payload == {
        "status": "unavailable",
        "reasonCode": PLAN_UNOBSERVED,
    }


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
    user, connection, run, reference = _seed_context(db_session)
    mutate(connection, run)
    db_session.commit()

    resolved = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(user.id, reference)

    assert resolved.payload["status"] == "unavailable"
    assert resolved.payload["reasonCode"] == reason


@pytest.mark.asyncio
async def test_resolve_enforces_observation_freshness_boundaries(db_session):
    user, _connection, _run, reference = _seed_context(
        db_session,
        observed_at=NOW - timedelta(days=7, seconds=1),
    )
    stale = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(user.id, reference)
    assert stale.payload["reasonCode"] == PLAN_STALE

    boundary_user, _connection, _run, boundary_reference = _seed_context(
        db_session,
        observed_at=NOW - timedelta(days=7),
    )
    boundary = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(boundary_user.id, boundary_reference)
    assert boundary.available is True


@pytest.mark.asyncio
async def test_resolve_rejects_catalog_digest_or_region_mismatch(db_session):
    user, _connection, _run, _reference = _seed_context(db_session)

    digest_mismatch = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(user.id, catalog_reference("aws", identity_hex="d"))
    assert digest_mismatch.payload["reasonCode"] == CATALOG_DIGEST_MISMATCH

    region_mismatch = await AwsTwinMakerPricingContextService(
        db_session,
        now=NOW,
    ).resolve(
        user.id,
        catalog_reference("aws", pricing_region="us-east-1"),
    )
    assert region_mismatch.payload["reasonCode"] == CATALOG_REGION_MISMATCH


def test_bind_refresh_result_rejects_account_or_catalog_mismatch(db_session):
    _user, connection, _run, reference = _seed_context(db_session)
    service = AwsTwinMakerPricingContextService(db_session, now=NOW)

    with pytest.raises(ValueError, match=PLAN_ACCOUNT_MISMATCH):
        service.bind_refresh_result(
            connection,
            {
                "activeCalculationReference": reference.to_http_dict(),
                ACCOUNT_CONTEXT_KEY: _observed_context(
                    reference.content_digest,
                    account_id="999999999999",
                ),
            },
        )

    with pytest.raises(ValueError, match=CATALOG_DIGEST_MISMATCH):
        service.bind_refresh_result(
            connection,
            {
                "activeCalculationReference": reference.to_http_dict(),
                ACCOUNT_CONTEXT_KEY: _observed_context(
                    "sha256:" + ("d" * 64),
                ),
            },
        )
