"""Five-layer v2 candidate and topology strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
from .five_layer_v2_costing import (
    FiveLayerV2CostEvaluation,
    FiveLayerV2CostedCandidate,
)
from .five_layer_v2_resolution_builder import FiveLayerV2ResolutionBuilder
from .strategy import (
    ArchitectureProfileRef,
    ArchitectureResolutionContext,
    OptimizationBundleRef,
)


FIVE_LAYER_V2_PROFILE_REF = ArchitectureProfileRef(
    profile_id="five-layer-baseline",
    profile_version="2",
    content_digest=(
        "sha256:8ebe9f14978f632c04a25837af1a4b9e4ee4da863f4a972189fb75cd174cac5c"
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


@dataclass(frozen=True)
class FiveLayerV2ResolutionWinner:
    candidate: CompleteArchitectureCandidate
    costed_candidate: FiveLayerV2CostedCandidate
    deployment_specification: Mapping[str, Any]
    pricing_evidence_refs: Mapping[str, Mapping[str, str]]


class FiveLayerV2CandidateStrategy:
    """Resolve all functionally complete v2 placements before cost ranking."""

    strategy_id = "five-layer-complete-path.v2"
    supported_profile_refs = frozenset({FIVE_LAYER_V2_PROFILE_REF})

    def __init__(self, profile: Mapping[str, Any]):
        if (
            ArchitectureProfileRef.from_profile(profile) != FIVE_LAYER_V2_PROFILE_REF
            or OptimizationBundleRef.from_profile(profile) != FIVE_LAYER_V2_BUNDLE_REF
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
        candidate: FiveLayerV2CostedCandidate,
        context: ArchitectureResolutionContext,
    ) -> FiveLayerV2CostedCandidate:
        if not isinstance(candidate.evaluation, FiveLayerV2CostEvaluation):
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
        if not isinstance(winner, FiveLayerV2ResolutionWinner):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "winner",
                "Five-layer v2 winner evidence is incomplete",
            )
        if winner.candidate.candidate_id != winner.costed_candidate.candidate_id:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "winner",
                "Five-layer v2 topology and cost winners differ",
            )
        return FiveLayerV2ResolutionBuilder().build(
            candidate=winner.candidate,
            context=context,
            deployment_specification=winner.deployment_specification,
            cost_evaluation=winner.costed_candidate.evaluation,
            pricing_evidence_refs=winner.pricing_evidence_refs,
        )
