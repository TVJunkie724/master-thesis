"""Tests for optimizer calculation service boundary."""

from __future__ import annotations

import pytest

from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.optimizer_calculation_service import OptimizerCalculationService
from src.services.service_errors import DownstreamServiceError


def _valid_route_params(sample_calc_params: dict) -> dict:
    return {
        **sample_calc_params,
        "average3DModelSizeInMB": 100.0,
        "orchestrationActionsPerMessage": 1,
        "eventsPerMessage": 1,
    }


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload or {}
        self.exc = exc
        self.calls = []

    async def calculate(self, params):
        self.calls.append(params)
        if self.exc:
            raise self.exc
        return self.payload


@pytest.mark.asyncio
async def test_calculate_forwards_params_and_returns_optimizer_payload():
    params = {"numberOfDevices": 10, "currency": "USD"}
    fake = FakeOptimizerClient({"cheapestPath": ["L1_AWS"]})

    result = await OptimizerCalculationService(optimizer_client=fake).calculate(params)

    assert result == {"cheapestPath": ["L1_AWS"]}
    assert fake.calls == [params]


@pytest.mark.asyncio
async def test_calculate_maps_optimizer_non_200():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerCalculationService(
            optimizer_client=FakeOptimizerClient(
                exc=ExternalServiceError(
                    "Optimizer API returned 422: invalid params",
                    upstream_status_code=422,
                    public_detail="invalid params",
                )
            )
        ).calculate({"bad": "params"})

    assert exc_info.value.status_code == 422
    assert exc_info.value.public_detail == "invalid params"


@pytest.mark.asyncio
async def test_calculate_maps_timeout():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await OptimizerCalculationService(
            optimizer_client=FakeOptimizerClient(
                exc=ExternalServiceUnavailable("Optimizer API timed out")
            )
        ).calculate({"numberOfDevices": 10})

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"


def test_calculate_route_returns_optimizer_payload(authenticated_client, sample_calc_params):
    client, headers = authenticated_client

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.api.routes.optimizer._optimizer_calculation_service",
            lambda: OptimizerCalculationService(
                optimizer_client=FakeOptimizerClient({"cheapestPath": ["L1_AWS"]})
            ),
        )
        response = client.put("/optimizer/calculate", json=_valid_route_params(sample_calc_params), headers=headers)

    assert response.status_code == 200
    assert response.json() == {"cheapestPath": ["L1_AWS"]}


def test_calculate_route_maps_optimizer_timeout(authenticated_client, sample_calc_params):
    client, headers = authenticated_client

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.api.routes.optimizer._optimizer_calculation_service",
            lambda: OptimizerCalculationService(
                optimizer_client=FakeOptimizerClient(
                    exc=ExternalServiceUnavailable("Optimizer API timed out")
                )
            ),
        )
        response = client.put("/optimizer/calculate", json=_valid_route_params(sample_calc_params), headers=headers)

    assert response.status_code == 504
    assert response.json()["detail"] == "Optimizer service timed out"
