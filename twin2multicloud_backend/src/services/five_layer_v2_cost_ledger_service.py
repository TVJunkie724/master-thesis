"""Untrusted Phase 8 cost-ledger validation and result projections."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
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
SIX_LAYER_TOPOLOGY_COST_REGISTRY_DIGEST = (
    "sha256:06c0a075f4db7944f4db5a43b4e58f7c5d9172220f0677ea514fc3a0ad5f3f1e"
)
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
    "component.eventing": "Eventing",
}
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
            "extension.action.outcome.v1",
            "notification.workflow.outcome.v1",
            "device.command.outcome.v1",
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
    normalized_quantities: dict[str, str]


@dataclass(frozen=True, slots=True)
class ValidatedFiveLayerV2CostLedger:
    ledger: dict[str, Any]
    result_items: tuple[dict[str, Any], ...]
    monthly_total: Decimal


def _fail(field: str, message: str) -> NoReturn:
    raise OptimizerContractError(
        "Optimizer Phase 8 cost ledger is invalid",
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
            "Optimizer Phase 8 cost ledger is invalid",
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
        raise RuntimeError("Phase 8 cost-ledger contract is unavailable") from exc
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
        _fail("params", "Ledger workload is not a frozen Phase 8 scenario")
    scenario_id = str(workload["eventingScenarioId"])
    digest = eventing["scenario_digests"].get(scenario_id)
    if scenario_id != f"eventing-{size}-v1" or not isinstance(digest, str):
        _fail("params.eventingScenarioId", "Ledger Eventing scenario is unavailable")
    return size, workload, {"id": scenario_id, "version": "1", "digest": digest}


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal(1)))
    return format(normalized, "f")


def _domain_event_channel_quantities(
    scenario: Mapping[str, Any],
) -> dict[str, tuple[Decimal, Decimal]]:
    events = Decimal(int(scenario["events_per_month"]))
    matches = events * Decimal(str(scenario["rule_match_share"]))
    workflows = matches * Decimal(
        str(scenario["workflow_start_share_of_matches"])
    )
    commands = matches * Decimal(
        str(scenario["device_command_share_of_matches"])
    )
    publishes = {
        "telemetry.received.v1": events,
        "telemetry.processed.v1": events,
        "event.matched.v1": matches,
        "notification.requested.v1": workflows,
        "device.command.requested.v1": commands,
        "extension.action.outcome.v1": matches,
        "notification.workflow.outcome.v1": workflows,
        "device.command.outcome.v1": commands,
    }
    if any(value != value.to_integral_value() for value in publishes.values()):
        _fail("params.eventingScenarioId", "Domain-event count is fractional")
    retry_share = Decimal(str(scenario["retry_share"]))
    replay_share = Decimal(str(scenario["replay_share"]))
    attempts = {
        channel_id: count
        + (count * retry_share).to_integral_value(rounding=ROUND_CEILING)
        + (count * replay_share).to_integral_value(rounding=ROUND_CEILING)
        for channel_id, count in publishes.items()
    }
    envelope_bytes = Decimal(1024)
    telemetry_bytes = Decimal(int(scenario["average_event_payload_bytes"]))
    canonical_bytes = {
        "telemetry.received.v1": telemetry_bytes + envelope_bytes,
        "telemetry.processed.v1": telemetry_bytes + envelope_bytes,
        "event.matched.v1": Decimal(1024) + envelope_bytes,
        "notification.requested.v1": Decimal(1024) + envelope_bytes,
        "device.command.requested.v1": Decimal(1024) + envelope_bytes,
        "extension.action.outcome.v1": Decimal(512) + envelope_bytes,
        "notification.workflow.outcome.v1": Decimal(512) + envelope_bytes,
        "device.command.outcome.v1": Decimal(512) + envelope_bytes,
    }
    return {
        channel_id: (attempts[channel_id], canonical_bytes[channel_id])
        for channel_id in publishes
    }


def _route_quantities(
    route_class: str,
    domain_flow_ids: tuple[str, ...],
    workload: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> dict[str, str]:
    month_seconds = Decimal("2592000")
    interval_seconds = (
        Decimal(str(workload["deviceSendingIntervalInMinutes"])) * Decimal(60)
    )
    messages = (
        Decimal(int(workload["numberOfDevices"]))
        * month_seconds
        / interval_seconds
    ).to_integral_value(rounding=ROUND_CEILING)
    payload_bytes = Decimal(str(workload["averageSizeOfMessageInKb"])) * 1024
    if route_class == "domain_event_cross_cloud":
        channels = _domain_event_channel_quantities(scenario)
        try:
            selected = [
                channels[flow_id.split(":", 1)[0]]
                for flow_id in domain_flow_ids
            ]
        except KeyError as exc:
            _fail("costLedger.route_costs", f"Unknown domain-event flow {exc.args[0]}")
        operations = sum((item[0] for item in selected), Decimal(0))
        egress_bytes = sum((item[0] * item[1] for item in selected), Decimal(0))
    elif route_class == "twin_projection_cross_cloud":
        operations = (
            (
                Decimal(str(workload["twinStateMaterializationsPerSecond"]))
                + Decimal(str(workload["twinGraphUpdatesPerSecond"]))
            )
            * month_seconds
        ).to_integral_value(rounding=ROUND_CEILING)
        egress_bytes = operations * payload_bytes
    elif route_class in {
        "storage_hot_to_cool_cross_cloud",
        "storage_cool_to_archive_cross_cloud",
    }:
        operations = Decimal(8640)
        egress_bytes = messages * payload_bytes
    else:
        _fail("costLedger.route_costs", "Route class has no quantity formula")
    return {
        "source_runtime": _decimal_text(operations),
        "destination_operations": _decimal_text(operations),
        "cross_cloud_egress_bytes": _decimal_text(egress_bytes),
    }


def _expected_routes(
    assignment: Mapping[str, str],
    *,
    size: str,
    workload: Mapping[str, Any],
    eventing_ref: Mapping[str, str],
) -> tuple[ExpectedRoute, ...]:
    registry, _fixtures, eventing = _sources()
    scenario = next(
        item
        for item in eventing["scenarios"]
        if item["scenario_id"] == eventing_ref["id"]
    )
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
                normalized_quantities=_route_quantities(
                    route_class,
                    flows,
                    workload,
                    scenario,
                ),
            )
        )

    domain_sources: dict[tuple[str, str], set[str]] = {}
    domain_flows: dict[tuple[str, str], list[str]] = {}
    uses_event_layer = "component.eventing" in assignment
    if uses_event_layer:
        for edge_id, source_logical, destination_logical, flow_ids in (
            SIX_LAYER_EVENT_FLOWS
        ):
            source = assignment[source_logical]
            destination = assignment[destination_logical]
            if source == destination:
                continue
            pair = (source, destination)
            domain_sources.setdefault(pair, set()).add(edge_id)
            domain_flows.setdefault(pair, []).extend(flow_ids)
    else:
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
            (
                tuple(sorted(set(domain_flows[pair])))
                if uses_event_layer
                else tuple(domain_flows[pair])
            ),
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
    profile_ref = architecture.get("architecture_profile_ref")
    six_layer = (
        isinstance(profile_ref, Mapping)
        and profile_ref.get("id") == "six-layer-eventing"
        and profile_ref.get("version") == "1"
    )

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
    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in architecture["component_assignments"]
    }
    if set(assignment) - set(LOGICAL_LAYER):
        _fail(
            "resolvedTwinArchitecture.component_assignments",
            "Cost ledger contains an unsupported logical component",
        )
    component_totals = {logical: Decimal(0) for logical in assignment}
    result_items: list[dict[str, Any]] = []
    owner_total = Decimal(0)
    for quote in raw_component_costs:
        expected_component_keys = {
            "component_id",
            "cost_owner_id",
            "selection_digest",
            "formula_reference",
            "pricing_evidence_digest",
            "monthly_amount",
        }
        topology_component = (
            six_layer and quote.get("component_id") in SIX_LAYER_EVENT_COMPONENT_IDS
        )
        if topology_component:
            expected_component_keys.add("topology_cost_registry_digest")
        _only_keys(
            quote,
            expected_component_keys,
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
            or (
                topology_component
                and quote["topology_cost_registry_digest"]
                != SIX_LAYER_TOPOLOGY_COST_REGISTRY_DIGEST
            )
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
        route = expected_routes[quote["cost_owner_id"]]
        expected_route_keys = {
            "cost_owner_id",
            "route_class",
            "pair",
            "domain_flow_ids",
            "workload_digest",
            "formula_reference",
            "normalized_quantities",
            "pricing_evidence_digests",
            "monthly_amount",
            "allocations",
        }
        topology_route = six_layer and route.route_class == "domain_event_cross_cloud"
        if topology_route:
            expected_route_keys.add("topology_cost_registry_digest")
        _only_keys(
            quote,
            expected_route_keys,
            "costLedger.route_costs",
        )
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
            or quote["normalized_quantities"] != route.normalized_quantities
            or quote["pricing_evidence_digests"] != expected_digests
            or (
                topology_route
                and quote["topology_cost_registry_digest"]
                != SIX_LAYER_TOPOLOGY_COST_REGISTRY_DIGEST
            )
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
