"""Untrusted Five-layer v2 cost-ledger validation and result projections."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, NoReturn

from src.schemas.pricing_catalog import PricingCatalogContext
from src.services.errors import OptimizerContractError
from src.services.resolved_deployment_specification_service import (
    V2_CONTRACT_ROOT,
)


FORMULA_REF = "formula.phase-08-complete-service-bundles"
PROVIDER_LABEL = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
WORKLOAD_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "five-layer-workload"
    / "v2"
)
LOGICAL_LAYER = {
    "component.ingestion": "L1",
    "component.processing": "L2",
    "component.hot-storage": "L3_hot",
    "component.cool-storage": "L3_cool",
    "component.archive-storage": "L3_archive",
    "component.twin-state": "L4",
    "component.visualization": "L5",
}
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
    (
        "notification.requested.v1",
        "component.processing",
        "component.processing",
    ),
    (
        "device.command.requested.v1",
        "component.processing",
        "component.ingestion",
    ),
    (
        "extension.action.outcome.v1",
        "component.processing",
        "component.hot-storage",
    ),
    (
        "notification.workflow.outcome.v1",
        "component.processing",
        "component.hot-storage",
    ),
    (
        "device.command.outcome.v1",
        "component.ingestion",
        "component.hot-storage",
    ),
)


@dataclass(frozen=True, slots=True)
class ExpectedRoute:
    cost_owner_id: str
    route_class: str
    pair: str
    source_provider: str
    destination_provider: str
    allocation_item_ids: tuple[str, ...]
    domain_flow_ids: tuple[str, ...]
    workload_digest: str


@dataclass(frozen=True, slots=True)
class ValidatedFiveLayerV2CostLedger:
    ledger: dict[str, Any]
    result_items: tuple[dict[str, Any], ...]
    monthly_total: Decimal


def _fail(field: str, message: str) -> NoReturn:
    raise OptimizerContractError(
        "Optimizer Five-layer v2 cost ledger is invalid",
        [{"field": field, "message": message}],
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        _fail(field, "Expected an exact decimal string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise OptimizerContractError(
            "Optimizer Five-layer v2 cost ledger is invalid",
            [{"field": field, "message": "Expected an exact decimal string"}],
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        _fail(field, "Expected a finite non-negative amount")
    return parsed


def _only_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(value) != expected:
        _fail(field, "Ledger fields are incomplete or unsupported")


@lru_cache(maxsize=1)
def _sources() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    try:
        registry = json.loads(
            (V2_CONTRACT_ROOT / "component-capacity-registry.json").read_text(
                encoding="utf-8"
            )
        )
        fixtures = {
            size: json.loads(
                (
                    WORKLOAD_ROOT
                    / "fixtures"
                    / "valid"
                    / f"core-{size}.json"
                ).read_text(encoding="utf-8")
            )
            for size in ("small", "medium", "large")
        }
        eventing = json.loads(
            (WORKLOAD_ROOT / "eventing-scenario-catalog.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Five-layer v2 cost-ledger contract is unavailable") from exc
    return registry, fixtures, eventing


def _resolved_workload(
    persisted_params: Mapping[str, Any],
) -> tuple[str, dict[str, Any], dict[str, str]]:
    _registry, fixtures, eventing = _sources()
    workload = {
        key: value
        for key, value in persisted_params.items()
        if key != "optimizationProfileId"
    }
    scenario_identity = {
        key: value for key, value in workload.items() if key != "currency"
    }
    size = next(
        (
            candidate
            for candidate, fixture in fixtures.items()
            if scenario_identity
            == {key: value for key, value in fixture.items() if key != "currency"}
        ),
        None,
    )
    if size is None:
        _fail("params", "Ledger workload is not a frozen Five-layer v2 scenario")
    scenario_id = str(workload["eventingScenarioId"])
    digest = eventing["scenario_digests"].get(scenario_id)
    if scenario_id != f"eventing-{size}-v1" or not isinstance(digest, str):
        _fail("params.eventingScenarioId", "Ledger Eventing scenario is unavailable")
    return size, workload, {"id": scenario_id, "version": "1", "digest": digest}


def _expected_routes(
    assignment: Mapping[str, str],
    *,
    size: str,
    workload: Mapping[str, Any],
    eventing_ref: Mapping[str, str],
) -> tuple[ExpectedRoute, ...]:
    registry, _fixtures, _eventing = _sources()
    route_index = {
        (item["route_class"], item["pair"]): item
        for item in registry["route_owners"]
    }
    routes: list[ExpectedRoute] = []

    def add(
        route_class: str,
        source: str,
        destination: str,
        allocations: tuple[str, ...],
        flows: tuple[str, ...] = (),
    ) -> None:
        if source == destination:
            return
        pair = f"{source}->{destination}"
        registered = route_index.get((route_class, pair))
        if not isinstance(registered, Mapping):
            _fail("costLedger.route_costs", "Required route owner is unavailable")
        workload_digest = _digest(
            {
                "route_class": route_class,
                "pair": pair,
                "allocation_item_ids": allocations,
                "domain_flow_ids": flows,
                "core_size": size,
                "workload": dict(workload),
                "eventing_scenario_ref": dict(eventing_ref),
            }
        )
        routes.append(
            ExpectedRoute(
                cost_owner_id=str(registered["cost_owner_id"]),
                route_class=route_class,
                pair=pair,
                source_provider=source,
                destination_provider=destination,
                allocation_item_ids=allocations,
                domain_flow_ids=flows,
                workload_digest=workload_digest,
            )
        )

    domain_sources: dict[tuple[str, str], set[str]] = {}
    domain_flows: dict[tuple[str, str], list[str]] = {}
    for flow_id, source_logical, destination_logical in DOMAIN_EVENT_FLOWS:
        source = assignment[source_logical]
        destination = assignment[destination_logical]
        if source == destination:
            continue
        pair = (source, destination)
        domain_sources.setdefault(pair, set()).add(source_logical)
        domain_flows.setdefault(pair, []).append(flow_id)
    for pair, sources in sorted(domain_sources.items()):
        add(
            "domain_event_cross_cloud",
            pair[0],
            pair[1],
            tuple(sorted(sources)),
            tuple(domain_flows[pair]),
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
    return tuple(sorted(routes, key=lambda item: item.cost_owner_id))


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


def validate_five_layer_v2_cost_ledger(
    raw_ledger: object,
    *,
    specification: Mapping[str, Any],
    architecture: Mapping[str, Any],
    persisted_params: Mapping[str, Any],
    catalog_context: PricingCatalogContext,
    expected_total_exact: object,
) -> ValidatedFiveLayerV2CostLedger:
    if not isinstance(raw_ledger, Mapping):
        _fail("costLedger", "Expected a cost-ledger object")
    serialized = _canonical_json(raw_ledger)
    if len(serialized.encode("utf-8")) > 512 * 1024:
        _fail("costLedger", "Cost ledger exceeds the size limit")
    ledger = json.loads(serialized)
    _only_keys(
        ledger,
        {"schema_version", "currency", "component_costs", "route_costs"},
        "costLedger",
    )
    if ledger["schema_version"] != "five-layer-v2-cost-ledger.v1":
        _fail("costLedger.schema_version", "Cost-ledger version is unsupported")
    if ledger["currency"] != specification["currency"]:
        _fail("costLedger.currency", "Cost-ledger currency differs")

    selections = {
        item["implementation_component_id"]: item
        for item in specification["component_selections"]
    }
    raw_component_costs = ledger["component_costs"]
    if not isinstance(raw_component_costs, list):
        _fail("costLedger.component_costs", "Expected a component-cost list")
    component_ids = [
        item.get("component_id")
        for item in raw_component_costs
        if isinstance(item, Mapping)
    ]
    if (
        len(component_ids) != len(raw_component_costs)
        or len(component_ids) != len(set(component_ids))
        or set(component_ids) != set(selections)
    ):
        _fail(
            "costLedger.component_costs",
            "Every selected component requires exactly one cost owner",
        )
    component_totals = {logical: Decimal(0) for logical in LOGICAL_LAYER}
    result_items: list[dict[str, Any]] = []
    owner_total = Decimal(0)
    for quote in raw_component_costs:
        _only_keys(
            quote,
            {
                "component_id",
                "cost_owner_id",
                "selection_digest",
                "formula_reference",
                "pricing_evidence_digest",
                "monthly_amount",
            },
            "costLedger.component_costs",
        )
        component_id = quote["component_id"]
        selection = selections[component_id]
        provider = selection["provider"]
        amount = _decimal(
            quote["monthly_amount"],
            f"costLedger.component_costs.{component_id}.monthly_amount",
        )
        if (
            quote["cost_owner_id"] != f"cost::{component_id}"
            or quote["selection_digest"] != _selection_digest(selection)
            or quote["formula_reference"] != FORMULA_REF
            or quote["pricing_evidence_digest"]
            != catalog_context.catalogs[provider].content_digest
        ):
            _fail(
                f"costLedger.component_costs.{component_id}",
                "Component quote is not bound to its selection and catalog",
            )
        logical = selection["logical_component_id"]
        component_totals[logical] += amount
        owner_total += amount
        result_items.append(
            {
                "layer": LOGICAL_LAYER[logical],
                "component": component_id,
                "provider": PROVIDER_LABEL[provider],
                "service_intent_id": quote["cost_owner_id"],
                "cost_amount": float(amount),
                "currency": ledger["currency"],
                "unit": "month",
                "evidence_id": quote["pricing_evidence_digest"],
                "service_model_id": quote["selection_digest"],
                "calculation_notes_json": _canonical_json(
                    {
                        "source": "five-layer-v2-cost-ledger",
                        "selection_id": selection["selection_id"],
                        "formula_reference": quote["formula_reference"],
                    }
                ),
                "review_status": "ready",
            }
        )

    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in architecture["component_assignments"]
    }
    size, workload, eventing_ref = _resolved_workload(persisted_params)
    expected_routes = {
        route.cost_owner_id: route
        for route in _expected_routes(
            assignment,
            size=size,
            workload=workload,
            eventing_ref=eventing_ref,
        )
    }
    raw_route_costs = ledger["route_costs"]
    if not isinstance(raw_route_costs, list):
        _fail("costLedger.route_costs", "Expected a route-cost list")
    route_ids = [
        item.get("cost_owner_id")
        for item in raw_route_costs
        if isinstance(item, Mapping)
    ]
    if (
        len(route_ids) != len(raw_route_costs)
        or len(route_ids) != len(set(route_ids))
        or set(route_ids) != set(expected_routes)
    ):
        _fail(
            "costLedger.route_costs",
            "Every required Cross-Cloud route requires exactly one cost owner",
        )
    edge_totals = {
        item["edge_id"]: Decimal(0) for item in architecture["resolved_edges"]
    }
    for quote in raw_route_costs:
        _only_keys(
            quote,
            {
                "cost_owner_id",
                "route_class",
                "pair",
                "domain_flow_ids",
                "workload_digest",
                "formula_reference",
                "pricing_evidence_digests",
                "monthly_amount",
                "allocations",
            },
            "costLedger.route_costs",
        )
        route = expected_routes[quote["cost_owner_id"]]
        expected_digests = {
            "source": catalog_context.catalogs[
                route.source_provider
            ].content_digest,
            "destination": catalog_context.catalogs[
                route.destination_provider
            ].content_digest,
        }
        if (
            quote["route_class"] != route.route_class
            or quote["pair"] != route.pair
            or quote["domain_flow_ids"] != list(route.domain_flow_ids)
            or quote["workload_digest"] != route.workload_digest
            or quote["formula_reference"] != FORMULA_REF
            or quote["pricing_evidence_digests"] != expected_digests
            or not isinstance(quote["allocations"], list)
        ):
            _fail(
                f"costLedger.route_costs.{route.cost_owner_id}",
                "Route quote is not bound to its route, workload, and catalogs",
            )
        allocation_ids = [
            item.get("item_id")
            for item in quote["allocations"]
            if isinstance(item, Mapping)
        ]
        if (
            len(allocation_ids) != len(quote["allocations"])
            or len(allocation_ids) != len(set(allocation_ids))
            or set(allocation_ids) != set(route.allocation_item_ids)
        ):
            _fail(
                f"costLedger.route_costs.{route.cost_owner_id}.allocations",
                "Route allocations are incomplete or duplicated",
            )
        amount = _decimal(
            quote["monthly_amount"],
            f"costLedger.route_costs.{route.cost_owner_id}.monthly_amount",
        )
        allocated_total = Decimal(0)
        for allocation in quote["allocations"]:
            _only_keys(
                allocation,
                {"item_id", "monthly_amount"},
                f"costLedger.route_costs.{route.cost_owner_id}.allocations",
            )
            allocated = _decimal(
                allocation["monthly_amount"],
                (
                    "costLedger.route_costs."
                    f"{route.cost_owner_id}.allocations.monthly_amount"
                ),
            )
            item_id = allocation["item_id"]
            if item_id.startswith("component."):
                component_totals[item_id] += allocated
            else:
                edge_totals[item_id] += allocated
            allocated_total += allocated
        if allocated_total != amount:
            _fail(
                f"costLedger.route_costs.{route.cost_owner_id}.allocations",
                "Route allocations do not reconcile",
            )
        owner_total += amount
        result_items.append(
            {
                "layer": route.route_class,
                "component": "cross_cloud_route",
                "provider": PROVIDER_LABEL[route.source_provider],
                "service_intent_id": route.cost_owner_id,
                "cost_amount": float(amount),
                "currency": ledger["currency"],
                "unit": "month",
                "evidence_id": expected_digests["source"],
                "service_model_id": route.workload_digest,
                "calculation_notes_json": _canonical_json(
                    {
                        "source": "five-layer-v2-cost-ledger",
                        "pair": route.pair,
                        "allocations": quote["allocations"],
                        "pricing_evidence_digests": expected_digests,
                    }
                ),
                "review_status": "ready",
            }
        )

    summary_components = {
        item["item_id"]: _decimal(
            item["monthly_amount"],
            f"resolvedTwinArchitecture.cost_summary.{item['item_id']}",
        )
        for item in architecture["cost_summary"]["component_totals"]
    }
    summary_edges = {
        item["item_id"]: _decimal(
            item["monthly_amount"],
            f"resolvedTwinArchitecture.cost_summary.{item['item_id']}",
        )
        for item in architecture["cost_summary"]["edge_totals"]
    }
    summary_total = _decimal(
        architecture["cost_summary"]["monthly_total"],
        "resolvedTwinArchitecture.cost_summary.monthly_total",
    )
    if (
        component_totals != summary_components
        or edge_totals != summary_edges
        or owner_total != summary_total
        or _decimal(expected_total_exact, "totalCostExact") != summary_total
    ):
        _fail(
            "costLedger",
            "Cost owners and allocations do not reconcile to the architecture",
        )
    return ValidatedFiveLayerV2CostLedger(
        ledger=ledger,
        result_items=tuple(result_items),
        monthly_total=summary_total,
    )
