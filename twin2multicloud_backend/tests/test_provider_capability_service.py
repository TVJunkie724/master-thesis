from copy import deepcopy

import pytest

from src.schemas.provider_capability import (
    CapabilityAvailability,
    CapabilityVerificationLevel,
)
from src.services.errors import ProviderCapabilityContractInvalid
from src.services.provider_capability_service import ProviderCapabilityService


LAYERS = ("l1", "l2", "l3_hot", "l3_cool", "l3_archive", "l4", "l5")


def _payload(service: str, *, availability: str = "available") -> dict:
    unavailable = availability != "available"
    return {
        "schema_version": "provider-service-capabilities.v1",
        "service": service,
        "generated_from": "runtime_registry",
        "providers": [
            {
                "provider": provider,
                "layers": [
                    {
                        "layer": layer,
                        "availability": availability,
                        "roadmap": "planned" if unavailable else "none",
                        "reason_code": "TEST_UNAVAILABLE" if unavailable else None,
                        "reason": "Capability unavailable for this test." if unavailable else None,
                        "verification_level": (
                            "not_verified" if unavailable else "contract_tested"
                        ),
                    }
                    for layer in LAYERS
                ],
            }
            for provider in ("aws", "azure", "gcp")
        ],
    }


class FakeCapabilityClient:
    def __init__(self, payload: dict):
        self.payload = payload

    async def get_provider_capabilities(self) -> dict:
        return self.payload


@pytest.mark.asyncio
async def test_service_aggregates_complete_available_matrix():
    service = ProviderCapabilityService(
        optimizer_client=FakeCapabilityClient(_payload("optimizer")),
        deployer_client=FakeCapabilityClient(_payload("deployer")),
    )

    result = await service.get_platform_capabilities()

    assert result.schema_version == "platform-provider-capabilities.v1"
    assert result.complete is True
    assert len(result.providers) == 3
    assert all(len(provider.layers) == 7 for provider in result.providers)
    assert all(
        layer.selectable
        and layer.availability is CapabilityAvailability.AVAILABLE
        and layer.verification_level
        is CapabilityVerificationLevel.CONTRACT_TESTED
        for provider in result.providers
        for layer in provider.layers
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("optimizer_state", "deployer_state", "expected", "restriction_source"),
    [
        ("available", "available", "available", "none"),
        ("available", "unsupported", "unsupported", "restricted_by_deployer"),
        ("unsupported", "available", "unsupported", "restricted_by_optimizer"),
        ("unsupported", "unsupported", "unsupported", "restricted_by_both"),
        ("available", "disabled", "disabled", "restricted_by_deployer"),
        ("disabled", "available", "disabled", "restricted_by_optimizer"),
        ("disabled", "unsupported", "disabled", "restricted_by_both"),
        ("unsupported", "disabled", "disabled", "restricted_by_both"),
        ("disabled", "disabled", "disabled", "restricted_by_both"),
    ],
)
async def test_availability_precedence_is_fail_closed(
    optimizer_state,
    deployer_state,
    expected,
    restriction_source,
):
    service = ProviderCapabilityService(
        optimizer_client=FakeCapabilityClient(
            _payload("optimizer", availability=optimizer_state)
        ),
        deployer_client=FakeCapabilityClient(
            _payload("deployer", availability=deployer_state)
        ),
    )

    result = await service.get_platform_capabilities()
    layer = result.providers[0].layers[0]

    assert layer.availability.value == expected
    assert layer.selectable is (expected == "available")
    assert layer.restriction_source == restriction_source
    assert layer.sources_agree is (optimizer_state == deployer_state)


@pytest.mark.asyncio
async def test_aggregation_uses_weaker_verification_level():
    optimizer = _payload("optimizer")
    deployer = _payload("deployer")
    optimizer["providers"][0]["layers"][0]["verification_level"] = "live_verified"

    service = ProviderCapabilityService(
        optimizer_client=FakeCapabilityClient(optimizer),
        deployer_client=FakeCapabilityClient(deployer),
    )
    result = await service.get_platform_capabilities()

    assert (
        result.providers[0].layers[0].verification_level
        is CapabilityVerificationLevel.CONTRACT_TESTED
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(schema_version="provider-service-capabilities.v2"),
        lambda payload: payload["providers"].pop(),
        lambda payload: payload["providers"][0]["layers"].pop(),
        lambda payload: payload["providers"][0]["layers"].append(
            deepcopy(payload["providers"][0]["layers"][0])
        ),
        lambda payload: payload["providers"][0]["layers"][0].update(
            layer="unknown"
        ),
        lambda payload: payload["providers"][0]["layers"][0].update(
            unexpected=True
        ),
    ],
)
async def test_malformed_or_incomplete_contracts_fail_closed(mutation):
    optimizer = _payload("optimizer")
    mutation(optimizer)
    service = ProviderCapabilityService(
        optimizer_client=FakeCapabilityClient(optimizer),
        deployer_client=FakeCapabilityClient(_payload("deployer")),
    )

    with pytest.raises(ProviderCapabilityContractInvalid):
        await service.get_platform_capabilities()


@pytest.mark.asyncio
async def test_service_identity_mismatch_fails_closed():
    service = ProviderCapabilityService(
        optimizer_client=FakeCapabilityClient(_payload("deployer")),
        deployer_client=FakeCapabilityClient(_payload("deployer")),
    )

    with pytest.raises(ProviderCapabilityContractInvalid, match="Expected optimizer"):
        await service.get_platform_capabilities()
