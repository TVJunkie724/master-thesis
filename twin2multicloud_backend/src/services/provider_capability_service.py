"""Aggregate Optimizer and Deployer capabilities into the platform contract."""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from src.clients.deployer_client import DeployerClient
from src.clients.optimizer_client import OptimizerClient
from src.schemas.provider_capability import (
    PLATFORM_CAPABILITY_SCHEMA_VERSION,
    CapabilityAvailability,
    CapabilityRoadmap,
    CapabilitySource,
    CapabilitySourceHealth,
    CapabilitySources,
    CapabilityVerificationLevel,
    PlatformCapabilitySourceHealth,
    PlatformLayerCapability,
    PlatformProviderCapabilities,
    PlatformProviderCapability,
    ServiceLayerCapability,
    ServiceProviderCapabilities,
)
from src.services.errors import ProviderCapabilityContractInvalid


_VERIFICATION_RANK = {
    CapabilityVerificationLevel.NOT_VERIFIED: 0,
    CapabilityVerificationLevel.CONTRACT_TESTED: 1,
    CapabilityVerificationLevel.LIVE_VERIFIED: 2,
}


class ProviderCapabilityService:
    def __init__(
        self,
        *,
        optimizer_client: OptimizerClient | None = None,
        deployer_client: DeployerClient | None = None,
    ) -> None:
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.deployer_client = deployer_client or DeployerClient()

    async def get_platform_capabilities(self) -> PlatformProviderCapabilities:
        optimizer_payload, deployer_payload = await asyncio.gather(
            self.optimizer_client.get_provider_capabilities(),
            self.deployer_client.get_provider_capabilities(),
        )
        optimizer = _parse_service_contract(optimizer_payload, "optimizer")
        deployer = _parse_service_contract(deployer_payload, "deployer")
        return aggregate_provider_capabilities(optimizer, deployer)


def _parse_service_contract(
    payload: object,
    expected_service: str,
) -> ServiceProviderCapabilities:
    try:
        contract = ServiceProviderCapabilities.model_validate(payload)
    except ValidationError as exc:
        raise ProviderCapabilityContractInvalid(
            f"{expected_service} provider capability contract is invalid"
        ) from exc
    if contract.service != expected_service:
        raise ProviderCapabilityContractInvalid(
            f"Expected {expected_service} capability contract, received {contract.service}"
        )
    return contract


def aggregate_provider_capabilities(
    optimizer: ServiceProviderCapabilities,
    deployer: ServiceProviderCapabilities,
) -> PlatformProviderCapabilities:
    if optimizer.service != "optimizer" or deployer.service != "deployer":
        raise ProviderCapabilityContractInvalid(
            "Capability contracts were supplied for the wrong service boundary"
        )

    providers: list[PlatformProviderCapability] = []
    for optimizer_provider, deployer_provider in zip(
        optimizer.providers,
        deployer.providers,
        strict=True,
    ):
        if optimizer_provider.provider != deployer_provider.provider:
            raise ProviderCapabilityContractInvalid(
                "Optimizer and Deployer provider identities do not align"
            )
        layers: list[PlatformLayerCapability] = []
        for optimizer_layer, deployer_layer in zip(
            optimizer_provider.layers,
            deployer_provider.layers,
            strict=True,
        ):
            if optimizer_layer.layer != deployer_layer.layer:
                raise ProviderCapabilityContractInvalid(
                    "Optimizer and Deployer layer identities do not align"
                )
            layers.append(_aggregate_layer(optimizer_layer, deployer_layer))
        providers.append(
            PlatformProviderCapability(
                provider=optimizer_provider.provider,
                layers=tuple(layers),
            )
        )

    health = CapabilitySourceHealth(
        status="available",
        schema_version="provider-service-capabilities.v1",
    )
    return PlatformProviderCapabilities(
        schema_version=PLATFORM_CAPABILITY_SCHEMA_VERSION,
        complete=True,
        sources=PlatformCapabilitySourceHealth(
            optimizer=health,
            deployer=health,
        ),
        providers=tuple(providers),
    )


def _aggregate_layer(
    optimizer: ServiceLayerCapability,
    deployer: ServiceLayerCapability,
) -> PlatformLayerCapability:
    availability = _aggregate_availability(optimizer, deployer)
    restricted_sources = [
        service
        for service, capability in (
            ("optimizer", optimizer),
            ("deployer", deployer),
        )
        if capability.availability is not CapabilityAvailability.AVAILABLE
    ]
    restriction_source = {
        (): "none",
        ("optimizer",): "restricted_by_optimizer",
        ("deployer",): "restricted_by_deployer",
        ("optimizer", "deployer"): "restricted_by_both",
    }[tuple(restricted_sources)]
    roadmap = (
        CapabilityRoadmap.PLANNED
        if availability is not CapabilityAvailability.AVAILABLE
        and CapabilityRoadmap.PLANNED in {optimizer.roadmap, deployer.roadmap}
        else CapabilityRoadmap.NONE
    )
    verification_level = min(
        (optimizer.verification_level, deployer.verification_level),
        key=_VERIFICATION_RANK.__getitem__,
    )
    reason_code, reason = _aggregate_reason(
        availability,
        optimizer,
        deployer,
    )
    return PlatformLayerCapability(
        layer=optimizer.layer,
        availability=availability,
        roadmap=roadmap,
        reason_code=reason_code,
        reason=reason,
        selectable=availability is CapabilityAvailability.AVAILABLE,
        sources_agree=optimizer.availability is deployer.availability,
        restriction_source=restriction_source,
        verification_level=verification_level,
        sources=CapabilitySources(
            optimizer=_source(optimizer),
            deployer=_source(deployer),
        ),
    )


def _aggregate_availability(
    optimizer: ServiceLayerCapability,
    deployer: ServiceLayerCapability,
) -> CapabilityAvailability:
    values = {optimizer.availability, deployer.availability}
    if CapabilityAvailability.DISABLED in values:
        return CapabilityAvailability.DISABLED
    if CapabilityAvailability.UNSUPPORTED in values:
        return CapabilityAvailability.UNSUPPORTED
    return CapabilityAvailability.AVAILABLE


def _aggregate_reason(
    availability: CapabilityAvailability,
    optimizer: ServiceLayerCapability,
    deployer: ServiceLayerCapability,
) -> tuple[str | None, str | None]:
    if availability is CapabilityAvailability.AVAILABLE:
        return None, None
    relevant = [
        (service, capability)
        for service, capability in (
            ("Optimizer", optimizer),
            ("Deployer", deployer),
        )
        if capability.availability is availability
    ]
    reason_codes = {capability.reason_code for _, capability in relevant}
    reason_code = (
        next(iter(reason_codes))
        if len(reason_codes) == 1
        else "PLATFORM_CAPABILITY_UNAVAILABLE"
    )
    reason = " ".join(
        f"{service}: {capability.reason}"
        for service, capability in relevant
    )
    return reason_code, reason


def _source(capability: ServiceLayerCapability) -> CapabilitySource:
    return CapabilitySource(
        availability=capability.availability,
        roadmap=capability.roadmap,
        reason_code=capability.reason_code,
        reason=capability.reason,
        verification_level=capability.verification_level,
    )
