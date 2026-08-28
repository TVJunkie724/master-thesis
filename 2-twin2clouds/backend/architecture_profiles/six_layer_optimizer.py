"""Closed-world Six-layer Eventing v1 optimization orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from backend.deployment_specification.six_layer_builder import (
    build_six_layer_eventing_v1_deployment_specification,
)

from .diagnostics import ArchitectureResolutionError, RejectionCollector
from .registry import DEFINITIONS_ROOT, ArchitectureProfileRegistry
from .six_layer_costing import (
    SixLayerCostedCandidate,
    SixLayerCostEvaluation,
    evaluate_six_layer_costs,
    select_lowest_cost_six_layer_candidate,
)
from .six_layer_pricing import build_six_layer_catalog_cost_ledger_resolver
from .six_layer_strategy import (
    SixLayerEventingV1CandidateStrategy,
    SixLayerEventingV1ResolutionWinner,
)
from .six_layer_workload import (
    ResolvedSixLayerWorkload,
    resolve_six_layer_workload,
)
from .strategy import ArchitectureResolutionContext, build_resolution_context

SIX_LAYER_KEYS = (
    "L1",
    "L2",
    "L3_hot",
    "L3_cool",
    "L3_archive",
    "L4",
    "L5",
    "Eventing",
)
PROVIDER_LABELS = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
PROVIDER_REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
EVENTING_MANIFEST_PATH = DEFINITIONS_ROOT / "six-layer-eventing-v1-manifest.json"
EVENTING_MANIFEST_DIGEST = (
    "sha256:d705ce02f2b930b3735e415bb14bf13706952eaeb929d9b99c8ac1ee855585f1"
)
EVENTING_COST_REGISTRY_DIGEST = (
    "sha256:851af214c192826c2b5d0cd4250c552a7a23e1e40a6ca01a807fdf38c77d3972"
)
EVENTING_DECISION_DIGEST = (
    "sha256:b2afdaff2793391f0bab0127c93e13b0ff281964d1184818090781234444be35"
)
EVENTING_IMPLEMENTATION_DIGEST = (
    "sha256:bcc8fd9465243bd92028cf7c6cb970973096227048aeac98294f429b1f24252f"
)


CostLedgerResolver = Callable[
    [Mapping[str, Any], Mapping[str, str], ResolvedSixLayerWorkload],
    Mapping[str, Any],
]


@dataclass(frozen=True)
class SixLayerEventingV1OptimizationResult:
    resolved_architecture: Mapping[str, Any]
    deployment_specification: Mapping[str, Any]
    cost_evaluation: SixLayerCostEvaluation
    cost_ledger: Mapping[str, Any]
    selected_candidate_id: str
    selection_kind: Literal["cost_winner", "evaluation_candidate"]
    enumerated_candidate_count: int
    costed_candidate_count: int
    rejected_by_error_code: tuple[tuple[str, int], ...]

    @property
    def winning_candidate_id(self) -> str:
        """Expose winner terminology only for the normal cost-selected path."""

        if self.selection_kind != "cost_winner":
            raise RuntimeError("An evaluation candidate is not the cost winner")
        return self.selected_candidate_id


def _validate_eventing_decision_manifest(
    context: ArchitectureResolutionContext,
) -> None:
    try:
        manifest = json.loads(EVENTING_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
            "eventingDecision",
            "Six-layer Eventing decision evidence is unavailable",
        ) from exc
    expected_profile_ref = {
        "id": context.profile_ref.profile_id,
        "version": context.profile_ref.profile_version,
        "digest": context.profile_ref.content_digest,
    }
    expected_catalog_ref = {
        "id": context.catalog["catalog_id"],
        "version": context.catalog["catalog_version"],
        "digest": context.catalog["content_digest"],
    }
    if (
        manifest.get("manifest_version")
        != "six-layer-eventing-architecture-definitions.v1"
        or manifest.get("activation_status") != "active"
        or manifest.get("content_digest") != EVENTING_MANIFEST_DIGEST
        or manifest.get("profile_ref") != expected_profile_ref
        or manifest.get("catalog_ref") != expected_catalog_ref
        or (manifest.get("eventing_decision_ref") or {}).get("digest")
        != EVENTING_DECISION_DIGEST
        or (manifest.get("eventing_implementation_manifest_ref") or {}).get("digest")
        != EVENTING_IMPLEMENTATION_DIGEST
        or (manifest.get("topology_cost_registry_ref") or {}).get("digest")
        != EVENTING_COST_REGISTRY_DIGEST
    ):
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
            "eventingDecision",
            "Six-layer Eventing decision evidence or digest drifted",
        )


def optimize_six_layer_eventing_v1(
    *,
    calculation_run_id: str,
    architecture_profile: Mapping[str, Any],
    extension_bindings: object,
    workload: Mapping[str, Any],
    pricing_evidence_refs: Mapping[str, Mapping[str, str]],
    cost_ledger_resolver: CostLedgerResolver | None = None,
    pricing_by_provider: Mapping[str, Mapping[str, Any]] | None = None,
    providers: tuple[str, ...] = ("aws", "azure", "gcp"),
    resolution_status: str = "offline_contract_fixture",
    satisfied_live_gate_ids: frozenset[str] = frozenset(),
    azure_large_autoscale_ru_per_second: int | None = None,
    azure_large_autoscale_evidence_digest: str | None = None,
    registry: ArchitectureProfileRegistry | None = None,
    evaluation_candidate_id: str | None = None,
) -> SixLayerEventingV1OptimizationResult:
    """Resolve, cost, rank, and materialize one Six-layer architecture.

    ``evaluation_candidate_id`` is an internal research hook. It materializes
    one already enumerated and fully costed candidate for the supervised
    evaluation. The HTTP calculation path never binds this argument and
    therefore always returns the deterministic cost winner.
    """

    if (cost_ledger_resolver is None) == (pricing_by_provider is None):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "pricing",
            "Supply exactly one live catalog or explicit test-ledger resolver",
        )
    ledger_resolver = cost_ledger_resolver or (
        build_six_layer_catalog_cost_ledger_resolver(pricing_by_provider or {})
    )
    if (
        not providers
        or len(providers) != len(set(providers))
        or any(provider not in PROVIDER_LABELS for provider in providers)
    ):
        raise ArchitectureResolutionError(
            "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
            "providers",
            "Six-layer providers must be a unique supported subset",
        )
    if resolution_status not in {"offline_contract_fixture", "publishable"}:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "resolutionStatus",
            "Six-layer optimization status is unsupported",
        )
    profile_registry = registry or ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    context = build_resolution_context(
        registry=profile_registry,
        calculation_run_id=calculation_run_id,
        architecture_profile=architecture_profile,
        extension_bindings=extension_bindings,
        resolution_status=resolution_status,
    ).with_execution_inputs(
        layer_options={
            layer: tuple((PROVIDER_LABELS[provider], 0) for provider in providers)
            for layer in SIX_LAYER_KEYS
        },
        provider_regions=PROVIDER_REGIONS,
    )
    _validate_eventing_decision_manifest(context)
    resolved_workload = resolve_six_layer_workload(workload)
    strategy = SixLayerEventingV1CandidateStrategy(context.profile)
    strategy.validate_request(context)
    candidates = strategy.enumerate_candidates(context)
    rejections = RejectionCollector()
    costed_candidates = []
    specifications = {}
    cost_ledgers = {}
    resolved_architectures = {}
    for candidate in candidates:
        try:
            complete = strategy.validate_functional_completeness(candidate, context)
            assignment = {
                option.logical_component_id: option.provider
                for option in candidate.components
            }
            used_providers = set(assignment.values())
            selected_pricing_refs = {
                provider: pricing_evidence_refs[provider] for provider in used_providers
            }
            specification = build_six_layer_eventing_v1_deployment_specification(
                calculation_run_id=calculation_run_id,
                assignment=assignment,
                resolved_workload=resolved_workload,
                architecture_profile_ref={
                    "id": context.profile_ref.profile_id,
                    "version": context.profile_ref.profile_version,
                    "digest": context.profile_ref.content_digest,
                },
                component_catalog_ref={
                    "id": context.catalog["catalog_id"],
                    "version": context.catalog["catalog_version"],
                    "digest": context.catalog["content_digest"],
                },
                workload_contract_digest=context.profile["workload_contract_ref"][
                    "digest"
                ],
                pricing_evidence_digests={
                    provider: str(reference["digest"])
                    for provider, reference in selected_pricing_refs.items()
                },
                resolution_status=(
                    "deployment_ready"
                    if resolution_status == "publishable"
                    else "offline_contract_fixture"
                ),
                definition_lifecycle_statuses={
                    "profile": str(context.profile["lifecycle_status"]),
                    "catalog": str(context.catalog["lifecycle_status"]),
                    **{
                        f"provider:{provider}": str(
                            context.provider_profiles[provider]["lifecycle_status"]
                        )
                        for provider in used_providers
                    },
                },
                satisfied_live_gate_ids=satisfied_live_gate_ids,
                azure_large_autoscale_ru_per_second=azure_large_autoscale_ru_per_second,
                azure_large_autoscale_evidence_digest=azure_large_autoscale_evidence_digest,
            )
            ledger = ledger_resolver(specification, assignment, resolved_workload)
            evaluation = evaluate_six_layer_costs(
                specification=specification,
                assignment=assignment,
                resolved_workload=resolved_workload,
                cost_ledger=ledger,
            )
            costed = SixLayerCostedCandidate(
                candidate_id=candidate.candidate_id,
                canonical_assignment_key=tuple(sorted(assignment.items())),
                evaluation=evaluation,
            )
            resolved_architecture = strategy.build_resolution(
                SixLayerEventingV1ResolutionWinner(
                    candidate=complete,
                    costed_candidate=costed,
                    deployment_specification=specification,
                    pricing_evidence_refs=selected_pricing_refs,
                ),
                context,
            )
        except (ArchitectureResolutionError, KeyError) as exc:
            code = (
                exc.code
                if isinstance(exc, ArchitectureResolutionError)
                else "ARCH_PRICING_EVIDENCE_MISSING"
            )
            rejections.record(code, candidate.candidate_id)
            continue
        specifications[candidate.candidate_id] = specification
        cost_ledgers[candidate.candidate_id] = dict(ledger)
        resolved_architectures[candidate.candidate_id] = resolved_architecture
        costed_candidates.append(costed)
    if not costed_candidates:
        raise ArchitectureResolutionError(
            "ARCH_NO_ADMISSIBLE_CANDIDATE",
            "candidates",
            "No fully costed Six-layer candidate is available",
            enumerated_candidate_count=len(candidates),
            diagnostics=rejections.freeze(),
        )
    if evaluation_candidate_id is None:
        selected = select_lowest_cost_six_layer_candidate(tuple(costed_candidates))
        selection_kind = "cost_winner"
    else:
        selected = next(
            (
                candidate
                for candidate in costed_candidates
                if candidate.candidate_id == evaluation_candidate_id
            ),
            None,
        )
        if selected is None:
            raise ArchitectureResolutionError(
                "ARCH_NO_ADMISSIBLE_CANDIDATE",
                "evaluationCandidateId",
                "Requested evaluation candidate is not fully costed and admissible",
                enumerated_candidate_count=len(candidates),
                diagnostics=rejections.freeze(),
            )
        selection_kind = "evaluation_candidate"
    specification = specifications[selected.candidate_id]
    resolved_architecture = resolved_architectures[selected.candidate_id]
    frozen_rejections = rejections.freeze()
    return SixLayerEventingV1OptimizationResult(
        resolved_architecture=resolved_architecture,
        deployment_specification=specification,
        cost_evaluation=selected.evaluation,
        cost_ledger=cost_ledgers[selected.candidate_id],
        selected_candidate_id=selected.candidate_id,
        selection_kind=selection_kind,
        enumerated_candidate_count=len(candidates),
        costed_candidate_count=len(costed_candidates),
        rejected_by_error_code=frozen_rejections.rejected_by_error_code,
    )
