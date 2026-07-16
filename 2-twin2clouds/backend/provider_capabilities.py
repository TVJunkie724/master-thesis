"""Provider-layer calculation capability registry."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from backend.calculation_v2.layers.aws_layers import AWSLayerCalculators
from backend.calculation_v2.layers.azure_layers import AzureLayerCalculators
from backend.calculation_v2.layers.gcp_layers import GCPLayerCalculators


SERVICE_CAPABILITY_SCHEMA_VERSION = "provider-service-capabilities.v1"

ProviderId = Literal["aws", "azure", "gcp"]
LayerId = Literal["l1", "l2", "l3_hot", "l3_cool", "l3_archive", "l4", "l5"]

LAYER_IDS: tuple[LayerId, ...] = (
    "l1",
    "l2",
    "l3_hot",
    "l3_cool",
    "l3_archive",
    "l4",
    "l5",
)

_CALCULATOR_LAYER_IDS = {
    "l1": "L1",
    "l2": "L2",
    "l3_hot": "L3_hot",
    "l3_cool": "L3_cool",
    "l3_archive": "L3_archive",
    "l4": "L4",
    "l5": "L5",
}


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


class ProviderLayerCapability(BaseModel):
    """One provider-layer capability owned by the Optimizer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: LayerId
    availability: CapabilityAvailability
    roadmap: CapabilityRoadmap = CapabilityRoadmap.NONE
    reason_code: str | None = None
    reason: str | None = None
    verification_level: CapabilityVerificationLevel

    @model_validator(mode="after")
    def validate_state(self) -> "ProviderLayerCapability":
        has_reason = bool((self.reason or "").strip())
        has_code = bool((self.reason_code or "").strip())
        if self.availability is CapabilityAvailability.AVAILABLE:
            if has_reason or has_code:
                raise ValueError("Available capabilities cannot declare a reason")
            if self.roadmap is not CapabilityRoadmap.NONE:
                raise ValueError("Available capabilities cannot be marked planned")
        elif not has_reason or not has_code:
            raise ValueError("Unavailable capabilities require a reason code and reason")
        return self


class ProviderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderId
    layers: tuple[ProviderLayerCapability, ...]

    @model_validator(mode="after")
    def validate_layers(self) -> "ProviderCapability":
        layer_ids = tuple(item.layer for item in self.layers)
        if layer_ids != LAYER_IDS:
            raise ValueError("Provider capabilities must contain every canonical layer")
        return self


class ServiceProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["provider-service-capabilities.v1"]
    service: Literal["optimizer"]
    generated_from: Literal["runtime_registry"]
    providers: tuple[ProviderCapability, ...]

    @model_validator(mode="after")
    def validate_providers(self) -> "ServiceProviderCapabilities":
        if tuple(item.provider for item in self.providers) != ("aws", "azure", "gcp"):
            raise ValueError("Capabilities must contain AWS, Azure, and GCP exactly once")
        return self


_CALCULATORS = {
    "aws": AWSLayerCalculators,
    "azure": AzureLayerCalculators,
    "gcp": GCPLayerCalculators,
}

_PLANNED_UNSUPPORTED = {
    ("gcp", "l4"): (
        "CALCULATION_NOT_IMPLEMENTED",
        "GCP L4 calculation is outside the implemented thesis path.",
    ),
    ("gcp", "l5"): (
        "CALCULATION_NOT_IMPLEMENTED",
        "GCP L5 calculation is outside the implemented thesis path.",
    ),
}


def get_provider_capabilities() -> ServiceProviderCapabilities:
    """Build the public contract from executable calculator declarations."""
    providers: list[ProviderCapability] = []
    for provider_id, calculator_type in _CALCULATORS.items():
        layers: list[ProviderLayerCapability] = []
        for layer_id in LAYER_IDS:
            calculator_layer = _CALCULATOR_LAYER_IDS[layer_id]
            if calculator_layer in calculator_type.supported_layers:
                layers.append(
                    ProviderLayerCapability(
                        layer=layer_id,
                        availability=CapabilityAvailability.AVAILABLE,
                        verification_level=CapabilityVerificationLevel.CONTRACT_TESTED,
                    )
                )
                continue

            reason_code, reason = _PLANNED_UNSUPPORTED.get(
                (provider_id, layer_id),
                (
                    "CALCULATION_NOT_IMPLEMENTED",
                    f"{provider_id.upper()} {layer_id} calculation is not implemented.",
                ),
            )
            layers.append(
                ProviderLayerCapability(
                    layer=layer_id,
                    availability=CapabilityAvailability.UNSUPPORTED,
                    roadmap=(
                        CapabilityRoadmap.PLANNED
                        if (provider_id, layer_id) in _PLANNED_UNSUPPORTED
                        else CapabilityRoadmap.NONE
                    ),
                    reason_code=reason_code,
                    reason=reason,
                    verification_level=CapabilityVerificationLevel.NOT_VERIFIED,
                )
            )
        providers.append(
            ProviderCapability(provider=provider_id, layers=tuple(layers))
        )

    return ServiceProviderCapabilities(
        schema_version=SERVICE_CAPABILITY_SCHEMA_VERSION,
        service="optimizer",
        generated_from="runtime_registry",
        providers=tuple(providers),
    )
