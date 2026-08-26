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
    OptimizationBundleRef,
)

FIVE_LAYER_PROFILE_REF = ArchitectureProfileRef(
    profile_id="five-layer-baseline",
    profile_version="1",
    content_digest=(
        "sha256:dcac9d4c519c7624b74ba6f9e5b878b17553c828b6d6d8583754c34c6a2e4807"
    ),
)
FIVE_LAYER_BUNDLE_REF = OptimizationBundleRef(
    optimization_strategy_id="cost_minimization_v1",
    optimization_strategy_version="1",
    calculation_strategy_id="cost_calculation_v2",
    calculation_strategy_version="2",
    formula_set_id="cost_formula_set_v1",
    formula_set_version="1",
    scoring_strategy_id="min_total_cost_v1",
    scoring_strategy_version="1",
    compatibility_digest=(
        "sha256:0f53f6a7ed48dd7a7765b52479dfd428a58f448d4f11d477ff9adb8439d63499"
    ),
)


class FiveLayerCompletePathStrategy:
    """Adapt the current seven-slot kernel to the architecture contracts."""

    strategy_id = "five-layer-complete-path.v1"

    def __init__(self, profile: Mapping[str, Any]):
        if (
            ArchitectureProfileRef.from_profile(profile) != FIVE_LAYER_PROFILE_REF
            or OptimizationBundleRef.from_profile(profile) != FIVE_LAYER_BUNDLE_REF
        ):
            raise RuntimeError(
                "Five-layer strategy profile or optimization bundle drifted"
            )
        self.supported_profile_refs = frozenset({FIVE_LAYER_PROFILE_REF})

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
        expected_slots = tuple(slot_id for _, slot_id, _ in BASELINE_LAYER_COMPONENTS)
        if tuple(context.profile["optimization_slot_ids"]) != expected_slots:
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "optimizationSlots",
                "The selected profile differs from the seven-slot baseline",
            )
        if not any(
            profile["lifecycle_status"] == "active" and profile["supported"] is True
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
    return _build_strategy_registry(context.profile)


def validate_architecture_strategy_readiness(
    registry=None,
) -> ArchitectureStrategyRegistry:
    """Load and resolve the exact reviewed strategy during API startup."""

    if registry is None:
        from .registry import ArchitectureProfileRegistry

        registry = ArchitectureProfileRegistry()
    return _build_strategy_registry(registry.profile)


def _build_strategy_registry(
    profile: Mapping[str, Any],
) -> ArchitectureStrategyRegistry:
    profile_ref = (
        str(profile.get("profile_id")),
        str(profile.get("profile_version")),
    )
    if profile_ref == ("six-layer-eventing", "1"):
        from .six_layer_strategy import SixLayerEventingV1CandidateStrategy

        strategy = SixLayerEventingV1CandidateStrategy(profile)
    else:
        strategy = FiveLayerCompletePathStrategy(profile)
    registry = ArchitectureStrategyRegistry()
    registry.register(
        profile,
        strategy,
    )
    registry.freeze()
    registry.resolve(profile)
    return registry
