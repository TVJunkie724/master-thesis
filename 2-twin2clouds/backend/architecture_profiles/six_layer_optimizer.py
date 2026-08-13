"""Closed-world Six-layer Eventing v1 optimization orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Mapping

from backend.deployment_specification.five_layer_v2_builder import (
    build_six_layer_eventing_v1_deployment_specification,
)

from .diagnostics import ArchitectureResolutionError, RejectionCollector
from .five_layer_strategy import build_default_strategy_registry
from .five_layer_v2_costing import (
    FiveLayerV2CostEvaluation,
    FiveLayerV2CostedCandidate,
    evaluate_five_layer_v2_costs,
    select_lowest_cost_five_layer_v2_candidate,
)
from .five_layer_v2_optimizer import PROVIDER_LABELS, PROVIDER_REGIONS
from .five_layer_v2_pricing import build_five_layer_v2_catalog_cost_ledger_resolver
from .five_layer_v2_workload import (
    ResolvedFiveLayerV2Workload,
    resolve_five_layer_v2_workload,
)
from .registry import ArchitectureProfileRegistry, DEFINITIONS_ROOT
from .six_layer_strategy import SixLayerEventingV1ResolutionWinner
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
EVENTING_MANIFEST_PATH = DEFINITIONS_ROOT / "six-layer-eventing-v1-manifest.json"
EVENTING_MANIFEST_DIGEST = (
    "sha256:3e33d44545ba04938a27364492fdd1a9a82b2fc2f173f293ebdce5d904a1c6a9"
)
EVENTING_COST_REGISTRY_DIGEST = (
    "sha256:06c0a075f4db7944f4db5a43b4e58f7c5d9172220f0677ea514fc3a0ad5f3f1e"
)
EVENTING_DECISION_DIGEST = (
    "sha256:027ba4e220e3a211e632f7b462267ba46928de0a4dd949bcf5a6d37a59284e0b"
)
EVENTING_IMPLEMENTATION_DIGEST = (
    "sha256:f8ace7160f06c0282d84e16fbd474d8744ac12bd14b2fea14cf47f36ce8b67f3"
)


CostLedgerResolver = Callable[
    [Mapping[str, Any], Mapping[str, str], ResolvedFiveLayerV2Workload],
    Mapping[str, Any],
]


@dataclass(frozen=True)
class SixLayerEventingV1OptimizationResult:
    resolved_architecture: Mapping[str, Any]
    deployment_specification: Mapping[str, Any]
    cost_evaluation: FiveLayerV2CostEvaluation
    cost_ledger: Mapping[str, Any]
    winning_candidate_id: str
    enumerated_candidate_count: int
    costed_candidate_count: int
    rejected_by_error_code: tuple[tuple[str, int], ...]


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
        or (manifest.get("eventing_implementation_manifest_ref") or {}).get(
            "digest"
        )
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
) -> SixLayerEventingV1OptimizationResult:
    """Resolve, cost, rank, and materialize one Six-layer architecture."""

    if (cost_ledger_resolver is None) == (pricing_by_provider is None):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "pricing",
            "Supply exactly one live catalog or explicit test-ledger resolver",
        )
    ledger_resolver = cost_ledger_resolver or (
        build_five_layer_v2_catalog_cost_ledger_resolver(pricing_by_provider or {})
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
            evaluation = evaluate_five_layer_v2_costs(
                specification=specification,
                assignment=assignment,
                resolved_workload=resolved_workload,
                cost_ledger=ledger,
            )
            costed = FiveLayerV2CostedCandidate(
                candidate_id=candidate.candidate_id,
                canonical_assignment_key=tuple(sorted(assignment.items())),
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
    if not costed_candidates:
        raise ArchitectureResolutionError(
            "ARCH_NO_ADMISSIBLE_CANDIDATE",
            "candidates",
            "No fully costed Six-layer candidate is available",
            enumerated_candidate_count=len(candidates),
            diagnostics=rejections.freeze(),
        )
    winner = select_lowest_cost_five_layer_v2_candidate(tuple(costed_candidates))
    complete_winner = complete_candidates[winner.candidate_id]
    specification = specifications[winner.candidate_id]
    used_providers = {
        option.provider for option in complete_winner.candidate.components
    }
    resolved_architecture = strategy.build_resolution(
        SixLayerEventingV1ResolutionWinner(
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
    return SixLayerEventingV1OptimizationResult(
        resolved_architecture=resolved_architecture,
        deployment_specification=specification,
        cost_evaluation=winner.evaluation,
        cost_ledger=cost_ledgers[winner.candidate_id],
        winning_candidate_id=winner.candidate_id,
        enumerated_candidate_count=len(candidates),
        costed_candidate_count=len(costed_candidates),
        rejected_by_error_code=frozen_rejections.rejected_by_error_code,
    )
