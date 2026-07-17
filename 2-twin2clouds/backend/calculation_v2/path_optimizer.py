"""Closed-world complete-path evaluation for the five-layer baseline."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
from itertools import product
import json
from typing import Any

from backend.calculation_v2.components.types import LayerType, Provider
from backend.calculation_v2.transfer_pricing import (
    TransferBillingScope,
    TransferGeography,
    TransferNetworkTier,
    TransferPricingContractError,
    TransferPricingPool,
    TransferRouteClass,
    TransferEndpoint,
    TransferRouteIntent,
    TransferRouteRegistry,
    TransferSegmentCharge,
    allocate_transfer_pool,
)
from backend.pricing_catalog_models import PricingCatalogContext
from backend.pricing_registry import PricingRegistry
from backend.transfer_catalog import validate_transfer_catalog


PATH_OPTIMIZATION_SCHEMA_VERSION = "complete-path-optimization.v1"
TRANSFER_CONTEXT_SCHEMA_VERSION = "complete-path-transfer-pricing.v1"

LAYER_ORDER: tuple[tuple[str, LayerType], ...] = (
    ("L1", LayerType.L1_INGESTION),
    ("L2", LayerType.L2_PROCESSING),
    ("L3_hot", LayerType.L3_HOT_STORAGE),
    ("L3_cool", LayerType.L3_COOL_STORAGE),
    ("L3_archive", LayerType.L3_ARCHIVE_STORAGE),
    ("L4", LayerType.L4_TWIN_MANAGEMENT),
    ("L5", LayerType.L5_VISUALIZATION),
)

_PROVIDER_LABELS = {
    Provider.AWS: "AWS",
    Provider.AZURE: "Azure",
    Provider.GCP: "GCP",
}
_PROVIDERS_BY_LABEL = {label: provider for provider, label in _PROVIDER_LABELS.items()}
_CANONICAL_PROVIDER_ORDER = tuple(Provider)


@dataclass(frozen=True)
class BaselineEdgeWorkload:
    """One fixed baseline edge and its monthly transfer workload."""

    segment_id: str
    source_layer_key: str
    destination_layer_key: str
    source_layer: LayerType
    destination_layer: LayerType
    volume_bytes: Decimal
    volume_basis: str
    glue_invocations: Decimal
    glue_invocation_basis: str
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class LayerAssignment:
    """One provider selection and its provider-local layer cost."""

    layer_key: str
    layer: LayerType
    provider: Provider
    cost: Decimal


@dataclass(frozen=True)
class CompletePathEvaluation:
    """Fully evaluated architecture candidate including all baseline edges."""

    candidate_id: str
    assignments: tuple[LayerAssignment, ...]
    transfer_charges: tuple[TransferSegmentCharge, ...]
    pricing_pools: tuple[TransferPricingPool, ...]
    layer_cost: Decimal
    transfer_cost: Decimal
    total_cost: Decimal

    def provider_for(self, layer_key: str) -> Provider:
        for assignment in self.assignments:
            if assignment.layer_key == layer_key:
                return assignment.provider
        raise KeyError(layer_key)


@dataclass(frozen=True)
class CompletePathEvaluationSet:
    """Evaluated candidates plus bounded rejection diagnostics."""

    evaluations: tuple[CompletePathEvaluation, ...]
    enumerated_path_count: int
    rejected_by_error_code: tuple[tuple[str, int], ...]

    @property
    def rejected_path_count(self) -> int:
        return sum(count for _, count in self.rejected_by_error_code)


GlueCostResolver = Callable[[Provider, Decimal], Decimal]
RouteIndexValue = TransferRouteIntent | tuple[str, str]


def build_baseline_edge_workloads(
    derived: Mapping[str, Any],
) -> tuple[BaselineEdgeWorkload, ...]:
    """Build the six approved baseline edges from canonical monthly usage."""

    messages = _decimal(
        derived["total_messages_per_month"],
        "total_messages_per_month",
    )
    message_size_kb = _decimal(
        derived["msg_size_kb"],
        "msg_size_kb",
    )
    telemetry_bytes = messages * message_size_kb * Decimal(1024)
    queries = _decimal(derived["queries_per_month"], "queries_per_month")
    query_response_size_kb = _decimal(
        derived["average_digital_twin_query_response_size_kb"],
        "average_digital_twin_query_response_size_kb",
    )
    query_response_bytes = queries * query_response_size_kb * Decimal(1024)
    transition_assumption = (
        "Steady-state storage transitions move one newly ingested monthly cohort; "
        "retained storage volume is not retransferred every month."
    )
    query_assumption = (
        "The legacy query-response size input uses KiB semantics: one input KB "
        "equals 1024 bytes."
    )

    return (
        BaselineEdgeWorkload(
            segment_id="L1_to_L2",
            source_layer_key="L1",
            destination_layer_key="L2",
            source_layer=LayerType.L1_INGESTION,
            destination_layer=LayerType.L2_PROCESSING,
            volume_bytes=telemetry_bytes,
            volume_basis="monthly_telemetry_payload",
            glue_invocations=messages,
            glue_invocation_basis="one_destination_bridge_invocation_per_message",
            assumptions=(),
        ),
        BaselineEdgeWorkload(
            segment_id="L2_to_L3_hot",
            source_layer_key="L2",
            destination_layer_key="L3_hot",
            source_layer=LayerType.L2_PROCESSING,
            destination_layer=LayerType.L3_HOT_STORAGE,
            volume_bytes=telemetry_bytes,
            volume_basis="monthly_processed_telemetry_payload",
            glue_invocations=messages,
            glue_invocation_basis="one_destination_bridge_invocation_per_message",
            assumptions=(),
        ),
        BaselineEdgeWorkload(
            segment_id="L3_hot_to_L3_cool",
            source_layer_key="L3_hot",
            destination_layer_key="L3_cool",
            source_layer=LayerType.L3_HOT_STORAGE,
            destination_layer=LayerType.L3_COOL_STORAGE,
            volume_bytes=telemetry_bytes,
            volume_basis="monthly_hot_to_cool_transition_cohort",
            glue_invocations=Decimal(30),
            glue_invocation_basis="one_daily_destination_mover_invocation",
            assumptions=(transition_assumption,),
        ),
        BaselineEdgeWorkload(
            segment_id="L3_cool_to_L3_archive",
            source_layer_key="L3_cool",
            destination_layer_key="L3_archive",
            source_layer=LayerType.L3_COOL_STORAGE,
            destination_layer=LayerType.L3_ARCHIVE_STORAGE,
            volume_bytes=telemetry_bytes,
            volume_basis="monthly_cool_to_archive_transition_cohort",
            glue_invocations=Decimal(4),
            glue_invocation_basis="one_weekly_destination_mover_invocation",
            assumptions=(transition_assumption,),
        ),
        BaselineEdgeWorkload(
            segment_id="L3_hot_to_L4",
            source_layer_key="L3_hot",
            destination_layer_key="L4",
            source_layer=LayerType.L3_HOT_STORAGE,
            destination_layer=LayerType.L4_TWIN_MANAGEMENT,
            volume_bytes=query_response_bytes,
            volume_basis="monthly_digital_twin_query_response_payload",
            glue_invocations=queries,
            glue_invocation_basis="one_destination_reader_invocation_per_query",
            assumptions=(query_assumption,),
        ),
        BaselineEdgeWorkload(
            segment_id="L4_to_L5",
            source_layer_key="L4",
            destination_layer_key="L5",
            source_layer=LayerType.L4_TWIN_MANAGEMENT,
            destination_layer=LayerType.L5_VISUALIZATION,
            volume_bytes=query_response_bytes,
            volume_basis="monthly_visualization_query_response_payload",
            glue_invocations=queries,
            glue_invocation_basis="one_destination_bridge_invocation_per_query",
            assumptions=(query_assumption,),
        ),
    )


def evaluate_complete_paths(
    *,
    layer_options: Mapping[str, Sequence[tuple[str, float]]],
    derived: Mapping[str, Any],
    pricing: Mapping[str, Any],
    pricing_catalog_context: PricingCatalogContext,
    pricing_registry: PricingRegistry,
    glue_cost_resolver: GlueCostResolver,
) -> CompletePathEvaluationSet:
    """Enumerate and evaluate every executable baseline architecture path."""

    if not isinstance(pricing_catalog_context, PricingCatalogContext):
        raise TypeError("pricing_catalog_context must be a PricingCatalogContext")
    if not isinstance(pricing_registry, PricingRegistry):
        raise TypeError("pricing_registry must be a PricingRegistry")
    transfer_registry = pricing_registry.transfer_routes

    normalized_options = _normalize_layer_options(layer_options)
    workloads = build_baseline_edge_workloads(derived)
    endpoints = _build_endpoint_index(
        pricing_catalog_context,
        transfer_registry,
    )
    route_index = _build_route_index(
        workloads,
        endpoints,
        transfer_registry,
    )
    pools = _build_pricing_pools(
        pricing,
        pricing_catalog_context,
        pricing_registry,
    )

    evaluations: list[CompletePathEvaluation] = []
    rejected_codes: Counter[str] = Counter()
    glue_cost_cache: dict[tuple[Provider, Decimal], Decimal] = {}
    option_product = product(
        *(normalized_options[layer_key] for layer_key, _ in LAYER_ORDER)
    )
    enumerated_count = 0
    for selected_options in option_product:
        enumerated_count += 1
        assignments = tuple(
            LayerAssignment(
                layer_key=layer_key,
                layer=layer,
                provider=selected_provider,
                cost=selected_cost,
            )
            for (layer_key, layer), (selected_provider, selected_cost) in zip(
                LAYER_ORDER,
                selected_options,
                strict=True,
            )
        )
        try:
            evaluations.append(
                _evaluate_path(
                    assignments=assignments,
                    workloads=workloads,
                    route_index=route_index,
                    pools=pools,
                    glue_cost_resolver=glue_cost_resolver,
                    glue_cost_cache=glue_cost_cache,
                )
            )
        except TransferPricingContractError as exc:
            rejected_codes[exc.code] += 1

    if not evaluations:
        details = ", ".join(
            f"{code}={count}" for code, count in sorted(rejected_codes.items())
        )
        raise TransferPricingContractError(
            "TRANSFER_NO_COMPLETE_PATH",
            "no complete baseline path satisfies the transfer contract"
            + (f" ({details})" if details else ""),
        )
    return CompletePathEvaluationSet(
        evaluations=tuple(evaluations),
        enumerated_path_count=enumerated_count,
        rejected_by_error_code=tuple(sorted(rejected_codes.items())),
    )


def build_optimization_diagnostics(
    evaluation_set: CompletePathEvaluationSet,
    winner: CompletePathEvaluation,
) -> dict[str, Any]:
    """Serialize bounded solver diagnostics without raw pricing payloads."""

    return {
        "schemaVersion": PATH_OPTIMIZATION_SCHEMA_VERSION,
        "enumeratedPathCount": evaluation_set.enumerated_path_count,
        "evaluatedPathCount": len(evaluation_set.evaluations),
        "rejectedPathCount": evaluation_set.rejected_path_count,
        "rejectedByErrorCode": dict(evaluation_set.rejected_by_error_code),
        "winningCandidateId": winner.candidate_id,
        "winningScore": float(winner.total_cost),
        "winningLayerCost": float(winner.layer_cost),
        "winningTransferCost": float(winner.transfer_cost),
        "tieBreakPolicy": "canonical_provider_order",
        "canonicalProviderOrder": [
            provider.value for provider in _CANONICAL_PROVIDER_ORDER
        ],
        "scoreUnit": "USD/month",
    }


def build_transfer_pricing_context(
    winner: CompletePathEvaluation,
) -> dict[str, Any]:
    """Serialize the complete winning route and pool evidence trace."""

    pools = {pool.pool_id: pool for pool in winner.pricing_pools}
    pool_totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"volume_bytes": Decimal(0), "egress_cost": Decimal(0)}
    )
    route_payloads: list[dict[str, Any]] = []
    for charge in winner.transfer_charges:
        route = charge.route
        pool = pools.get(charge.pool_id)
        if pool is not None:
            pool_totals[pool.pool_id]["volume_bytes"] += route.volume_bytes
            pool_totals[pool.pool_id]["egress_cost"] += charge.egress_cost
        route_payloads.append(
            {
                "segmentId": route.segment_id,
                "source": _endpoint_payload(route.source),
                "destination": _endpoint_payload(route.destination),
                "routeClass": route.route_class.value,
                "networkTier": route.network_tier.value,
                "volumeBytes": _decimal_json(route.volume_bytes),
                "poolId": pool.pool_id if pool is not None else None,
                "catalogSnapshotId": (
                    pool.catalog_snapshot_id if pool is not None else None
                ),
                "evidenceId": pool.evidence_id if pool is not None else None,
                "tierContributions": [
                    {
                        "tierId": contribution.tier_id,
                        "fromQuantity": _decimal_json(
                            contribution.from_quantity
                        ),
                        "toQuantity": _decimal_json(contribution.to_quantity),
                        "billableQuantity": _decimal_json(
                            contribution.billable_quantity
                        ),
                        "unitPrice": _decimal_json(contribution.unit_price),
                        "cost": _decimal_json(contribution.cost),
                    }
                    for contribution in charge.tier_contributions
                ],
                "egressCost": _decimal_json(charge.egress_cost),
                "glueCost": _decimal_json(charge.glue_cost),
                "totalCost": _decimal_json(charge.total_cost),
                "assumptions": list(charge.assumptions),
            }
        )

    return {
        "schemaVersion": TRANSFER_CONTEXT_SCHEMA_VERSION,
        "currency": "USD",
        "assumptions": [
            (
                "Account-aggregate transfer allowances include only this "
                "calculation; unrelated workloads in the provider account "
                "are not imported."
            ),
            (
                "Destination glue free tiers are aggregated across glue routes "
                "in this calculation; selected layer functions and unrelated "
                "serverless workloads are not imported into the glue pool."
            ),
        ],
        "routes": route_payloads,
        "pools": [
            {
                "poolId": pool.pool_id,
                "provider": pool.provider.value,
                "routeClass": pool.route_class.value,
                "sourceGeography": pool.source_geography.value,
                "destinationGeography": pool.destination_geography.value,
                "networkTier": pool.network_tier.value,
                "billingScope": pool.billing_scope.value,
                "billingUnit": pool.billing_unit.value,
                "bytesPerBillingUnit": pool.bytes_per_billing_unit,
                "catalogSnapshotId": pool.catalog_snapshot_id,
                "evidenceId": pool.evidence_id,
                "aggregateVolumeBytes": _decimal_json(
                    pool_totals[pool.pool_id]["volume_bytes"]
                ),
                "aggregateEgressCost": _decimal_json(
                    pool_totals[pool.pool_id]["egress_cost"]
                ),
            }
            for pool in winner.pricing_pools
        ],
    }


def _normalize_layer_options(
    layer_options: Mapping[str, Sequence[tuple[str, float]]],
) -> dict[str, tuple[tuple[Provider, Decimal], ...]]:
    expected_layers = {layer_key for layer_key, _ in LAYER_ORDER}
    if set(layer_options) != expected_layers:
        raise ValueError("layer_options must contain the complete baseline layer set")
    normalized: dict[str, tuple[tuple[Provider, Decimal], ...]] = {}
    for layer_key, _ in LAYER_ORDER:
        options: dict[Provider, Decimal] = {}
        for provider_label, cost in layer_options[layer_key]:
            try:
                provider = _PROVIDERS_BY_LABEL[provider_label]
            except KeyError as exc:
                raise ValueError(
                    f"Unsupported provider label {provider_label!r}"
                ) from exc
            if provider in options:
                raise ValueError(
                    f"Duplicate provider option for {layer_key}.{provider_label}"
                )
            options[provider] = _decimal(
                cost,
                f"{layer_key}.{provider_label}",
            )
        if not options:
            raise ValueError(f"No executable provider option for {layer_key}")
        normalized[layer_key] = tuple(
            (provider, options[provider])
            for provider in _CANONICAL_PROVIDER_ORDER
            if provider in options
        )
    return normalized


def _build_endpoint_index(
    pricing_catalog_context: PricingCatalogContext,
    transfer_registry: TransferRouteRegistry,
) -> dict[tuple[LayerType, Provider], TransferEndpoint]:
    endpoints = {}
    for _, layer in LAYER_ORDER:
        for provider in Provider:
            region = pricing_catalog_context.catalogs[provider.value].pricing_region
            endpoints[(layer, provider)] = transfer_registry.endpoint(
                layer=layer,
                provider=provider,
                region=region,
            )
    return endpoints


def _build_pricing_pools(
    pricing: Mapping[str, Any],
    pricing_catalog_context: PricingCatalogContext,
    pricing_registry: PricingRegistry,
) -> dict[Provider, TransferPricingPool]:
    pools = {}
    for provider in Provider:
        provider_pricing = pricing.get(provider.value)
        transfer = (
            provider_pricing.get("transfer")
            if isinstance(provider_pricing, Mapping)
            else None
        )
        if not isinstance(transfer, Mapping):
            raise TransferPricingContractError(
                "TRANSFER_CATALOG_INVALID",
                f"missing {provider.value}.transfer catalog",
            )
        reference = pricing_catalog_context.catalogs[provider.value]
        table = validate_transfer_catalog(
            provider,
            reference.pricing_region,
            transfer,
            pricing_registry=pricing_registry,
        )
        source_geography = TransferGeography(transfer["source_geography"])
        destination_geography = TransferGeography.EUROPE
        network_tier = TransferNetworkTier(transfer["network_tier"])
        billing_scope = TransferBillingScope(transfer["billing_scope"])
        identity = {
            "provider": provider.value,
            "route_class": TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET.value,
            "source_geography": source_geography.value,
            "destination_geography": destination_geography.value,
            "network_tier": network_tier.value,
            "billing_scope": billing_scope.value,
            "catalog_snapshot_id": reference.snapshot_id,
            "evidence_id": table.evidence_id,
        }
        digest = hashlib.sha256(
            json.dumps(
                identity,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        pool = TransferPricingPool(
            pool_id=f"pool:{provider.value}:{digest}",
            provider=provider,
            route_class=TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
            source_geography=source_geography,
            destination_geography=destination_geography,
            network_tier=network_tier,
            billing_scope=billing_scope,
            catalog_snapshot_id=reference.snapshot_id,
            evidence_id=table.evidence_id,
            tier_table=table,
        )
        pools[provider] = pool
    return pools


def _build_route_index(
    workloads: Sequence[BaselineEdgeWorkload],
    endpoints: Mapping[tuple[LayerType, Provider], TransferEndpoint],
    transfer_registry: TransferRouteRegistry,
) -> dict[tuple[str, Provider, Provider], RouteIndexValue]:
    routes = {}
    for workload in workloads:
        for source_provider in Provider:
            for destination_provider in Provider:
                key = (
                    workload.segment_id,
                    source_provider,
                    destination_provider,
                )
                try:
                    routes[key] = transfer_registry.resolve_route(
                        segment_id=workload.segment_id,
                        source=endpoints[
                            (workload.source_layer, source_provider)
                        ],
                        destination=endpoints[
                            (workload.destination_layer, destination_provider)
                        ],
                        volume_bytes=workload.volume_bytes,
                        assumptions=(
                            f"volume_basis={workload.volume_basis}",
                            "glue_invocation_basis="
                            f"{workload.glue_invocation_basis}",
                            *workload.assumptions,
                        ),
                    )
                except TransferPricingContractError as exc:
                    routes[key] = (exc.code, exc.message)
    return routes


def _evaluate_path(
    *,
    assignments: tuple[LayerAssignment, ...],
    workloads: tuple[BaselineEdgeWorkload, ...],
    route_index: Mapping[
        tuple[str, Provider, Provider],
        RouteIndexValue,
    ],
    pools: Mapping[Provider, TransferPricingPool],
    glue_cost_resolver: GlueCostResolver,
    glue_cost_cache: dict[tuple[Provider, Decimal], Decimal],
) -> CompletePathEvaluation:
    assignments_by_key = {
        assignment.layer_key: assignment for assignment in assignments
    }
    routes: list[TransferRouteIntent] = []
    workload_by_segment = {workload.segment_id: workload for workload in workloads}
    for workload in workloads:
        source_provider = assignments_by_key[workload.source_layer_key].provider
        destination_provider = assignments_by_key[
            workload.destination_layer_key
        ].provider
        route_or_error = route_index[
            (
                workload.segment_id,
                source_provider,
                destination_provider,
            )
        ]
        if isinstance(route_or_error, tuple):
            raise TransferPricingContractError(*route_or_error)
        routes.append(
            route_or_error
        )

    glue_costs = _allocate_glue_costs(
        routes,
        workload_by_segment,
        glue_cost_resolver,
        glue_cost_cache,
    )
    charges_by_segment: dict[str, TransferSegmentCharge] = {}
    cross_provider_routes: dict[Provider, list[TransferRouteIntent]] = defaultdict(
        list
    )
    for route in routes:
        if route.route_class == TransferRouteClass.SAME_PROVIDER_SAME_REGION:
            charges_by_segment[route.segment_id] = TransferSegmentCharge(
                route=route,
                pool_id=f"no-egress:{route.source.provider.value}",
                tier_contributions=(),
                egress_cost=Decimal(0),
                glue_cost=Decimal(0),
                total_cost=Decimal(0),
                assumptions=(
                    *route.assumptions,
                    "same-provider same-region routes have no egress or glue charge",
                ),
            )
        else:
            cross_provider_routes[route.source.provider].append(route)

    used_pools: list[TransferPricingPool] = []
    for provider in Provider:
        provider_routes = cross_provider_routes.get(provider)
        if not provider_routes:
            continue
        pool = pools[provider]
        allocated = allocate_transfer_pool(
            pool,
            provider_routes,
            glue_costs={
                route.segment_id: glue_costs[route.segment_id]
                for route in provider_routes
            },
        )
        charges_by_segment.update(
            {charge.route.segment_id: charge for charge in allocated}
        )
        used_pools.append(pool)

    ordered_charges = tuple(
        charges_by_segment[workload.segment_id] for workload in workloads
    )
    layer_cost = sum(
        (assignment.cost for assignment in assignments),
        Decimal(0),
    )
    transfer_cost = sum(
        (charge.total_cost for charge in ordered_charges),
        Decimal(0),
    )
    candidate_id = "|".join(
        assignment.provider.value for assignment in assignments
    )
    return CompletePathEvaluation(
        candidate_id=candidate_id,
        assignments=assignments,
        transfer_charges=ordered_charges,
        pricing_pools=tuple(used_pools),
        layer_cost=layer_cost,
        transfer_cost=transfer_cost,
        total_cost=layer_cost + transfer_cost,
    )


def _allocate_glue_costs(
    routes: Sequence[TransferRouteIntent],
    workloads: Mapping[str, BaselineEdgeWorkload],
    glue_cost_resolver: GlueCostResolver,
    glue_cost_cache: dict[tuple[Provider, Decimal], Decimal],
) -> dict[str, Decimal]:
    routes_by_destination: dict[Provider, list[TransferRouteIntent]] = defaultdict(
        list
    )
    for route in routes:
        if route.route_class == TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET:
            routes_by_destination[route.destination.provider].append(route)

    costs: dict[str, Decimal] = {}
    for provider in Provider:
        cumulative_invocations = Decimal(0)
        cumulative_cost = Decimal(0)
        for route in routes_by_destination.get(provider, ()):
            cumulative_invocations += workloads[route.segment_id].glue_invocations
            cache_key = (provider, cumulative_invocations)
            try:
                next_cost = glue_cost_cache[cache_key]
            except KeyError:
                next_cost = _decimal(
                    glue_cost_resolver(provider, cumulative_invocations),
                    f"{provider.value}.glue_cost",
                )
                glue_cost_cache[cache_key] = next_cost
            if next_cost < cumulative_cost:
                raise TransferPricingContractError(
                    "TRANSFER_GLUE_COST_INVALID",
                    "aggregate glue cost must be monotonic",
                )
            costs[route.segment_id] = next_cost - cumulative_cost
            cumulative_cost = next_cost
    return costs


def _endpoint_payload(endpoint: TransferEndpoint) -> dict[str, str]:
    return {
        "layer": endpoint.layer.name,
        "provider": endpoint.provider.value,
        "region": endpoint.region,
        "geography": endpoint.geography.value,
    }


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite non-negative number")
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} must be a finite non-negative number"
        ) from exc
    if not normalized.is_finite() or normalized < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return normalized


def _decimal_json(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)
