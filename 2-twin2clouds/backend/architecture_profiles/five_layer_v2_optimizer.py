"""Closed-world Five-layer v2 optimization orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from backend.deployment_specification.five_layer_v2_builder import (
    build_five_layer_v2_deployment_specification,
)

from .diagnostics import ArchitectureResolutionError, RejectionCollector
from .five_layer_strategy import build_default_strategy_registry
from .five_layer_v2_costing import (
    FiveLayerV2CostEvaluation,
    FiveLayerV2CostedCandidate,
    evaluate_five_layer_v2_costs,
    select_lowest_cost_five_layer_v2_candidate,
)
from .five_layer_v2_pricing import (
    build_five_layer_v2_catalog_cost_ledger_resolver,
)
from .five_layer_v2_strategy import FiveLayerV2ResolutionWinner
from .five_layer_v2_workload import (
    ResolvedFiveLayerV2Workload,
    resolve_five_layer_v2_workload,
)
from .registry import ArchitectureProfileRegistry
from .strategy import build_resolution_context


PROVIDER_LABELS = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
PROVIDER_REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
LAYER_KEYS = (
    "L1",
    "L2",
    "L3_hot",
    "L3_cool",
    "L3_archive",
    "L4",
    "L5",
)


CostLedgerResolver = Callable[
    [Mapping[str, Any], Mapping[str, str], ResolvedFiveLayerV2Workload],
    Mapping[str, Any],
]


@dataclass(frozen=True)
class FiveLayerV2OptimizationResult:
    resolved_architecture: Mapping[str, Any]
    deployment_specification: Mapping[str, Any]
    cost_evaluation: FiveLayerV2CostEvaluation
    cost_ledger: Mapping[str, Any]
    winning_candidate_id: str
    enumerated_candidate_count: int
    costed_candidate_count: int
    rejected_by_error_code: tuple[tuple[str, int], ...]


def optimize_five_layer_v2(
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
    registry: ArchitectureProfileRegistry | None = None,
) -> FiveLayerV2OptimizationResult:
    """Resolve, cost, rank, and materialize one v2 architecture."""

    if (cost_ledger_resolver is None) == (pricing_by_provider is None):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "pricing",
            "Supply exactly one live catalog or explicit test-ledger resolver",
        )
    ledger_resolver = cost_ledger_resolver or (
        build_five_layer_v2_catalog_cost_ledger_resolver(
            pricing_by_provider or {}
        )
    )

    if (
        not providers
        or len(providers) != len(set(providers))
        or any(provider not in PROVIDER_LABELS for provider in providers)
    ):
        raise ArchitectureResolutionError(
            "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
            "providers",
            "Five-layer v2 providers must be a unique supported subset",
        )
    if resolution_status not in {"offline_contract_fixture", "publishable"}:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "resolutionStatus",
            "Five-layer v2 optimization status is unsupported",
        )
    profile_registry = registry or ArchitectureProfileRegistry(profile_version="2")
    context = build_resolution_context(
        registry=profile_registry,
        calculation_run_id=calculation_run_id,
        architecture_profile=architecture_profile,
        extension_bindings=extension_bindings,
        resolution_status=resolution_status,
    ).with_execution_inputs(
        layer_options={
            layer: tuple((PROVIDER_LABELS[provider], 0) for provider in providers)
            for layer in LAYER_KEYS
        },
        provider_regions=PROVIDER_REGIONS,
    )
    resolved_workload = resolve_five_layer_v2_workload(workload)
    strategy = build_default_strategy_registry(context).resolve(context.profile)
    strategy.validate_request(context)
    candidates = strategy.enumerate_candidates(context)
    rejections = RejectionCollector()
    complete_candidates = {}
    costed_candidates = []
    specifications = {}
    cost_ledgers = {}
    for candidate in candidates:
        try:
            complete = strategy.validate_functional_completeness(candidate, context)
            assignment = {
                option.logical_component_id: option.provider
                for option in candidate.components
            }
            used_providers = set(assignment.values())
            selected_pricing_refs = {
                provider: pricing_evidence_refs[provider]
                for provider in used_providers
            }
            specification = build_five_layer_v2_deployment_specification(
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
                azure_large_autoscale_ru_per_second=(
                    azure_large_autoscale_ru_per_second
                ),
            )
            ledger = ledger_resolver(
                specification,
                assignment,
                resolved_workload,
            )
            evaluation = evaluate_five_layer_v2_costs(
                specification=specification,
                assignment=assignment,
                resolved_workload=resolved_workload,
                cost_ledger=ledger,
            )
            costed = FiveLayerV2CostedCandidate(
                candidate_id=candidate.candidate_id,
                canonical_assignment_key=tuple(
                    sorted(assignment.items())
                ),
                evaluation=evaluation,
            )
        except (ArchitectureResolutionError, KeyError) as exc:
            code = (
                exc.code
                if isinstance(exc, ArchitectureResolutionError)
                else "ARCH_PRICING_EVIDENCE_MISSING"
            )
            rejections.record(code, candidate.candidate_id)
            continue
        complete_candidates[candidate.candidate_id] = complete
        specifications[candidate.candidate_id] = specification
        cost_ledgers[candidate.candidate_id] = dict(ledger)
        costed_candidates.append(costed)
    winner = select_lowest_cost_five_layer_v2_candidate(
        tuple(costed_candidates)
    )
    complete_winner = complete_candidates[winner.candidate_id]
    specification = specifications[winner.candidate_id]
    used_providers = {
        option.provider for option in complete_winner.candidate.components
    }
    resolved_architecture = strategy.build_resolution(
        FiveLayerV2ResolutionWinner(
            candidate=complete_winner,
            costed_candidate=winner,
            deployment_specification=specification,
            pricing_evidence_refs={
                provider: pricing_evidence_refs[provider]
                for provider in used_providers
            },
        ),
        context,
    )
    frozen_rejections = rejections.freeze()
    return FiveLayerV2OptimizationResult(
        resolved_architecture=resolved_architecture,
        deployment_specification=specification,
        cost_evaluation=winner.evaluation,
        cost_ledger=cost_ledgers[winner.candidate_id],
        winning_candidate_id=winner.candidate_id,
        enumerated_candidate_count=len(candidates),
        costed_candidate_count=len(costed_candidates),
        rejected_by_error_code=frozen_rejections.rejected_by_error_code,
    )
