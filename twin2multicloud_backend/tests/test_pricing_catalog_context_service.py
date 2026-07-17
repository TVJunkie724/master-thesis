"""Owner-scope and fail-closed tests for immutable catalog resolution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from src.models.pricing_refresh_run import PricingRefreshRun
from src.models.user import User
from src.services.errors import (
    ExternalServiceError,
    OptimizerContractError,
    PricingCatalogUnavailable,
)
from src.services.pricing_catalog_context_service import (
    PricingCatalogContextService,
)
from tests.pricing_catalog_test_data import (
    catalog_context,
    catalog_reference,
)


NOW = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)


class FakeOptimizerClient:
    def __init__(self):
        self.baselines = {
            provider: catalog_reference(provider)
            for provider in ("aws", "azure", "gcp")
        }
        self.references = {
            reference.snapshot_id: reference
            for reference in self.baselines.values()
        }
        self.missing: set[str] = set()
        self.stale: set[str] = set()
        self.calls = []

    async def get_pricing_catalog_baseline(self, provider):
        self.calls.append(("baseline", provider))
        return self.baselines[provider].to_http_dict()

    async def get_exact_pricing_catalog_reference(
        self,
        provider,
        pricing_region,
        snapshot_id,
    ):
        self.calls.append(
            ("exact", provider, pricing_region, snapshot_id)
        )
        if snapshot_id in self.missing:
            raise ExternalServiceError(
                "not found",
                upstream_status_code=404,
                public_detail="Pricing catalog not found",
            )
        reference = self.references[snapshot_id]
        return {
            "reference": reference.to_http_dict(),
            "isFresh": snapshot_id not in self.stale,
        }


def _user(db, label):
    user = User(
        email=f"catalog-{label}@example.test",
        name=f"Catalog {label}",
    )
    db.add(user)
    db.flush()
    return user


def _refresh_run(db, user, reference, *, completed_at):
    run = PricingRefreshRun(
        user_id=user.id,
        provider=reference.provider,
        status="succeeded",
        force=True,
        credential_summary_json="{}",
        result_summary_json=json.dumps(
            {"activeCalculationReference": reference.to_http_dict()}
        ),
        created_at=completed_at,
        started_at=completed_at,
        completed_at=completed_at,
    )
    db.add(run)
    db.flush()
    return run


@pytest.mark.asyncio
async def test_resolve_prefers_latest_usable_owner_reference_and_isolates_users(
    db_session,
):
    owner = _user(db_session, "owner")
    other = _user(db_session, "other")
    owner_reference = catalog_reference("aws", identity_hex="d")
    other_reference = catalog_reference("aws", identity_hex="e")
    _refresh_run(db_session, owner, owner_reference, completed_at=NOW)
    _refresh_run(db_session, other, other_reference, completed_at=NOW)
    db_session.commit()

    client = FakeOptimizerClient()
    client.references[owner_reference.snapshot_id] = owner_reference
    client.references[other_reference.snapshot_id] = other_reference
    resolved = await PricingCatalogContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve_for_user(owner.id)

    assert resolved.catalogs["aws"] == owner_reference
    assert resolved.catalogs["azure"] == catalog_reference("azure")
    assert resolved.catalogs["gcp"] == catalog_reference("gcp")
    assert (
        "exact",
        "aws",
        other_reference.pricing_region,
        other_reference.snapshot_id,
    ) not in client.calls


@pytest.mark.asyncio
async def test_resolve_skips_missing_newer_owner_reference():
    # This test uses a tiny fake DB query boundary to focus ordering behavior.
    class Query:
        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def all(self):
            return runs

    class DB:
        def query(self, _model):
            return Query()

    newer = catalog_reference("aws", identity_hex="d")
    older = catalog_reference("aws", identity_hex="e")
    runs = [
        type(
            "Run",
            (),
            {
                "result_summary_json": json.dumps(
                    {"activeCalculationReference": newer.to_http_dict()}
                )
            },
        )(),
        type(
            "Run",
            (),
            {
                "result_summary_json": json.dumps(
                    {"activeCalculationReference": older.to_http_dict()}
                )
            },
        )(),
    ]
    client = FakeOptimizerClient()
    client.references[newer.snapshot_id] = newer
    client.references[older.snapshot_id] = older
    client.missing.add(newer.snapshot_id)
    service = PricingCatalogContextService(
        DB(),
        optimizer_client=client,
        now=NOW,
    )

    resolved = await service._resolve_provider_reference("owner", "aws")

    assert resolved == older


@pytest.mark.asyncio
async def test_resolve_uses_baselines_when_owner_has_no_refresh(db_session):
    owner = _user(db_session, "baseline")
    db_session.commit()
    client = FakeOptimizerClient()

    resolved = await PricingCatalogContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    ).resolve_for_user(owner.id)

    assert resolved == catalog_context()


@pytest.mark.asyncio
async def test_stale_baseline_blocks_calculation_but_remains_visible_in_status(
    db_session,
):
    owner = _user(db_session, "stale")
    db_session.commit()
    client = FakeOptimizerClient()
    client.stale.add(catalog_reference("azure").snapshot_id)
    service = PricingCatalogContextService(
        db_session,
        optimizer_client=client,
        now=NOW + timedelta(days=8),
    )

    with pytest.raises(PricingCatalogUnavailable) as exc_info:
        await service.resolve_for_user(owner.id)

    assert exc_info.value.error_code == "PRICING_CATALOG_STALE"
    statuses = await service.status_for_user(owner.id)
    assert statuses["azure"]["status"] == "valid"
    assert statuses["azure"]["is_fresh"] is False
    assert statuses["azure"]["active_reference"] == (
        catalog_reference("azure").to_http_dict()
    )


@pytest.mark.asyncio
async def test_verify_context_distinguishes_missing_stale_and_mismatch(
    db_session,
):
    context = catalog_context()
    client = FakeOptimizerClient()
    service = PricingCatalogContextService(
        db_session,
        optimizer_client=client,
        now=NOW,
    )

    missing_id = context.catalogs["aws"].snapshot_id
    client.missing.add(missing_id)
    with pytest.raises(PricingCatalogUnavailable) as missing:
        await service.verify_context(context)
    assert missing.value.error_code == "PRICING_CATALOG_NOT_FOUND"

    client.missing.clear()
    stale_id = context.catalogs["azure"].snapshot_id
    client.stale.add(stale_id)
    with pytest.raises(PricingCatalogUnavailable) as stale:
        await service.verify_context(context)
    assert stale.value.error_code == "PRICING_CATALOG_STALE"

    client.stale.clear()
    client.references[context.catalogs["gcp"].snapshot_id] = catalog_reference(
        "gcp",
        identity_hex="d",
    )
    with pytest.raises(OptimizerContractError, match="does not match"):
        await service.verify_context(context)
