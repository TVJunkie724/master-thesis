"""Exact-once atomic cost ownership and ranking inputs for Five-layer v2."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .diagnostics import ArchitectureResolutionError
from .five_layer_v2_workload import ResolvedFiveLayerV2Workload


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v2"
)
FORMULA_REF = "formula.phase-08-complete-service-bundles"
SIX_LAYER_TOPOLOGY_COST_REGISTRY_DIGEST = (
    "sha256:851af214c192826c2b5d0cd4250c552a7a23e1e40a6ca01a807fdf38c77d3972"
)
SIX_LAYER_EVENT_COMPONENT_IDS = frozenset(
    {
        "aws.kinesis-data-streams",
        "aws.sns-fifo",
        "aws.sqs-fifo",
        "aws.lambda-event-worker",
        "aws.s3-event-failure-store",
        "aws.cloudwatch",
        "aws.kinesis-only-for-reviewed-remote-telemetry-edge",
        "aws.sns-fifo-only-for-reviewed-remote-control-edge",
        "aws.lambda-event-adapter",
        "azure.event-hubs-standard-small-medium",
        "azure.event-hubs-dedicated-large",
        "azure.service-bus-standard",
        "azure.functions-flex-event-worker",
        "azure.monitor",
        "azure.log-analytics-shared-workspace",
        "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
        "azure.functions-flex-event-adapter",
        "gcp.pubsub-separated-event-layer-topics",
        "gcp.cloud-run-event-service-small-medium",
        "gcp.cloud-run-worker-pool-fixed-large",
        "gcp.cloud-logging",
        "gcp.cloud-monitoring",
        "gcp.pubsub-separated-embedded-topics",
        "gcp.cloud-run-event-adapter",
    }
)
PROFILE_EDGE_IDS = (
    "edge.cool-to-archive-storage",
    "edge.hot-storage-to-twin-state",
    "edge.hot-to-cool-storage",
    "edge.ingestion-to-hot-storage",
    "edge.ingestion-to-processing",
    "edge.processing-to-hot-storage",
    "edge.processing-to-ingestion",
    "edge.hot-storage-to-visualization",
)
SIX_LAYER_EDGE_IDS = (
    "edge.cool-to-archive-storage",
    "edge.hot-storage-to-twin-state",
    "edge.hot-to-cool-storage",
    "edge.hot-storage-to-visualization",
    "edge.ingestion-to-eventing",
    "edge.eventing-to-processing",
    "edge.processing-to-eventing",
    "edge.eventing-to-ingestion",
    "edge.eventing-to-hot-storage",
)
DOMAIN_EVENT_FLOWS = (
    ("telemetry.received.v1", "component.ingestion", "component.processing"),
    (
        "telemetry.processed.v1:historical-persistence",
        "component.processing",
        "component.hot-storage",
    ),
    (
        "telemetry.processed.v1:twin-state-update",
        "component.processing",
        "component.twin-state",
    ),
    ("event.matched.v1", "component.processing", "component.processing"),
    ("notification.requested.v1", "component.processing", "component.processing"),
    ("device.command.requested.v1", "component.processing", "component.ingestion"),
    ("extension.action.outcome.v1", "component.processing", "component.hot-storage"),
    ("notification.workflow.outcome.v1", "component.processing", "component.hot-storage"),
    ("device.command.outcome.v1", "component.ingestion", "component.hot-storage"),
)
SIX_LAYER_EVENT_FLOWS = (
    (
        "edge.ingestion-to-eventing",
        "component.ingestion",
        "component.eventing",
        ("telemetry.received.v1", "device.command.outcome.v1"),
    ),
    (
        "edge.eventing-to-processing",
        "component.eventing",
        "component.processing",
        (
            "telemetry.received.v1",
            "telemetry.processed.v1",
            "event.matched.v1",
            "notification.requested.v1",
        ),
    ),
    (
        "edge.processing-to-eventing",
        "component.processing",
        "component.eventing",
        (
            "telemetry.processed.v1",
            "event.matched.v1",
            "notification.requested.v1",
            "device.command.requested.v1",
            "extension.action.outcome.v1",
            "notification.workflow.outcome.v1",
        ),
    ),
    (
        "edge.eventing-to-ingestion",
        "component.eventing",
        "component.ingestion",
        ("device.command.requested.v1",),
    ),
    (
        "edge.eventing-to-hot-storage",
        "component.eventing",
        "component.hot-storage",
        (
            "telemetry.processed.v1",
            "extension.action.outcome.v1",
            "notification.workflow.outcome.v1",
            "device.command.outcome.v1",
        ),
    ),
)


@dataclass(frozen=True)
class ExpectedRouteOwner:
    cost_owner_id: str
    route_class: str
    pair: str
    source_provider: str
    destination_provider: str
    allocation_item_ids: tuple[str, ...]
    domain_flow_ids: tuple[str, ...]
    workload_digest: str


@dataclass(frozen=True)
class FiveLayerV2CostEvaluation:
    currency: str
    component_totals: Mapping[str, Decimal]
    edge_totals: Mapping[str, Decimal]
    component_owner_totals: Mapping[str, Decimal]
    route_owner_totals: Mapping[str, Decimal]
    monthly_total: Decimal


@dataclass(frozen=True)
class FiveLayerV2CostedCandidate:
    candidate_id: str
    canonical_assignment_key: tuple[tuple[str, str], ...]
    evaluation: FiveLayerV2CostEvaluation


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Five-layer v2 cost registry is unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Five-layer v2 cost registry must be an object: {path}")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    registry = _read(CONTRACT_ROOT / "component-capacity-registry.json")
    supplied = registry["content_digest"]
    registry["content_digest"] = ""
    if supplied != _digest(registry):
        raise RuntimeError("Five-layer v2 cost registry digest drifted")
    registry["content_digest"] = supplied
    return registry


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING", field, "Cost must be a decimal string"
        )
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING", field, "Cost must be a decimal string"
        ) from exc
    if not result.is_finite() or result < 0:
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            field,
            "Cost must be finite and non-negative",
        )
    return result


def _pricing_evidence(specification: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(item["provider"]): str(item["digest"])
        for item in specification["optimization_context"]["pricing_evidence_refs"]
    }


def _selection_digest(selection: Mapping[str, Any]) -> str:
    return _digest(
        {
            "implementation_component_id": selection[
                "implementation_component_id"
            ],
            "implementation_component_digest": selection[
                "implementation_component_digest"
            ],
            "provider": selection["provider"],
            "dimensions": selection["dimensions"],
        }
    )


def expected_route_owners(
    assignment: Mapping[str, str],
    resolved_workload: ResolvedFiveLayerV2Workload,
) -> tuple[ExpectedRouteOwner, ...]:
    """Derive only cross-provider route owners; local operations stay in components."""

    route_index = {
        (item["route_class"], item["pair"]): item
        for item in _registry()["route_owners"]
    }
    expected: list[ExpectedRouteOwner] = []

    def add(
        route_class: str,
        source: str,
        destination: str,
        allocation_item_ids: tuple[str, ...],
        domain_flow_ids: tuple[str, ...] = (),
    ) -> None:
        if source == destination:
            return
        pair = f"{source}->{destination}"
        owner = route_index.get((route_class, pair))
        if owner is None:
            raise ArchitectureResolutionError(
                "ARCH_PRICING_EVIDENCE_MISSING",
                pair,
                "Cross-provider route has no pricing owner",
            )
        workload_digest = _digest(
            {
                "route_class": route_class,
                "pair": pair,
                "allocation_item_ids": allocation_item_ids,
                "domain_flow_ids": domain_flow_ids,
                "core_size": resolved_workload.size,
                "workload": dict(resolved_workload.workload),
                "eventing_scenario_ref": dict(
                    resolved_workload.eventing_scenario_ref
                ),
            }
        )
        expected.append(
            ExpectedRouteOwner(
                cost_owner_id=str(owner["cost_owner_id"]),
                route_class=route_class,
                pair=pair,
                source_provider=source,
                destination_provider=destination,
                allocation_item_ids=allocation_item_ids,
                domain_flow_ids=domain_flow_ids,
                workload_digest=workload_digest,
            )
        )

    grouped_domain_sources: dict[tuple[str, str], set[str]] = {}
    grouped_domain_flows: dict[tuple[str, str], list[str]] = {}
    uses_event_layer = "component.eventing" in assignment
    if uses_event_layer:
        for edge_id, source_component, destination_component, flow_ids in SIX_LAYER_EVENT_FLOWS:
            source = assignment[source_component]
            destination = assignment[destination_component]
            if source != destination:
                grouped_domain_sources.setdefault((source, destination), set()).add(
                    edge_id
                )
                grouped_domain_flows.setdefault((source, destination), []).extend(
                    flow_ids
                )
    else:
        for flow_id, source_component, destination_component in DOMAIN_EVENT_FLOWS:
            source = assignment[source_component]
            destination = assignment[destination_component]
            if source != destination:
                grouped_domain_sources.setdefault((source, destination), set()).add(
                    source_component
                )
                grouped_domain_flows.setdefault((source, destination), []).append(
                    flow_id
                )
    for (source, destination), source_components in sorted(
        grouped_domain_sources.items()
    ):
        add(
            "domain_event_cross_cloud",
            source,
            destination,
            tuple(sorted(source_components)),
            tuple(sorted(set(grouped_domain_flows[(source, destination)])))
            if uses_event_layer
            else tuple(grouped_domain_flows[(source, destination)]),
        )
    add(
        "twin_projection_cross_cloud",
        assignment["component.hot-storage"],
        assignment["component.twin-state"],
        ("edge.hot-storage-to-twin-state",),
    )
    add(
        "storage_hot_to_cool_cross_cloud",
        assignment["component.hot-storage"],
        assignment["component.cool-storage"],
        ("edge.hot-to-cool-storage",),
    )
    add(
        "storage_cool_to_archive_cross_cloud",
        assignment["component.cool-storage"],
        assignment["component.archive-storage"],
        ("edge.cool-to-archive-storage",),
    )
    identities = [owner.cost_owner_id for owner in expected]
    if len(identities) != len(set(identities)):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "routes",
            "A route pricing owner would be counted more than once",
        )
    return tuple(sorted(expected, key=lambda item: item.cost_owner_id))


def evaluate_five_layer_v2_costs(
    *,
    specification: Mapping[str, Any],
    assignment: Mapping[str, str],
    resolved_workload: ResolvedFiveLayerV2Workload,
    cost_ledger: Mapping[str, Any],
) -> FiveLayerV2CostEvaluation:
    """Validate an exact formula-result ledger and aggregate every owner once."""

    if cost_ledger.get("schema_version") != "five-layer-v2-cost-ledger.v1":
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "costLedger",
            "Five-layer v2 cost ledger version is unsupported",
        )
    currency = str(cost_ledger.get("currency", ""))
    if currency != specification["currency"] or currency not in {"USD", "EUR"}:
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "costLedger.currency",
            "Cost ledger currency differs from the deployment specification",
        )
    pricing_evidence = _pricing_evidence(specification)
    registry_components = {
        item["component_id"]: item for item in _registry()["components"]
    }
    expected_components = {
        str(selection["implementation_component_id"]): selection
        for selection in specification["component_selections"]
    }
    component_quotes = cost_ledger.get("component_costs")
    if not isinstance(component_quotes, list):
        component_quotes = []
    supplied_component_ids = [
        str(item.get("component_id", ""))
        for item in component_quotes
        if isinstance(item, Mapping)
    ]
    if (
        len(supplied_component_ids) != len(set(supplied_component_ids))
        or set(supplied_component_ids) != set(expected_components)
    ):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "costLedger.componentCosts",
            "Component cost ledger must cover every selected owner exactly once",
        )
    component_totals = {
        logical: Decimal(0) for logical in assignment
    }
    component_owner_totals: dict[str, Decimal] = {}
    uses_event_layer = "component.eventing" in assignment
    for quote in component_quotes:
        component_id = str(quote["component_id"])
        selection = expected_components[component_id]
        registry_component = registry_components[component_id]
        if (
            quote.get("cost_owner_id")
            != registry_component["pricing_owner_id"]
            or quote.get("selection_digest") != _selection_digest(selection)
            or quote.get("formula_reference") != FORMULA_REF
            or quote.get("pricing_evidence_digest")
            != pricing_evidence[selection["provider"]]
            or (
                uses_event_layer
                and component_id in SIX_LAYER_EVENT_COMPONENT_IDS
                and quote.get("topology_cost_registry_digest")
                != SIX_LAYER_TOPOLOGY_COST_REGISTRY_DIGEST
            )
        ):
            raise ArchitectureResolutionError(
                "ARCH_PRICING_EVIDENCE_MISSING",
                component_id,
                "Component price result is not bound to the exact selection and evidence",
            )
        amount = _decimal(quote.get("monthly_amount"), component_id)
        owner_id = str(quote["cost_owner_id"])
        if owner_id in component_owner_totals:
            raise ArchitectureResolutionError(
                "ARCH_PRICING_EVIDENCE_MISSING",
                owner_id,
                "Component pricing owner is duplicated",
            )
        component_owner_totals[owner_id] = amount
        component_totals[str(selection["logical_component_id"])] += amount

    expected_routes = {
        item.cost_owner_id: item
        for item in expected_route_owners(assignment, resolved_workload)
    }
    route_quotes = cost_ledger.get("route_costs")
    if not isinstance(route_quotes, list):
        route_quotes = []
    supplied_route_ids = [
        str(item.get("cost_owner_id", ""))
        for item in route_quotes
        if isinstance(item, Mapping)
    ]
    if (
        len(supplied_route_ids) != len(set(supplied_route_ids))
        or set(supplied_route_ids) != set(expected_routes)
    ):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "costLedger.routeCosts",
            "Route cost ledger must cover every selected cross-provider owner exactly once",
        )
    edge_totals = {
        edge_id: Decimal(0)
        for edge_id in (
            SIX_LAYER_EDGE_IDS
            if "component.eventing" in assignment
            else PROFILE_EDGE_IDS
        )
    }
    route_owner_totals: dict[str, Decimal] = {}
    for quote in route_quotes:
        owner_id = str(quote["cost_owner_id"])
        expected = expected_routes[owner_id]
        raw_allocations = quote.get("allocations")
        if not isinstance(raw_allocations, list):
            raw_allocations = []
        allocation_ids = [
            str(item.get("item_id", ""))
            for item in raw_allocations
            if isinstance(item, Mapping)
        ]
        if (
            quote.get("route_class") != expected.route_class
            or quote.get("pair") != expected.pair
            or tuple(quote.get("domain_flow_ids", ()))
            != expected.domain_flow_ids
            or quote.get("workload_digest") != expected.workload_digest
            or quote.get("formula_reference") != FORMULA_REF
            or quote.get("pricing_evidence_digests")
            != {
                "source": pricing_evidence[expected.source_provider],
                "destination": pricing_evidence[
                    expected.destination_provider
                ],
            }
            or (
                uses_event_layer
                and expected.route_class == "domain_event_cross_cloud"
                and quote.get("topology_cost_registry_digest")
                != SIX_LAYER_TOPOLOGY_COST_REGISTRY_DIGEST
            )
            or len(allocation_ids) != len(set(allocation_ids))
            or set(allocation_ids) != set(expected.allocation_item_ids)
        ):
            raise ArchitectureResolutionError(
                "ARCH_PRICING_EVIDENCE_MISSING",
                owner_id,
                "Route price result is not bound to the exact route, workload, and evidence",
            )
        amount = _decimal(quote.get("monthly_amount"), owner_id)
        allocations = {
            str(item["item_id"]): _decimal(
                item.get("monthly_amount"),
                f"{owner_id}.allocations",
            )
            for item in raw_allocations
        }
        if sum(allocations.values(), Decimal(0)) != amount:
            raise ArchitectureResolutionError(
                "ARCH_PRICING_EVIDENCE_MISSING",
                owner_id,
                "Route allocation does not reconcile to its owner total",
            )
        route_owner_totals[owner_id] = amount
        for item_id, allocated in allocations.items():
            if item_id.startswith("component."):
                component_totals[item_id] += allocated
            else:
                edge_totals[item_id] += allocated
    monthly_total = sum(component_totals.values(), Decimal(0)) + sum(
        edge_totals.values(), Decimal(0)
    )
    expected_total = sum(component_owner_totals.values(), Decimal(0)) + sum(
        route_owner_totals.values(), Decimal(0)
    )
    if monthly_total != expected_total:
        raise ArchitectureResolutionError(
            "ARCH_RESOLUTION_BUILD_FAILED",
            "costSummary",
            "Five-layer v2 cost aggregation does not reconcile",
        )
    return FiveLayerV2CostEvaluation(
        currency=currency,
        component_totals=MappingProxyType(component_totals),
        edge_totals=MappingProxyType(edge_totals),
        component_owner_totals=MappingProxyType(component_owner_totals),
        route_owner_totals=MappingProxyType(route_owner_totals),
        monthly_total=monthly_total,
    )


def selection_digest(selection: Mapping[str, Any]) -> str:
    """Public helper for a pricing adapter to bind its formula result."""

    return _selection_digest(selection)


def select_lowest_cost_five_layer_v2_candidate(
    candidates: tuple[FiveLayerV2CostedCandidate, ...],
) -> FiveLayerV2CostedCandidate:
    """Select by exact monthly cost, then stable logical/provider assignment."""

    if not candidates:
        raise ArchitectureResolutionError(
            "ARCH_NO_ADMISSIBLE_CANDIDATE",
            "candidates",
            "No fully costed Five-layer v2 candidate is available",
        )
    if len({item.candidate_id for item in candidates}) != len(candidates):
        raise ArchitectureResolutionError(
            "ARCH_NO_ADMISSIBLE_CANDIDATE",
            "candidates",
            "Five-layer v2 candidate IDs must be unique",
        )
    return min(
        candidates,
        key=lambda item: (
            item.evaluation.monthly_total,
            item.canonical_assignment_key,
            item.candidate_id,
        ),
    )
