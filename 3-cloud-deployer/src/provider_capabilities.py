"""Provider-layer deployment capability registry and enforcement."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, model_validator


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

_TERRAFORM_LAYER_KEYS = {
    "layer_1_provider": "l1",
    "layer_2_provider": "l2",
    "layer_3_hot_provider": "l3_hot",
    "layer_3_cold_provider": "l3_cool",
    "layer_3_archive_provider": "l3_archive",
    "layer_4_provider": "l4",
    "layer_5_provider": "l5",
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
        if tuple(item.layer for item in self.layers) != LAYER_IDS:
            raise ValueError("Provider capabilities must contain every canonical layer")
        return self


class ServiceProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["provider-service-capabilities.v1"]
    service: Literal["deployer"]
    generated_from: Literal["runtime_registry"]
    providers: tuple[ProviderCapability, ...]

    @model_validator(mode="after")
    def validate_providers(self) -> "ServiceProviderCapabilities":
        if tuple(item.provider for item in self.providers) != ("aws", "azure", "gcp"):
            raise ValueError("Capabilities must contain AWS, Azure, and GCP exactly once")
        return self


class ProviderCapabilityViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderId
    layer: LayerId
    availability: CapabilityAvailability
    reason_code: str
    reason: str


class ProviderCapabilityError(ValueError):
    """Raised before package side effects for unsupported selections."""

    def __init__(self, violations: tuple[ProviderCapabilityViolation, ...]):
        self.violations = violations
        summary = ", ".join(
            f"{item.provider}:{item.layer} ({item.reason_code})"
            for item in violations
        )
        super().__init__(f"Provider capability unavailable: {summary}")


_GCP_UNSUPPORTED = {
    "l4": (
        "DEPLOYMENT_PATH_NOT_IMPLEMENTED",
        "GCP L4 deployment is outside the implemented thesis path.",
    ),
    "l5": (
        "DEPLOYMENT_PATH_NOT_IMPLEMENTED",
        "GCP L5 deployment is outside the implemented thesis path.",
    ),
}


def _build_provider(provider: ProviderId) -> ProviderCapability:
    layers: list[ProviderLayerCapability] = []
    for layer in LAYER_IDS:
        unsupported = _GCP_UNSUPPORTED.get(layer) if provider == "gcp" else None
        if unsupported is None:
            layers.append(
                ProviderLayerCapability(
                    layer=layer,
                    availability=CapabilityAvailability.AVAILABLE,
                    verification_level=CapabilityVerificationLevel.CONTRACT_TESTED,
                )
            )
        else:
            reason_code, reason = unsupported
            layers.append(
                ProviderLayerCapability(
                    layer=layer,
                    availability=CapabilityAvailability.UNSUPPORTED,
                    roadmap=CapabilityRoadmap.PLANNED,
                    reason_code=reason_code,
                    reason=reason,
                    verification_level=CapabilityVerificationLevel.NOT_VERIFIED,
                )
            )
    return ProviderCapability(provider=provider, layers=tuple(layers))


_CAPABILITIES = ServiceProviderCapabilities(
    schema_version=SERVICE_CAPABILITY_SCHEMA_VERSION,
    service="deployer",
    generated_from="runtime_registry",
    providers=tuple(_build_provider(provider) for provider in ("aws", "azure", "gcp")),
)


def get_provider_capabilities() -> ServiceProviderCapabilities:
    return _CAPABILITIES


def get_provider_layer_capability(
    provider: str,
    layer: str,
) -> ProviderLayerCapability:
    normalized_provider = (
        "gcp" if provider.strip().lower() == "google" else provider.strip().lower()
    )
    if normalized_provider not in {"aws", "azure", "gcp"}:
        raise ValueError(f"Unknown provider: {provider!r}")
    if layer not in LAYER_IDS:
        raise ValueError(f"Unknown layer: {layer!r}")
    provider_contract = next(
        item for item in _CAPABILITIES.providers if item.provider == normalized_provider
    )
    return next(item for item in provider_contract.layers if item.layer == layer)


def validate_provider_selections(
    selections: Mapping[str, str],
) -> tuple[ProviderCapabilityViolation, ...]:
    violations: list[ProviderCapabilityViolation] = []
    for layer, provider in selections.items():
        if provider.strip().lower() == "none":
            continue
        capability = get_provider_layer_capability(provider, layer)
        if capability.availability is CapabilityAvailability.AVAILABLE:
            continue
        normalized_provider = (
            "gcp" if provider.strip().lower() == "google" else provider.strip().lower()
        )
        violations.append(
            ProviderCapabilityViolation(
                provider=normalized_provider,
                layer=layer,
                availability=capability.availability,
                reason_code=capability.reason_code or "CAPABILITY_UNAVAILABLE",
                reason=capability.reason or "Provider capability unavailable.",
            )
        )
    return tuple(violations)


def selections_from_terraform_config(config: Mapping[str, object]) -> dict[str, str]:
    selections: dict[str, str] = {}
    for config_key, layer in _TERRAFORM_LAYER_KEYS.items():
        provider = config.get(config_key)
        if isinstance(provider, str) and provider.strip():
            selections[layer] = provider
    return selections


def validate_terraform_provider_capabilities(config: Mapping[str, object]) -> None:
    violations = validate_provider_selections(selections_from_terraform_config(config))
    if violations:
        raise ProviderCapabilityError(violations)


def selections_from_cheapest_path(path: Mapping[str, object]) -> dict[str, str]:
    selections: dict[str, str] = {}
    direct_keys = {"L1": "l1", "L2": "l2", "L4": "l4", "L5": "l5"}
    for path_key, layer in direct_keys.items():
        value = path.get(path_key, path.get(path_key.lower()))
        if isinstance(value, str) and value.strip():
            selections[layer] = value

    nested_l3 = path.get("L3", path.get("l3"))
    if isinstance(nested_l3, Mapping):
        for tier, layer in (
            ("Hot", "l3_hot"),
            ("Cool", "l3_cool"),
            ("Archive", "l3_archive"),
        ):
            value = nested_l3.get(tier, nested_l3.get(tier.lower()))
            if isinstance(value, str) and value.strip():
                selections[layer] = value
    for key, layer in (
        ("L3_hot", "l3_hot"),
        ("L3_cool", "l3_cool"),
        ("L3_cold", "l3_cool"),
        ("L3_archive", "l3_archive"),
    ):
        value = path.get(key, path.get(key.lower()))
        if isinstance(value, str) and value.strip():
            selections[layer] = value
    return selections
