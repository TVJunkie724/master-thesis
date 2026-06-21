"""Tests for optimizer pricing export service boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.optimizer_pricing_export_service import OptimizerPricingExportService
from src.services.service_errors import DownstreamServiceError, ValidationError


def _mock_response(status_code: int, payload: dict, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = text
    return response


@pytest.mark.asyncio
async def test_export_pricing_snapshot_returns_provider_payload():
    with patch("src.services.optimizer_pricing_export_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response(200, {"provider": "aws", "prices": []})
        )

        result = await OptimizerPricingExportService().export_pricing_snapshot("aws")

    assert result == {"provider": "aws", "prices": []}
    called_url = mock_client.return_value.__aenter__.return_value.get.call_args.args[0]
    assert called_url.endswith("/pricing/export/aws")


@pytest.mark.asyncio
async def test_export_pricing_snapshot_rejects_unknown_provider_before_downstream_call():
    with patch("src.services.optimizer_pricing_export_service.httpx.AsyncClient") as mock_client:
        with pytest.raises(ValidationError, match="Invalid provider: digitalocean"):
            await OptimizerPricingExportService().export_pricing_snapshot("digitalocean")

    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_export_pricing_snapshot_maps_optimizer_non_200():
    with patch("src.services.optimizer_pricing_export_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response(503, {}, "optimizer unavailable")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await OptimizerPricingExportService().export_pricing_snapshot("azure")

    assert exc_info.value.status_code == 503
    assert exc_info.value.public_detail == "optimizer unavailable"


@pytest.mark.asyncio
async def test_export_pricing_snapshot_maps_timeout():
    with patch("src.services.optimizer_pricing_export_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("read timed out")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await OptimizerPricingExportService().export_pricing_snapshot("gcp")

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"
