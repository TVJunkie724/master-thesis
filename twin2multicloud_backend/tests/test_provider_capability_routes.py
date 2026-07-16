import pytest

from src.api.routes import provider_capabilities as route
from src.services.errors import (
    ExternalServiceError,
    ExternalServiceUnavailable,
    ProviderCapabilityContractInvalid,
)
from src.services.provider_capability_service import ProviderCapabilityService
from tests.test_provider_capability_service import FakeCapabilityClient, _payload


class FakeService:
    def __init__(self, *, result=None, error=None):
        self.result = result
        self.error = error

    async def get_platform_capabilities(self):
        if self.error:
            raise self.error
        return self.result


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (
            ProviderCapabilityContractInvalid("secret upstream detail"),
            502,
            "PROVIDER_CAPABILITY_CONTRACT_INVALID",
        ),
        (
            ExternalServiceUnavailable("secret endpoint detail"),
            503,
            "PROVIDER_CAPABILITY_SOURCE_UNAVAILABLE",
        ),
        (
            ExternalServiceError("secret response body"),
            502,
            "PROVIDER_CAPABILITY_SOURCE_ERROR",
        ),
    ],
)
def test_route_returns_sanitized_typed_errors(
    authenticated_client,
    monkeypatch,
    error,
    status_code,
    error_code,
):
    client, headers = authenticated_client
    monkeypatch.setattr(
        route,
        "get_provider_capability_service",
        lambda: FakeService(error=error),
    )

    response = client.get("/platform/provider-capabilities", headers=headers)

    assert response.status_code == status_code
    assert response.json()["error_code"] == error_code
    assert "secret" not in response.text
    assert response.json()["request_id"]


def test_route_requires_authentication(client):
    response = client.get("/platform/provider-capabilities")

    assert response.status_code == 401


def test_route_returns_aggregate_contract(authenticated_client, monkeypatch):
    client, headers = authenticated_client
    service = ProviderCapabilityService(
        optimizer_client=FakeCapabilityClient(_payload("optimizer")),
        deployer_client=FakeCapabilityClient(_payload("deployer")),
    )
    monkeypatch.setattr(
        route,
        "get_provider_capability_service",
        lambda: service,
    )

    response = client.get("/platform/provider-capabilities", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "platform-provider-capabilities.v1"
    assert payload["complete"] is True
    assert len(payload["providers"]) == 3
    assert all(len(provider["layers"]) == 7 for provider in payload["providers"])
