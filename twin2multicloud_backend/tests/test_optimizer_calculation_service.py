"""Tests for optimizer calculation service boundary."""

from __future__ import annotations

import pytest

from src.services.aws_twinmaker_pricing_context_service import (
    ResolvedAwsTwinMakerPricingContext,
)
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.optimizer_calculation_service import OptimizerCalculationService
from src.services.service_errors import DownstreamServiceError
from tests.pricing_catalog_test_data import catalog_context


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
        result = self.payload.get("result", self.payload)
        if isinstance(result, dict):
            result["pricingCatalogs"] = params["providerPricingCatalogs"]
        return self.payload


class FakeAwsTwinMakerContextService:
    def __init__(self, payload=None):
        self.payload = payload or {
            "status": "unavailable",
            "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
        }
        self.calls = []

    async def resolve(self, user_id, aws_catalog_reference):
        self.calls.append((user_id, aws_catalog_reference))
        return ResolvedAwsTwinMakerPricingContext(
            payload=self.payload,
            source_refresh_run_id=None,
        )


class FakePricingCatalogContextService:
    def __init__(self):
        self.context = catalog_context()
        self.calls = []

    async def resolve_for_user(self, user_id):
        self.calls.append(user_id)
        return self.context


def _service(fake):
    return OptimizerCalculationService(
        optimizer_client=fake,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(),
        pricing_catalog_contexts=FakePricingCatalogContextService(),
    )


@pytest.mark.asyncio
async def test_calculate_forwards_params_and_returns_optimizer_payload():
    params = {"numberOfDevices": 10, "currency": "USD"}
    fake = FakeOptimizerClient({"cheapestPath": ["L1_AWS"]})

    result = await _service(fake).calculate(params, "user-1")

    assert result == {
        "cheapestPath": ["L1_AWS"],
        "pricingCatalogs": catalog_context().to_http_dict(),
    }
    assert fake.calls == [
        {
            **params,
            "providerPricingCatalogs": catalog_context().to_http_dict(),
            "providerPricingContexts": {
                "awsTwinMaker": {
                    "status": "unavailable",
                    "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
                }
            },
        }
    ]


@pytest.mark.asyncio
async def test_calculate_maps_optimizer_non_200():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            FakeOptimizerClient(
                exc=ExternalServiceError(
                    "Optimizer API returned 422: invalid params",
                    upstream_status_code=422,
                    public_detail="invalid params",
                )
            )
        ).calculate({"bad": "params"}, "user-1")

    assert exc_info.value.status_code == 422
    assert exc_info.value.public_detail == "invalid params"


@pytest.mark.asyncio
async def test_calculate_maps_timeout():
    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            FakeOptimizerClient(
                exc=ExternalServiceUnavailable("Optimizer API timed out")
            )
        ).calculate({"numberOfDevices": 10}, "user-1")

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"


@pytest.mark.asyncio
async def test_calculate_rejects_aws_l4_without_trusted_result_context():
    fake = FakeOptimizerClient(
        {
            "result": {
                "calculationResult": {"L4": "AWS"},
                "providerPricingContexts": {
                    "awsTwinMaker": {"status": "compatible"}
                },
            }
        }
    )

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(fake).calculate({"numberOfDevices": 10}, "user-1")

    assert exc_info.value.status_code == 502
    assert "trusted pricing context" in exc_info.value.public_detail


def test_calculate_route_returns_optimizer_payload(authenticated_client, sample_calc_params):
    client, headers = authenticated_client
    fake = FakeOptimizerClient({"cheapestPath": ["L1_AWS"]})

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.api.routes.optimizer._optimizer_calculation_service",
            lambda _db: _service(fake),
        )
        response = client.put("/optimizer/calculate", json=_valid_route_params(sample_calc_params), headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "cheapestPath": ["L1_AWS"],
        "pricingCatalogs": catalog_context().to_http_dict(),
    }
    assert fake.calls[0] == {
        **_valid_route_params(sample_calc_params),
        "providerPricingCatalogs": catalog_context().to_http_dict(),
        "providerPricingContexts": {
            "awsTwinMaker": {
                "status": "unavailable",
                "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
            }
        },
    }


def test_calculate_route_preserves_omitted_adt_assumption_provenance(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    fake = FakeOptimizerClient({"cheapestPath": ["L1_AWS"]})
    params = _valid_route_params(sample_calc_params)
    params.pop("averageDigitalTwinQueryUnitsPerQuery")
    params.pop("averageDigitalTwinQueryResponseSizeInKb")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.api.routes.optimizer._optimizer_calculation_service",
            lambda _db: _service(fake),
        )
        response = client.put(
            "/optimizer/calculate",
            json=params,
            headers=headers,
        )

    assert response.status_code == 200
    assert fake.calls[0] == {
        **params,
        "providerPricingCatalogs": catalog_context().to_http_dict(),
        "providerPricingContexts": {
            "awsTwinMaker": {
                "status": "unavailable",
                "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
            }
        },
    }


def test_calculate_route_maps_optimizer_timeout(authenticated_client, sample_calc_params):
    client, headers = authenticated_client

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.api.routes.optimizer._optimizer_calculation_service",
            lambda _db: _service(
                FakeOptimizerClient(
                    exc=ExternalServiceUnavailable("Optimizer API timed out"),
                ),
            ),
        )
        response = client.put("/optimizer/calculate", json=_valid_route_params(sample_calc_params), headers=headers)

    assert response.status_code == 504
    assert response.json()["detail"] == "Optimizer service timed out"


def test_calculate_route_rejects_client_supplied_provider_pricing_context(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    params = _valid_route_params(sample_calc_params)
    params["providerPricingContexts"] = {
        "awsTwinMaker": {
            "status": "available",
        }
    }

    response = client.put(
        "/optimizer/calculate",
        json=params,
        headers=headers,
    )

    assert response.status_code == 422
    assert "providerPricingContexts" in response.text
