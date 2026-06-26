"""Tests for optimizer pricing export service boundary."""

from __future__ import annotations

import pytest

from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.optimizer_pricing_export_service import OptimizerPricingExportService
from src.services.service_errors import DownstreamServiceError, ValidationError


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload or {}
        self.exc = exc
        self.calls = []

    async def export_pricing_snapshot(self, provider):
        self.calls.append(provider)
        if self.exc:
            raise self.exc
        return self.payload


@pytest.mark.asyncio
async def test_export_pricing_snapshot_returns_provider_payload():
    fake = FakeOptimizerClient({"provider": "aws", "prices": []})
    result = await OptimizerPricingExportService(optimizer_client=fake).export_pricing_snapshot("aws")

    assert result == {"provider": "aws", "prices": []}
    assert fake.calls == ["aws"]


@pytest.mark.asyncio
async def test_export_pricing_snapshot_rejects_unknown_provider_before_downstream_call():
    fake = FakeOptimizerClient()
    with pytest.raises(ValidationError, match="Invalid provider: digitalocean"):
        await OptimizerPricingExportService(optimizer_client=fake).export_pricing_snapshot("digitalocean")

    assert fake.calls == []


@pytest.mark.asyncio
async def test_export_pricing_snapshot_maps_optimizer_non_200():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerPricingExportService(
            optimizer_client=FakeOptimizerClient(
                exc=ExternalServiceError(
                    "Optimizer API returned 503: optimizer unavailable",
                    upstream_status_code=503,
                    public_detail="optimizer unavailable",
                )
            )
        ).export_pricing_snapshot("azure")

    assert exc_info.value.status_code == 503
    assert exc_info.value.public_detail == "optimizer unavailable"


@pytest.mark.asyncio
async def test_export_pricing_snapshot_maps_timeout():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerPricingExportService(
            optimizer_client=FakeOptimizerClient(
                exc=ExternalServiceUnavailable("Optimizer API timed out")
            )
        ).export_pricing_snapshot("gcp")

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"
