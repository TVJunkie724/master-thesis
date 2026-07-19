"""Five-layer architecture strategy backed by the existing path optimizer."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from backend.calculation_v2.path_optimizer import CompletePathEvaluation

from .candidate_factory import (
    ArchitectureCandidate,
    BASELINE_LAYER_COMPONENTS,
    enumerate_component_candidates,
)
from .completeness import (
    CompleteArchitectureCandidate,
    ResolvedEdgeOption,
    resolve_candidate_edges,
    validate_candidate_completeness,
)
from .diagnostics import ArchitectureResolutionError
from .resolution_builder import ResolvedTwinArchitectureBuilder
from .strategy import (
    ArchitectureProfileRef,
    ArchitectureResolutionContext,
    ArchitectureStrategyRegistry,
)


class FiveLayerCompletePathStrategy:
    """Adapt the current seven-slot kernel to the architecture contracts."""

    strategy_id = "five-layer-complete-path.v1"

    def __init__(self, profile: Mapping[str, Any]):
        self.supported_profile_refs = frozenset(
            {ArchitectureProfileRef.from_profile(profile)}
        )

    def validate_request(self, context: ArchitectureResolutionContext) -> None:
        if context.profile_ref not in self.supported_profile_refs:
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "architectureProfile",
                "The five-layer strategy does not support this profile",
            )
        if context.catalog["lifecycle_status"] != "active":
            raise ArchitectureResolutionError(
                "ARCH_COMPONENT_CANDIDATE_MISSING",
                "componentCatalog",
                "The compatible component catalog is not active",
            )
        expected_slots = tuple(
            slot_id for _, slot_id, _ in BASELINE_LAYER_COMPONENTS
        )
        if tuple(context.profile["optimization_slot_ids"]) != expected_slots:
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "optimizationSlots",
                "The selected profile differs from the seven-slot baseline",
            )
        if not any(
            profile["lifecycle_status"] == "active"
            and profile["supported"] is True
            for profile in context.provider_profiles.values()
        ):
            raise ArchitectureResolutionError(
                "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
                "providerProfiles",
                "No active supported provider profile is available",
            )

    def enumerate_candidates(
        self,
        context: ArchitectureResolutionContext,
    ) -> tuple[ArchitectureCandidate, ...]:
        return enumerate_component_candidates(context)

    def validate_functional_completeness(
        self,
        candidate: ArchitectureCandidate,
        context: ArchitectureResolutionContext,
    ) -> CompleteArchitectureCandidate:
        return validate_candidate_completeness(candidate, context)

    def calculate_candidate(
        self,
        candidate: CompletePathEvaluation,
        context: ArchitectureResolutionContext,
    ) -> CompletePathEvaluation:
        if (
            not isinstance(candidate.total_cost, Decimal)
            or not candidate.total_cost.is_finite()
            or candidate.total_cost < 0
        ):
            raise ArchitectureResolutionError(
                "ARCH_NO_ADMISSIBLE_CANDIDATE",
                candidate.candidate_id,
                "Path optimizer returned an invalid candidate cost",
            )
        return candidate

    def resolve_edges(
        self,
        candidate: ArchitectureCandidate,
        context: ArchitectureResolutionContext,
    ) -> tuple[ResolvedEdgeOption, ...]:
        return resolve_candidate_edges(candidate, context)

    def build_resolution(
        self,
        winner: Any,
        context: ArchitectureResolutionContext,
    ) -> Mapping[str, Any]:
        return ResolvedTwinArchitectureBuilder().build(
            winner=winner,
            context=context,
        )


def build_default_strategy_registry(
    context: ArchitectureResolutionContext,
) -> ArchitectureStrategyRegistry:
    registry = ArchitectureStrategyRegistry()
    registry.register(
        context.profile,
        FiveLayerCompletePathStrategy(context.profile),
    )
    registry.freeze()
    return registry
