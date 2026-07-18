"""Tests for exact, bounded pricing-catalog diagnostics."""

from __future__ import annotations

import pytest

from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.optimizer_pricing_catalog_service import (
    OptimizerPricingCatalogService,
)
from src.services.service_errors import DownstreamServiceError, ValidationError
from tests.pricing_catalog_test_data import catalog_reference


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.calls = []

    async def get_exact_pricing_catalog_snapshot(
        self,
        provider,
        pricing_region,
        snapshot_id,
    ):
        self.calls.append((provider, pricing_region, snapshot_id))
        if self.exc:
            raise self.exc
        return self.payload


@pytest.mark.asyncio
async def test_exact_snapshot_returns_matching_catalog_payload():
    reference = catalog_reference("azure")
    fake = FakeOptimizerClient(
        {"reference": reference.to_http_dict(), "pricing": {"blobStorage": {}}}
    )

    result = await OptimizerPricingCatalogService(fake).get_exact_snapshot(
        "AZURE",
        reference.pricing_region,
        reference.snapshot_id,
    )

    assert result["reference"] == reference.to_http_dict()
    assert fake.calls == [
        ("azure", reference.pricing_region, reference.snapshot_id)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "region", "snapshot_id"),
    [
        ("digitalocean", "fra1", "pcs_" + ("a" * 64)),
        ("aws", "../secrets", "pcs_" + ("a" * 64)),
        ("gcp", "europe-west1", "latest"),
    ],
)
async def test_exact_snapshot_rejects_invalid_identity_before_downstream(
    provider,
    region,
    snapshot_id,
):
    fake = FakeOptimizerClient()

    with pytest.raises(ValidationError):
        await OptimizerPricingCatalogService(fake).get_exact_snapshot(
            provider,
            region,
            snapshot_id,
        )

    assert fake.calls == []


@pytest.mark.asyncio
async def test_exact_snapshot_rejects_mismatched_downstream_identity():
    requested = catalog_reference("aws")
    returned = catalog_reference("aws", identity_hex="d")
    fake = FakeOptimizerClient(
        {"reference": returned.to_http_dict(), "pricing": {"iotCore": {}}}
    )

    with pytest.raises(ValidationError, match="different pricing catalog"):
        await OptimizerPricingCatalogService(fake).get_exact_snapshot(
            requested.provider,
            requested.pricing_region,
            requested.snapshot_id,
        )


@pytest.mark.asyncio
async def test_exact_snapshot_rejects_missing_pricing_payload():
    reference = catalog_reference("gcp")
    fake = FakeOptimizerClient({"reference": reference.to_http_dict()})

    with pytest.raises(ValidationError, match="missing pricing data"):
        await OptimizerPricingCatalogService(fake).get_exact_snapshot(
            reference.provider,
            reference.pricing_region,
            reference.snapshot_id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (
            ExternalServiceError(
                "not found",
                upstream_status_code=404,
                public_detail="Pricing catalog not found",
            ),
            404,
        ),
        (ExternalServiceUnavailable("Optimizer API timed out"), 504),
    ],
)
async def test_exact_snapshot_maps_optimizer_failures(exc, status):
    reference = catalog_reference("azure")

    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerPricingCatalogService(
            FakeOptimizerClient(exc=exc)
        ).get_exact_snapshot(
            reference.provider,
            reference.pricing_region,
            reference.snapshot_id,
        )

    assert exc_info.value.status_code == status
