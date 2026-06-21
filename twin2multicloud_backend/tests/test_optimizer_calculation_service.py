"""Tests for optimizer calculation service boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.optimizer_calculation_service import OptimizerCalculationService
from src.services.service_errors import DownstreamServiceError


def _valid_route_params(sample_calc_params: dict) -> dict:
    return {
        **sample_calc_params,
        "average3DModelSizeInMB": 100.0,
        "orchestrationActionsPerMessage": 1,
        "eventsPerMessage": 1,
    }


def _mock_response(status_code: int, payload: dict, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = text
    return response


@pytest.mark.asyncio
async def test_calculate_forwards_params_and_returns_optimizer_payload():
    params = {"numberOfDevices": 10, "currency": "USD"}

    with patch("src.services.optimizer_calculation_service.httpx.AsyncClient") as mock_client:
        put = AsyncMock(return_value=_mock_response(200, {"cheapestPath": ["L1_AWS"]}))
        mock_client.return_value.__aenter__.return_value.put = put

        result = await OptimizerCalculationService().calculate(params)

    assert result == {"cheapestPath": ["L1_AWS"]}
    assert put.call_args.args[0].endswith("/calculate")
    assert put.call_args.kwargs["json"] == params


@pytest.mark.asyncio
async def test_calculate_maps_optimizer_non_200():
    with patch("src.services.optimizer_calculation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.put = AsyncMock(
            return_value=_mock_response(422, {}, "invalid params")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await OptimizerCalculationService().calculate({"bad": "params"})

    assert exc_info.value.status_code == 422
    assert exc_info.value.public_detail == "invalid params"


@pytest.mark.asyncio
async def test_calculate_maps_timeout():
    with patch("src.services.optimizer_calculation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.put = AsyncMock(
            side_effect=httpx.TimeoutException("read timed out")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await OptimizerCalculationService().calculate({"numberOfDevices": 10})

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"


def test_calculate_route_returns_optimizer_payload(authenticated_client, sample_calc_params):
    client, headers = authenticated_client

    with patch("src.services.optimizer_calculation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.put = AsyncMock(
            return_value=_mock_response(200, {"cheapestPath": ["L1_AWS"]})
        )

        response = client.put("/optimizer/calculate", json=_valid_route_params(sample_calc_params), headers=headers)

    assert response.status_code == 200
    assert response.json() == {"cheapestPath": ["L1_AWS"]}


def test_calculate_route_maps_optimizer_timeout(authenticated_client, sample_calc_params):
    client, headers = authenticated_client

    with patch("src.services.optimizer_calculation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.put = AsyncMock(
            side_effect=httpx.TimeoutException("read timed out")
        )

        response = client.put("/optimizer/calculate", json=_valid_route_params(sample_calc_params), headers=headers)

    assert response.status_code == 504
    assert response.json()["detail"] == "Optimizer service timed out"
