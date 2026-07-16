"""Strict provider capability contracts for service and platform boundaries."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


SERVICE_CAPABILITY_SCHEMA_VERSION = "provider-service-capabilities.v1"
PLATFORM_CAPABILITY_SCHEMA_VERSION = "platform-provider-capabilities.v1"

ProviderId = Literal["aws", "azure", "gcp"]
LayerId = Literal["l1", "l2", "l3_hot", "l3_cool", "l3_archive", "l4", "l5"]

PROVIDER_IDS: tuple[ProviderId, ...] = ("aws", "azure", "gcp")
LAYER_IDS: tuple[LayerId, ...] = (
    "l1",
    "l2",
    "l3_hot",
    "l3_cool",
    "l3_archive",
    "l4",
    "l5",
)


class CapabilityAvailability(str, Enum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"


class CapabilityRoadmap(str, Enum):
    NONE = "none"
    PLANNED = "planned"


class CapabilityVerificationLevel(str, Enum):
    NOT_VERIFIED = "not_verified"
    CONTRACT_TESTED = "contract_tested"
    LIVE_VERIFIED = "live_verified"


class ServiceLayerCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: LayerId
    availability: CapabilityAvailability
    roadmap: CapabilityRoadmap
    reason_code: str | None
    reason: str | None
    verification_level: CapabilityVerificationLevel

    @model_validator(mode="after")
    def validate_state(self) -> "ServiceLayerCapability":
        has_reason = bool((self.reason or "").strip())
        has_code = bool((self.reason_code or "").strip())
        if self.availability is CapabilityAvailability.AVAILABLE:
            if has_reason or has_code or self.roadmap is not CapabilityRoadmap.NONE:
                raise ValueError("Available capability metadata is inconsistent")
        elif not has_reason or not has_code:
            raise ValueError("Unavailable capabilities require a reason code and reason")
        return self


class ServiceProviderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderId
    layers: tuple[ServiceLayerCapability, ...]

    @model_validator(mode="after")
    def validate_layers(self) -> "ServiceProviderCapability":
        if tuple(item.layer for item in self.layers) != LAYER_IDS:
            raise ValueError("Provider capability matrix is incomplete or unordered")
        return self


class ServiceProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["provider-service-capabilities.v1"]
    service: Literal["optimizer", "deployer"]
    generated_from: Literal["runtime_registry"]
    providers: tuple[ServiceProviderCapability, ...]

    @model_validator(mode="after")
    def validate_providers(self) -> "ServiceProviderCapabilities":
        if tuple(item.provider for item in self.providers) != PROVIDER_IDS:
            raise ValueError("Capability matrix must contain every provider exactly once")
        return self


class CapabilitySource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: CapabilityAvailability
    roadmap: CapabilityRoadmap
    reason_code: str | None
    reason: str | None
    verification_level: CapabilityVerificationLevel


class CapabilitySources(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    optimizer: CapabilitySource
    deployer: CapabilitySource


class PlatformLayerCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: LayerId
    availability: CapabilityAvailability
    roadmap: CapabilityRoadmap
    reason_code: str | None
    reason: str | None
    selectable: bool
    sources_agree: bool
    restriction_source: Literal[
        "none",
        "restricted_by_optimizer",
        "restricted_by_deployer",
        "restricted_by_both",
    ]
    verification_level: CapabilityVerificationLevel
    sources: CapabilitySources


class PlatformProviderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderId
    layers: tuple[PlatformLayerCapability, ...]


class CapabilitySourceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["available"]
    schema_version: Literal["provider-service-capabilities.v1"]


class PlatformCapabilitySourceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    optimizer: CapabilitySourceHealth
    deployer: CapabilitySourceHealth


class PlatformProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["platform-provider-capabilities.v1"]
    complete: Literal[True]
    sources: PlatformCapabilitySourceHealth
    providers: tuple[PlatformProviderCapability, ...]
