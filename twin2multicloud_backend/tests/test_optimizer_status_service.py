"""Tests for optimizer status service boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.optimizer_status_service import OptimizerStatusService
from src.services.service_errors import DownstreamServiceError


def _mock_response(status_code: int, payload: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_get_pricing_status_aggregates_all_providers():
    responses = [
        _mock_response(200, {"age": "1 day"}),
        _mock_response(200, {"age": "2 days"}),
        _mock_response(200, {"age": "3 days"}),
    ]

    with patch("src.services.optimizer_status_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=responses)

        result = await OptimizerStatusService().get_pricing_status()

    assert result == {
        "aws": {"age": "1 day"},
        "azure": {"age": "2 days"},
        "gcp": {"age": "3 days"},
    }


@pytest.mark.asyncio
async def test_get_regions_status_returns_error_for_failed_provider():
    responses = [
        _mock_response(200, {"age": "1 day"}),
        _mock_response(500, {"detail": "boom"}),
        _mock_response(200, {"age": "3 days"}),
    ]

    with patch("src.services.optimizer_status_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=responses)

        result = await OptimizerStatusService().get_regions_status()

    assert result["aws"] == {"age": "1 day"}
    assert result["azure"] == {"error": "Failed to fetch"}
    assert result["gcp"] == {"age": "3 days"}


@pytest.mark.asyncio
async def test_get_pricing_status_maps_connect_error():
    with patch("src.services.optimizer_status_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await OptimizerStatusService().get_pricing_status()

    assert exc_info.value.status_code == 503
    assert exc_info.value.public_detail == "Cannot connect to Optimizer service"


@pytest.mark.asyncio
async def test_get_regions_status_maps_timeout():
    with patch("src.services.optimizer_status_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("read timed out")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await OptimizerStatusService().get_regions_status()

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"
