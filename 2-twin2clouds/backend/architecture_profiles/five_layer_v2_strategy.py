"""Draft-safe Five-layer v2 candidate and topology strategy."""

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
from .strategy import (
    ArchitectureProfileRef,
    ArchitectureResolutionContext,
    OptimizationBundleRef,
)


FIVE_LAYER_V2_PROFILE_REF = ArchitectureProfileRef(
    profile_id="five-layer-baseline",
    profile_version="2",
    content_digest=(
        "sha256:0d7f87bda7703bd71ac16081f96ecab1a8777d6aa49bc52cb94c83906a11b16a"
    ),
)
FIVE_LAYER_V2_BUNDLE_REF = OptimizationBundleRef(
    optimization_strategy_id="cost-minimization-v2",
    optimization_strategy_version="2",
    calculation_strategy_id="profile-resolution-v2",
    calculation_strategy_version="2",
    formula_set_id="phase-08-complete-service-bundles",
    formula_set_version="1",
    scoring_strategy_id="profile-local-min-total-cost-v2",
    scoring_strategy_version="2",
    compatibility_digest=(
        "sha256:a0c39dcae6c95c2cb25251389c6569a0f5ea4428a0403ccc4cf934541cda06f1"
    ),
)


class FiveLayerV2CandidateStrategy:
    """Resolve all functionally complete v2 placements before cost ranking."""

    strategy_id = "five-layer-complete-path.v2"
    supported_profile_refs = frozenset({FIVE_LAYER_V2_PROFILE_REF})

    def __init__(self, profile: Mapping[str, Any]):
        if (
            ArchitectureProfileRef.from_profile(profile)
            != FIVE_LAYER_V2_PROFILE_REF
            or OptimizationBundleRef.from_profile(profile)
            != FIVE_LAYER_V2_BUNDLE_REF
        ):
            raise RuntimeError(
                "Five-layer v2 strategy profile or optimization bundle drifted"
            )

    def validate_request(self, context: ArchitectureResolutionContext) -> None:
        if context.profile_ref not in self.supported_profile_refs:
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "architectureProfile",
                "The Five-layer v2 strategy does not support this profile",
            )
        if context.resolution_status == "publishable":
            statuses = {
                context.profile["lifecycle_status"],
                context.catalog["lifecycle_status"],
                *(
                    profile["lifecycle_status"]
                    for profile in context.provider_profiles.values()
                ),
            }
            if statuses != {"active"}:
                raise ArchitectureResolutionError(
                    "ARCH_PROFILE_NOT_FOUND",
                    "architectureProfile",
                    "Five-layer v2 is not active",
                )
        if tuple(context.profile["optimization_slot_ids"]) != tuple(
            slot_id for _, slot_id, _ in BASELINE_LAYER_COMPONENTS
        ):
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "optimizationSlots",
                "Five-layer v2 requires the reviewed seven-slot model",
            )
        edge_ids = {str(edge["edge_id"]) for edge in context.profile["edges"]}
        if (
            "edge.hot-storage-to-visualization" not in edge_ids
            or "edge.hot-storage-to-twin-state" not in edge_ids
            or "edge.twin-state-to-visualization" in edge_ids
        ):
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "edges",
                "Five-layer v2 requires raw-history and Twin-projection edges without L4-to-L5",
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
                "Path optimizer returned an invalid v2 candidate cost",
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
        raise ArchitectureResolutionError(
            "ARCH_RESOLUTION_BUILD_FAILED",
            "resolvedTwinArchitecture",
            "Five-layer v2 cost and deployment resolution is not active yet",
        )
