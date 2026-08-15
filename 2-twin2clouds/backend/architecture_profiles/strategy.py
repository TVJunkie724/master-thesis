"""Typed strategy and request boundary for architecture profile resolution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import UUID

from . import contracts
from .diagnostics import ArchitectureResolutionError
from .registry import ArchitectureProfileRegistry


BUNDLE_FIELDS = (
    "optimization_strategy_id",
    "optimization_strategy_version",
    "calculation_strategy_id",
    "calculation_strategy_version",
    "formula_set_id",
    "formula_set_version",
    "scoring_strategy_id",
    "scoring_strategy_version",
    "compatibility_digest",
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_STABLE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True, order=True)
class ArchitectureProfileRef:
    profile_id: str
    profile_version: str
    content_digest: str

    @classmethod
    def from_profile(
        cls,
        profile: Mapping[str, Any],
    ) -> "ArchitectureProfileRef":
        return cls(
            profile_id=str(profile["profile_id"]),
            profile_version=str(profile["profile_version"]),
            content_digest=str(profile["content_digest"]),
        )


@dataclass(frozen=True, order=True)
class OptimizationBundleRef:
    optimization_strategy_id: str
    optimization_strategy_version: str
    calculation_strategy_id: str
    calculation_strategy_version: str
    formula_set_id: str
    formula_set_version: str
    scoring_strategy_id: str
    scoring_strategy_version: str
    compatibility_digest: str

    @classmethod
    def from_profile(
        cls,
        profile: Mapping[str, Any],
    ) -> "OptimizationBundleRef":
        bundle = profile["optimization_bundle"]
        return cls(
            **{field: str(bundle[field]) for field in BUNDLE_FIELDS}
        )

    def to_contract(self) -> dict[str, str]:
        return {
            field: getattr(self, field)
            for field in BUNDLE_FIELDS
        }


@dataclass(frozen=True)
class ExtensionBindingRef:
    slot_id: str
    slot_version: str
    artifact_id: str
    artifact_digest: str
    configuration_digest: str
    logical_component_id: str
    validation_contract_version: str

    def to_contract(self) -> dict[str, str]:
        return {
            "slot_id": self.slot_id,
            "slot_version": self.slot_version,
            "artifact_id": self.artifact_id,
            "artifact_digest": self.artifact_digest,
            "logical_component_id": self.logical_component_id,
            "configuration_digest": self.configuration_digest,
            "validation_contract_version": self.validation_contract_version,
        }


@dataclass(frozen=True)
class ArchitectureResolutionContext:
    calculation_run_id: str
    profile_ref: ArchitectureProfileRef
    bundle_ref: OptimizationBundleRef
    profile: Mapping[str, Any]
    catalog: Mapping[str, Any]
    provider_profiles: Mapping[str, Mapping[str, Any]]
    extension_bindings: tuple[ExtensionBindingRef, ...]
    resolution_status: str = "publishable"
    layer_options: Mapping[
        str,
        tuple[tuple[str, Decimal], ...],
    ] | None = None
    provider_regions: Mapping[str, str] | None = None

    @property
    def linked_documents(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.profile,
            *self.provider_profiles.values(),
            self.catalog,
        )

    def with_execution_inputs(
        self,
        *,
        layer_options: Mapping[str, tuple[tuple[str, float], ...]],
        provider_regions: Mapping[str, str],
    ) -> "ArchitectureResolutionContext":
        normalized_options = MappingProxyType(
            {
                layer_key: tuple(
                    (provider, Decimal(str(cost)))
                    for provider, cost in options
                )
                for layer_key, options in layer_options.items()
            }
        )
        return replace(
            self,
            layer_options=normalized_options,
            provider_regions=MappingProxyType(dict(provider_regions)),
        )


@runtime_checkable
class ArchitectureOptimizationStrategy(Protocol):
    """Closed-world profile strategy implemented by an approved adapter."""

    strategy_id: str
    supported_profile_refs: frozenset[ArchitectureProfileRef]

    def validate_request(self, context: ArchitectureResolutionContext) -> None: ...

    def enumerate_candidates(
        self,
        context: ArchitectureResolutionContext,
    ) -> tuple[Any, ...]: ...

    def validate_functional_completeness(
        self,
        candidate: Any,
        context: ArchitectureResolutionContext,
    ) -> Any: ...

    def calculate_candidate(
        self,
        candidate: Any,
        context: ArchitectureResolutionContext,
    ) -> Any: ...

    def resolve_edges(
        self,
        candidate: Any,
        context: ArchitectureResolutionContext,
    ) -> Any: ...

    def build_resolution(
        self,
        winner: Any,
        context: ArchitectureResolutionContext,
    ) -> Mapping[str, Any]: ...


class ArchitectureStrategyRegistry:
    """Register one strategy per exact immutable optimization bundle."""

    def __init__(self) -> None:
        self._strategies: dict[
            OptimizationBundleRef,
            ArchitectureOptimizationStrategy,
        ] = {}
        self._frozen = False

    def register(
        self,
        profile: Mapping[str, Any],
        strategy: ArchitectureOptimizationStrategy,
    ) -> None:
        if self._frozen:
            raise RuntimeError("Architecture strategy registry is frozen")
        profile_ref = ArchitectureProfileRef.from_profile(profile)
        if profile_ref not in strategy.supported_profile_refs:
            raise RuntimeError(
                "Architecture strategy does not declare the registered profile"
            )
        bundle_ref = OptimizationBundleRef.from_profile(profile)
        if bundle_ref in self._strategies:
            raise RuntimeError(
                "Duplicate architecture strategy bundle registration"
            )
        self._strategies[bundle_ref] = strategy

    def freeze(self) -> None:
        if not self._strategies:
            raise RuntimeError(
                "Architecture strategy registry has no registered strategy"
            )
        self._frozen = True

    def resolve(
        self,
        profile: Mapping[str, Any],
    ) -> ArchitectureOptimizationStrategy:
        if not self._frozen:
            raise RuntimeError("Architecture strategy registry is not frozen")
        bundle_ref = OptimizationBundleRef.from_profile(profile)
        strategy = self._strategies.get(bundle_ref)
        profile_ref = ArchitectureProfileRef.from_profile(profile)
        if (
            strategy is None
            or profile_ref not in strategy.supported_profile_refs
        ):
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "architectureProfile",
                "No registered strategy supports the exact profile bundle",
            )
        return strategy


def build_resolution_context(
    *,
    registry: ArchitectureProfileRegistry,
    calculation_run_id: str,
    architecture_profile: Mapping[str, Any],
    extension_bindings: object,
    resolution_status: str = "publishable",
) -> ArchitectureResolutionContext:
    """Validate references only and return immutable repository definitions."""

    try:
        normalized_run_id = str(UUID(str(calculation_run_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "calculationRunId",
            "Calculation run ID must be a UUID",
        ) from exc
    required_profile_keys = {
        "profileId",
        "profileVersion",
        "contentDigest",
    }
    if set(architecture_profile) != required_profile_keys:
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_NOT_FOUND",
            "architectureProfile",
            "Architecture profile must contain only an exact immutable reference",
        )
    try:
        profile = registry.require_profile(
            profile_id=str(architecture_profile["profileId"]),
            profile_version=str(architecture_profile["profileVersion"]),
            content_digest=str(architecture_profile["contentDigest"]),
        )
    except contracts.ContractError as exc:
        code = (
            exc.code
            if exc.code in {
                "ARCH_PROFILE_NOT_FOUND",
                "ARCH_PROFILE_DIGEST_MISMATCH",
            }
            else "ARCH_PROFILE_NOT_FOUND"
        )
        raise ArchitectureResolutionError(
            code,
            exc.path,
            str(exc),
        ) from exc
    if resolution_status not in {"publishable", "offline_contract_fixture"}:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "resolutionStatus",
            "Architecture resolution status is unsupported",
        )
    if (
        resolution_status == "offline_contract_fixture"
        and profile["schema_version"] != "architecture-profile.v2"
    ):
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
            "resolutionStatus",
            "Offline draft resolution is restricted to v2 implementation evidence",
        )
    if (
        resolution_status == "publishable"
        and profile["lifecycle_status"] != "active"
    ):
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_NOT_FOUND",
            "architectureProfile",
            "Architecture profile is not active",
        )
    normalized_bindings = _validate_extension_bindings(
        profile,
        extension_bindings,
    )
    return ArchitectureResolutionContext(
        calculation_run_id=normalized_run_id,
        profile_ref=ArchitectureProfileRef.from_profile(profile),
        bundle_ref=OptimizationBundleRef.from_profile(profile),
        profile=profile,
        catalog=registry.catalog,
        provider_profiles=MappingProxyType(dict(registry.providers)),
        extension_bindings=normalized_bindings,
        resolution_status=resolution_status,
    )


def _validate_extension_bindings(
    profile: Mapping[str, Any],
    raw_bindings: object,
) -> tuple[ExtensionBindingRef, ...]:
    if not isinstance(raw_bindings, (list, tuple)) or len(raw_bindings) > 64:
        raise ArchitectureResolutionError(
            "ARCH_EXTENSION_BINDING_INVALID",
            "extensionBindings",
            "Extension bindings must be a bounded array",
        )
    slots = {
        str(slot["slot_id"]): slot
        for slot in profile["extension_slots"]
    }
    expected_keys = {
        "slotId",
        "slotVersion",
        "artifactId",
        "artifactDigest",
        "configurationDigest",
    }
    normalized: dict[str, ExtensionBindingRef] = {}
    for index, raw in enumerate(raw_bindings):
        if not isinstance(raw, Mapping) or set(raw) != expected_keys:
            raise ArchitectureResolutionError(
                "ARCH_EXTENSION_BINDING_INVALID",
                f"extensionBindings[{index}]",
                "Extension binding must contain only immutable references",
            )
        slot_id = str(raw["slotId"])
        slot = slots.get(slot_id)
        if (
            slot is None
            or str(raw["slotVersion"]) != str(slot["slot_version"])
            or slot_id in normalized
        ):
            raise ArchitectureResolutionError(
                "ARCH_EXTENSION_BINDING_INVALID",
                f"extensionBindings[{index}].slotId",
                "Extension binding does not match one unique profile slot",
            )
        artifact_id = str(raw["artifactId"])
        if not _valid_artifact_id(artifact_id):
            raise ArchitectureResolutionError(
                "ARCH_EXTENSION_BINDING_INVALID",
                f"extensionBindings[{index}].artifactId",
                "Artifact ID must be a UUID or stable semantic ID",
            )
        artifact_digest = str(raw["artifactDigest"])
        configuration_digest = str(raw["configurationDigest"])
        if (
            not _DIGEST.fullmatch(artifact_digest)
            or not _DIGEST.fullmatch(configuration_digest)
        ):
            raise ArchitectureResolutionError(
                "ARCH_EXTENSION_BINDING_INVALID",
                f"extensionBindings[{index}]",
                "Extension digests must be canonical SHA-256 references",
            )
        normalized[slot_id] = ExtensionBindingRef(
            slot_id=slot_id,
            slot_version=str(slot["slot_version"]),
            artifact_id=artifact_id,
            artifact_digest=artifact_digest,
            configuration_digest=configuration_digest,
            logical_component_id=str(slot["component_id"]),
            validation_contract_version=str(
                slot["configuration_contract_ref"]["version"]
            ),
        )
    if set(normalized) != set(slots):
        raise ArchitectureResolutionError(
            "ARCH_EXTENSION_BINDING_INVALID",
            "extensionBindings",
            "Extension bindings must cover every profile slot exactly once",
        )
    return tuple(normalized[slot_id] for slot_id in sorted(normalized))


def _valid_artifact_id(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return len(value) <= 160 and bool(_STABLE_ID.fullmatch(value))
