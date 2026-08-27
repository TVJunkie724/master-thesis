"""Pinned, immutable pricing-catalog resolution tests."""

from __future__ import annotations

import pytest

from src.services.errors import (
    ExternalServiceError,
    OptimizerContractError,
    PricingCatalogUnavailable,
)
from src.services.pricing_catalog_context_service import PricingCatalogContextService
from tests.pricing_catalog_test_data import catalog_context, catalog_reference


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
        self.calls: list[tuple] = []

    async def get_pricing_catalog_baseline(self, provider):
        self.calls.append(("baseline", provider))
        return self.baselines[provider].to_http_dict()

    async def get_exact_pricing_catalog_reference(
        self,
        provider,
        pricing_region,
        snapshot_id,
    ):
        self.calls.append(("exact", provider, pricing_region, snapshot_id))
        if snapshot_id in self.missing:
            raise ExternalServiceError(
                "not found",
                upstream_status_code=404,
                public_detail="Pricing catalog not found",
            )
        reference = self.references[snapshot_id]
        return {
            "reference": reference.to_http_dict(),
            # Frozen thesis snapshots remain valid regardless of wall-clock age.
            "isFresh": False,
        }


@pytest.mark.asyncio
async def test_resolve_uses_exact_three_provider_repository_baselines():
    client = FakeOptimizerClient()

    resolved = await PricingCatalogContextService(client).resolve()

    assert resolved == catalog_context()
    assert client.calls == [
        ("baseline", "aws"),
        (
            "exact",
            "aws",
            catalog_reference("aws").pricing_region,
            catalog_reference("aws").snapshot_id,
        ),
        ("baseline", "azure"),
        (
            "exact",
            "azure",
            catalog_reference("azure").pricing_region,
            catalog_reference("azure").snapshot_id,
        ),
        ("baseline", "gcp"),
        (
            "exact",
            "gcp",
            catalog_reference("gcp").pricing_region,
            catalog_reference("gcp").snapshot_id,
        ),
    ]


@pytest.mark.asyncio
async def test_resolve_fails_when_pinned_snapshot_is_missing():
    client = FakeOptimizerClient()
    client.missing.add(catalog_reference("azure").snapshot_id)

    with pytest.raises(PricingCatalogUnavailable) as exc_info:
        await PricingCatalogContextService(client).resolve()

    assert exc_info.value.error_code == "PRICING_CATALOG_NOT_FOUND"


@pytest.mark.asyncio
async def test_verify_context_rejects_missing_or_mismatched_identity():
    context = catalog_context()
    client = FakeOptimizerClient()
    service = PricingCatalogContextService(client)

    missing_id = context.catalogs["aws"].snapshot_id
    client.missing.add(missing_id)
    with pytest.raises(PricingCatalogUnavailable) as missing:
        await service.verify_context(context)
    assert missing.value.error_code == "PRICING_CATALOG_NOT_FOUND"

    client.missing.clear()
    client.references[context.catalogs["gcp"].snapshot_id] = catalog_reference(
        "gcp",
        identity_hex="d",
    )
    with pytest.raises(OptimizerContractError, match="does not match"):
        await service.verify_context(context)
