"""Six-layer Eventing v1 candidate and topology strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .candidate_factory import (
    ArchitectureCandidate,
    SIX_LAYER_COMPONENTS,
    enumerate_component_candidates,
)
from .completeness import (
    CompleteArchitectureCandidate,
    ResolvedEdgeOption,
    resolve_candidate_edges,
    validate_candidate_completeness,
)
from .diagnostics import ArchitectureResolutionError
from .five_layer_v2_costing import FiveLayerV2CostEvaluation, FiveLayerV2CostedCandidate
from .five_layer_v2_resolution_builder import FiveLayerV2ResolutionBuilder
from .strategy import (
    ArchitectureProfileRef,
    ArchitectureResolutionContext,
    OptimizationBundleRef,
)


SIX_LAYER_EVENTING_V1_PROFILE_REF = ArchitectureProfileRef(
    profile_id="six-layer-eventing",
    profile_version="1",
    content_digest="sha256:99bb981aa1a60a5e4677609914bc9e341774ef500222da72c4f82efe6f0756c9",
)
SIX_LAYER_EVENTING_V1_BUNDLE_REF = OptimizationBundleRef(
    optimization_strategy_id="cost-minimization-v2",
    optimization_strategy_version="2",
    calculation_strategy_id="profile-resolution-v2",
    calculation_strategy_version="2",
    formula_set_id="phase-08-complete-service-bundles",
    formula_set_version="1",
    scoring_strategy_id="profile-local-min-total-cost-v2",
    scoring_strategy_version="2",
    compatibility_digest="sha256:a0c39dcae6c95c2cb25251389c6569a0f5ea4428a0403ccc4cf934541cda06f1",
)
EVENT_EDGE_IDS = {
    "edge.ingestion-to-eventing",
    "edge.eventing-to-processing",
    "edge.processing-to-eventing",
    "edge.eventing-to-ingestion",
    "edge.eventing-to-hot-storage",
}


@dataclass(frozen=True)
class SixLayerEventingV1ResolutionWinner:
    candidate: CompleteArchitectureCandidate
    costed_candidate: FiveLayerV2CostedCandidate
    deployment_specification: Mapping[str, Any]
    pricing_evidence_refs: Mapping[str, Mapping[str, str]]


class SixLayerEventingV1CandidateStrategy:
    """Resolve only complete Event-Layer placements before profile-local ranking."""

    strategy_id = "six-layer-eventing-complete-path.v1"
    supported_profile_refs = frozenset({SIX_LAYER_EVENTING_V1_PROFILE_REF})

    def __init__(self, profile: Mapping[str, Any]):
        if (
            ArchitectureProfileRef.from_profile(profile)
            != SIX_LAYER_EVENTING_V1_PROFILE_REF
            or OptimizationBundleRef.from_profile(profile)
            != SIX_LAYER_EVENTING_V1_BUNDLE_REF
        ):
            raise RuntimeError(
                "Six-layer Eventing profile or optimization bundle drifted"
            )

    def validate_request(self, context: ArchitectureResolutionContext) -> None:
        if context.profile_ref not in self.supported_profile_refs:
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "architectureProfile",
                "The Six-layer Eventing strategy does not support this profile",
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
                    "Six-layer Eventing v1 is not active",
                )
        if tuple(context.profile["optimization_slot_ids"]) != tuple(
            slot_id for _, slot_id, _ in SIX_LAYER_COMPONENTS
        ):
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "optimizationSlots",
                "Six-layer Eventing requires the reviewed eight-slot model",
            )
        edge_ids = {str(edge["edge_id"]) for edge in context.profile["edges"]}
        if (
            not EVENT_EDGE_IDS.issubset(edge_ids)
            or {
                "edge.ingestion-to-processing",
                "edge.processing-to-ingestion",
                "edge.ingestion-to-hot-storage",
                "edge.processing-to-hot-storage",
            }
            & edge_ids
        ):
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "edges",
                "Six-layer Eventing must mediate the reviewed ingestion/processing event edges",
            )

    def enumerate_candidates(
        self, context: ArchitectureResolutionContext
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
                "Path optimizer returned an invalid Six-layer candidate cost",
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
        if not isinstance(winner, SixLayerEventingV1ResolutionWinner):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "winner",
                "Six-layer Eventing winner evidence is incomplete",
            )
        if winner.candidate.candidate_id != winner.costed_candidate.candidate_id:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "winner",
                "Six-layer topology and cost winners differ",
            )
        return FiveLayerV2ResolutionBuilder(
            expected_profile_id="six-layer-eventing",
            expected_profile_version="1",
            profile_label="Six-layer Eventing v1",
        ).build(
            candidate=winner.candidate,
            context=context,
            deployment_specification=winner.deployment_specification,
            cost_evaluation=winner.costed_candidate.evaluation,
            pricing_evidence_refs=winner.pricing_evidence_refs,
        )
