"""Tests for optimizer status service boundary."""

from __future__ import annotations

import pytest

from src.clients.optimizer_client import OptimizerProviderStatus
from src.services.errors import ExternalServiceUnavailable
from src.services.optimizer_status_service import OptimizerStatusService
from src.services.service_errors import DownstreamServiceError


class FakeOptimizerClient:
    def __init__(self, results=None, exc=None):
        self.results = list(results or [])
        self.exc = exc
        self.calls = []

    async def get_cache_status(self, *, endpoint_prefix: str, provider: str):
        self.calls.append((endpoint_prefix, provider))
        if self.exc:
            raise self.exc
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_get_pricing_status_aggregates_all_providers():
    responses = [
        OptimizerProviderStatus("aws", 200, {"age": "1 day"}),
        OptimizerProviderStatus("azure", 200, {"age": "2 days"}),
        OptimizerProviderStatus("gcp", 200, {"age": "3 days"}),
    ]
    client = FakeOptimizerClient(responses)

    result = await OptimizerStatusService(optimizer_client=client).get_pricing_status()

    assert result == {
        "aws": {"age": "1 day"},
        "azure": {"age": "2 days"},
        "gcp": {"age": "3 days"},
    }
    assert client.calls == [
        ("pricing_age", "aws"),
        ("pricing_age", "azure"),
        ("pricing_age", "gcp"),
    ]


@pytest.mark.asyncio
async def test_get_regions_status_returns_error_for_failed_provider():
    responses = [
        OptimizerProviderStatus("aws", 200, {"age": "1 day"}),
        OptimizerProviderStatus("azure", 500, {}),
        OptimizerProviderStatus("gcp", 200, {"age": "3 days"}),
    ]
    client = FakeOptimizerClient(responses)

    result = await OptimizerStatusService(optimizer_client=client).get_regions_status()

    assert result["aws"] == {"age": "1 day"}
    assert result["azure"] == {"error": "Failed to fetch"}
    assert result["gcp"] == {"age": "3 days"}
    assert client.calls == [
        ("regions_age", "aws"),
        ("regions_age", "azure"),
        ("regions_age", "gcp"),
    ]


@pytest.mark.asyncio
async def test_get_pricing_status_maps_connect_error():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerStatusService(
            optimizer_client=FakeOptimizerClient(
                exc=ExternalServiceUnavailable("Optimizer API unavailable")
            )
        ).get_pricing_status()

    assert exc_info.value.status_code == 503
    assert exc_info.value.public_detail == "Cannot connect to Optimizer service"


@pytest.mark.asyncio
async def test_get_regions_status_maps_timeout():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerStatusService(
            optimizer_client=FakeOptimizerClient(
                exc=ExternalServiceUnavailable("Optimizer API timed out")
            )
        ).get_regions_status()

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"
