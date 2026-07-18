"""Validate Optimizer route evidence at the Management trust boundary."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from src.schemas.optimizer_transfer_pricing import (
    OptimizerPathDiagnostics,
    OptimizerTransitionRuntimeContext,
    OptimizerTransferPool,
    OptimizerTransferPricingContext,
    OptimizerTransferRoute,
)
from src.schemas.pricing_catalog import PricingCatalogContext
from src.services.errors import OptimizerContractError


EXPECTED_EDGES = {
    "L1_to_L2": ("L1", "L2", "L1_INGESTION", "L2_PROCESSING"),
    "L2_to_L3_hot": (
        "L2",
        "L3_hot",
        "L2_PROCESSING",
        "L3_HOT_STORAGE",
    ),
    "L3_hot_to_L3_cool": (
        "L3_hot",
        "L3_cool",
        "L3_HOT_STORAGE",
        "L3_COOL_STORAGE",
    ),
    "L3_cool_to_L3_archive": (
        "L3_cool",
        "L3_archive",
        "L3_COOL_STORAGE",
        "L3_ARCHIVE_STORAGE",
    ),
    "L3_hot_to_L4": (
        "L3_hot",
        "L4",
        "L3_HOT_STORAGE",
        "L4_TWIN_MANAGEMENT",
    ),
    "L4_to_L5": (
        "L4",
        "L5",
        "L4_TWIN_MANAGEMENT",
        "L5_VISUALIZATION",
    ),
}
PROVIDER_POLICY = {
    "aws": {
        "network_tier": "provider_default",
        "billing_scope": "account_aggregate_public_egress",
        "billing_unit": "gb",
        "bytes_per_billing_unit": 1_000_000_000,
    },
    "azure": {
        "network_tier": "microsoft_premium_global_network",
        "billing_scope": "account_aggregate_public_egress",
        "billing_unit": "gb",
        "bytes_per_billing_unit": 1_000_000_000,
    },
    "gcp": {
        "network_tier": "premium",
        "billing_scope": "sku_account_aggregate_public_egress",
        "billing_unit": "gib",
        "bytes_per_billing_unit": 1_073_741_824,
    },
}
_PROVIDER_LABELS = {"AWS": "aws", "Azure": "azure", "GCP": "gcp"}


@dataclass(frozen=True)
class ValidatedOptimizerTransferPricing:
    """Typed route context and solver diagnostics accepted by Management."""

    context: OptimizerTransferPricingContext
    transition_context: OptimizerTransitionRuntimeContext
    diagnostics: OptimizerPathDiagnostics


def validate_optimizer_transfer_pricing_result(
    result: dict[str, Any],
    expected_catalog_context: PricingCatalogContext,
) -> ValidatedOptimizerTransferPricing:
    """Fail closed unless route evidence matches the trusted calculation input."""

    errors: list[dict[str, str]] = []
    context = _parse_model(
        OptimizerTransferPricingContext,
        result.get("transferPricingContext"),
        "transferPricingContext",
        errors,
    )
    diagnostics = _parse_model(
        OptimizerPathDiagnostics,
        result.get("optimizationDiagnostics"),
        "optimizationDiagnostics",
        errors,
    )
    transition_context = _parse_model(
        OptimizerTransitionRuntimeContext,
        result.get("transitionRuntimeContext"),
        "transitionRuntimeContext",
        errors,
    )
    if (
        context is None
        or transition_context is None
        or diagnostics is None
    ):
        _raise_contract_error(errors)

    selected = _selected_providers(result.get("calculationResult"), errors)
    routes_by_segment = {route.segment_id: route for route in context.routes}
    if set(routes_by_segment) != set(EXPECTED_EDGES):
        _add_error(
            errors,
            "transferPricingContext.routes",
            "Routes must contain the exact six baseline segments",
        )

    pools_by_id = {pool.pool_id: pool for pool in context.pools}
    cross_routes: list[OptimizerTransferRoute] = []
    for segment_id, edge in EXPECTED_EDGES.items():
        route = routes_by_segment.get(segment_id)
        if route is None:
            continue
        _validate_route(
            route,
            edge=edge,
            selected=selected,
            expected_catalog_context=expected_catalog_context,
            pools_by_id=pools_by_id,
            errors=errors,
        )
        if route.route_class == "cross_provider_public_internet":
            cross_routes.append(route)

    _validate_pools(
        context.pools,
        cross_routes,
        expected_catalog_context,
        errors,
    )
    _validate_transfer_costs(result.get("transferCosts"), cross_routes, errors)
    _validate_transition_runtimes(
        result,
        transition_context,
        selected,
        routes_by_segment,
        errors,
    )
    _validate_result_currency(
        result,
        context,
        transition_context,
        diagnostics,
        errors,
    )
    _validate_diagnostics(
        result,
        diagnostics,
        selected,
        cross_routes,
        transition_context,
        errors,
    )
    if errors:
        _raise_contract_error(errors)
    return ValidatedOptimizerTransferPricing(
        context=context,
        transition_context=transition_context,
        diagnostics=diagnostics,
    )


def _validate_route(
    route: OptimizerTransferRoute,
    *,
    edge: tuple[str, str, str, str],
    selected: dict[str, str],
    expected_catalog_context: PricingCatalogContext,
    pools_by_id: dict[str, OptimizerTransferPool],
    errors: list[dict[str, str]],
) -> None:
    source_key, destination_key, source_layer, destination_layer = edge
    field = f"transferPricingContext.routes.{route.segment_id}"
    if (
        route.source.layer != source_layer
        or route.destination.layer != destination_layer
    ):
        _add_error(
            errors,
            field,
            "Route endpoints do not match the baseline segment topology",
        )
    if (
        route.source.provider != selected.get(source_key)
        or route.destination.provider != selected.get(destination_key)
    ):
        _add_error(
            errors,
            field,
            "Route providers do not match the selected complete path",
        )
    for endpoint_name, endpoint in (
        ("source", route.source),
        ("destination", route.destination),
    ):
        expected_region = expected_catalog_context.catalogs[
            endpoint.provider
        ].pricing_region
        if endpoint.region != expected_region:
            _add_error(
                errors,
                f"{field}.{endpoint_name}.region",
                "Route region does not match the trusted catalog context",
            )

    same_provider = route.source.provider == route.destination.provider
    if same_provider:
        if route.route_class != "same_provider_same_region":
            _add_error(
                errors,
                f"{field}.routeClass",
                "Same-provider baseline endpoints require same-region routing",
            )
        if route.source.region != route.destination.region:
            _add_error(
                errors,
                field,
                "Same-provider baseline endpoints must use the same region",
            )
        if route.network_tier != "not_applicable":
            _add_error(
                errors,
                f"{field}.networkTier",
                "Same-provider routes must not claim a network tier",
            )
        if any(
            value is not None
            for value in (
                route.pool_id,
                route.catalog_snapshot_id,
                route.evidence_id,
            )
        ) or route.tier_contributions:
            _add_error(
                errors,
                field,
                "Zero-cost same-provider routes must not claim pricing evidence",
            )
        if any(
            not _close(value, Decimal(0))
            for value in (
                route.egress_cost,
                route.glue_cost,
                route.total_cost,
            )
        ):
            _add_error(
                errors,
                field,
                "Same-provider same-region routes must be zero cost",
            )
        return

    if route.route_class != "cross_provider_public_internet":
        _add_error(
            errors,
            f"{field}.routeClass",
            "Cross-provider endpoints require public internet routing",
        )
    policy = PROVIDER_POLICY[route.source.provider]
    if route.network_tier != policy["network_tier"]:
        _add_error(
            errors,
            f"{field}.networkTier",
            "Route network tier does not match the source-provider policy",
        )
    reference = expected_catalog_context.catalogs[route.source.provider]
    if route.catalog_snapshot_id != reference.snapshot_id:
        _add_error(
            errors,
            f"{field}.catalogSnapshotId",
            "Route snapshot does not match the trusted source catalog",
        )
    if not route.pool_id or route.pool_id not in pools_by_id:
        _add_error(
            errors,
            f"{field}.poolId",
            "Cross-provider route must reference a returned pricing pool",
        )
        return
    pool = pools_by_id[route.pool_id]
    if (
        route.source.provider != pool.provider
        or route.network_tier != pool.network_tier
        or route.catalog_snapshot_id != pool.catalog_snapshot_id
        or route.evidence_id != pool.evidence_id
    ):
        _add_error(
            errors,
            field,
            "Route pricing identity does not match its billing pool",
        )


def _validate_pools(
    pools: tuple[OptimizerTransferPool, ...],
    cross_routes: list[OptimizerTransferRoute],
    expected_catalog_context: PricingCatalogContext,
    errors: list[dict[str, str]],
) -> None:
    routes_by_pool: dict[str, list[OptimizerTransferRoute]] = {}
    for route in cross_routes:
        if route.pool_id:
            routes_by_pool.setdefault(route.pool_id, []).append(route)
    if {pool.pool_id for pool in pools} != set(routes_by_pool):
        _add_error(
            errors,
            "transferPricingContext.pools",
            "Pricing pools must exactly match pools used by cross-provider routes",
        )

    for pool in pools:
        field = f"transferPricingContext.pools.{pool.pool_id}"
        policy = PROVIDER_POLICY[pool.provider]
        reference = expected_catalog_context.catalogs[pool.provider]
        if (
            pool.network_tier != policy["network_tier"]
            or pool.billing_scope != policy["billing_scope"]
            or pool.billing_unit != policy["billing_unit"]
            or pool.bytes_per_billing_unit != policy["bytes_per_billing_unit"]
        ):
            _add_error(
                errors,
                field,
                "Pricing pool does not match the source-provider billing policy",
            )
        if pool.catalog_snapshot_id != reference.snapshot_id:
            _add_error(
                errors,
                f"{field}.catalogSnapshotId",
                "Pricing pool snapshot does not match the trusted source catalog",
            )
        routes = routes_by_pool.get(pool.pool_id, [])
        volume = sum((route.volume_bytes for route in routes), Decimal(0))
        egress = sum((route.egress_cost for route in routes), Decimal(0))
        if not _close(pool.aggregate_volume_bytes, volume):
            _add_error(
                errors,
                f"{field}.aggregateVolumeBytes",
                "Aggregate pool volume does not match its routes",
            )
        if not _close(pool.aggregate_egress_cost, egress):
            _add_error(
                errors,
                f"{field}.aggregateEgressCost",
                "Aggregate pool cost does not match its routes",
            )
        _validate_pool_tier_allocation(
            pool,
            routes,
            field,
            errors,
        )


def _validate_pool_tier_allocation(
    pool: OptimizerTransferPool,
    routes: list[OptimizerTransferRoute],
    field: str,
    errors: list[dict[str, str]],
) -> None:
    """Require marginal tier rows to cover the pool's billed quantity exactly."""

    consumed = Decimal(0)
    allocation_valid = True
    for route in routes:
        route_quantity = route.volume_bytes / Decimal(
            pool.bytes_per_billing_unit
        )
        contributions = route.tier_contributions
        if _close(route_quantity, Decimal(0)):
            if contributions:
                allocation_valid = False
            continue
        if not contributions:
            allocation_valid = False
            consumed += route_quantity
            continue

        cursor = consumed
        for contribution in contributions:
            if not _close(contribution.from_quantity, cursor):
                allocation_valid = False
            cursor = contribution.to_quantity
        if not _close(cursor - consumed, route_quantity):
            allocation_valid = False
        consumed += route_quantity

    expected_quantity = pool.aggregate_volume_bytes / Decimal(
        pool.bytes_per_billing_unit
    )
    if not allocation_valid or not _close(consumed, expected_quantity):
        _add_error(
            errors,
            f"{field}.tierContributions",
            (
                "Tier contributions must continuously cover the exact "
                "aggregate billed quantity"
            ),
        )


def _validate_transfer_costs(
    value: Any,
    cross_routes: list[OptimizerTransferRoute],
    errors: list[dict[str, str]],
) -> None:
    if not isinstance(value, dict):
        _add_error(errors, "transferCosts", "Expected a transfer cost object")
        return
    expected = {route.segment_id: route.total_cost for route in cross_routes}
    if set(value) != set(expected):
        _add_error(
            errors,
            "transferCosts",
            "Transfer costs must exactly match charged cross-provider routes",
        )
        return
    for segment_id, expected_cost in expected.items():
        actual = _decimal_or_none(value.get(segment_id))
        if actual is None or not _close(actual, expected_cost):
            _add_error(
                errors,
                f"transferCosts.{segment_id}",
                "Transfer cost does not match exact route evidence",
            )


def _validate_result_currency(
    result: dict[str, Any],
    context: OptimizerTransferPricingContext,
    transition_context: OptimizerTransitionRuntimeContext,
    diagnostics: OptimizerPathDiagnostics,
    errors: list[dict[str, str]],
) -> None:
    currency = result.get("currency")
    if currency != context.currency:
        _add_error(
            errors,
            "transferPricingContext.currency",
            "Transfer currency must match the optimizer result",
        )
    if currency != transition_context.currency:
        _add_error(
            errors,
            "transitionRuntimeContext.currency",
            "Transition runtime currency must match the optimizer result",
        )
    if diagnostics.score_unit != f"{currency}/month":
        _add_error(
            errors,
            "optimizationDiagnostics.scoreUnit",
            "Score unit must match the optimizer result currency",
        )


def _validate_diagnostics(
    result: dict[str, Any],
    diagnostics: OptimizerPathDiagnostics,
    selected: dict[str, str],
    cross_routes: list[OptimizerTransferRoute],
    transition_context: OptimizerTransitionRuntimeContext,
    errors: list[dict[str, str]],
) -> None:
    expected_candidate = "|".join(
        selected.get(layer_key, "")
        for layer_key in (
            "L1",
            "L2",
            "L3_hot",
            "L3_cool",
            "L3_archive",
            "L4",
            "L5",
        )
    )
    if diagnostics.winning_candidate_id != expected_candidate:
        _add_error(
            errors,
            "optimizationDiagnostics.winningCandidateId",
            "Winning candidate does not match calculationResult",
        )
    transfer_total = sum(
        (route.total_cost for route in cross_routes),
        Decimal(0),
    )
    if not _close(diagnostics.winning_transfer_cost, transfer_total):
        _add_error(
            errors,
            "optimizationDiagnostics.winningTransferCost",
            "Winning transfer cost does not match route evidence",
        )
    transition_total = sum(
        (
            transition.mover_runtime_cost
            for transition in transition_context.transitions
        ),
        Decimal(0),
    )
    if not _close(
        diagnostics.winning_transition_runtime_cost,
        transition_total,
    ):
        _add_error(
            errors,
            "optimizationDiagnostics.winningTransitionRuntimeCost",
            "Winning transition cost does not match runtime evidence",
        )
    result_total = _decimal_or_none(result.get("totalCost"))
    if result_total is None or abs(result_total - diagnostics.winning_score) > Decimal(
        "0.01"
    ):
        _add_error(
            errors,
            "optimizationDiagnostics.winningScore",
            "Winning score does not match totalCost",
        )


def _validate_transition_runtimes(
    result: dict[str, Any],
    context: OptimizerTransitionRuntimeContext,
    selected: dict[str, str],
    routes_by_segment: dict[str, OptimizerTransferRoute],
    errors: list[dict[str, str]],
) -> None:
    expected = {
        "l3_hot_to_l3_cool": (
            "L3_hot",
            "L3_cool",
            30,
            "one_daily_source_mover_invocation",
            "L3_hot_to_L3_cool",
        ),
        "l3_cool_to_l3_archive": (
            "L3_cool",
            "L3_archive",
            4,
            "one_weekly_source_mover_invocation",
            "L3_cool_to_L3_archive",
        ),
    }
    runtime_costs = result.get("transitionRuntimeCosts")
    if not isinstance(runtime_costs, dict) or set(runtime_costs) != set(
        expected
    ):
        _add_error(
            errors,
            "transitionRuntimeCosts",
            "Transition costs must contain exactly the two baseline edges",
        )
        runtime_costs = {}

    for transition in context.transitions:
        (
            source_slot,
            destination_slot,
            invocations,
            invocation_basis,
            segment_id,
        ) = expected[transition.edge_id]
        field = (
            "transitionRuntimeContext.transitions."
            f"{transition.edge_id}"
        )
        source_provider = selected.get(source_slot)
        destination_provider = selected.get(destination_slot)
        expected_component = (
            f"transition.{transition.edge_id}."
            f"{source_provider}.runtime"
        )
        if (
            transition.source_slot != source_slot
            or transition.destination_slot != destination_slot
            or transition.source_provider != source_provider
            or transition.destination_provider != destination_provider
            or transition.monthly_invocations != invocations
            or transition.invocation_basis != invocation_basis
            or transition.source_runtime_component_id
            != expected_component
        ):
            _add_error(
                errors,
                field,
                "Transition runtime does not match source-owned topology",
            )

        route = routes_by_segment.get(segment_id)
        if route is not None and (
            not _close(transition.destination_writer_cost, route.glue_cost)
            or not _close(transition.egress_cost, route.egress_cost)
        ):
            _add_error(
                errors,
                field,
                "Transition writer and egress costs do not match route evidence",
            )
        runtime_cost = _decimal_or_none(
            runtime_costs.get(transition.edge_id)
        )
        if runtime_cost is None or not _close(
            runtime_cost,
            transition.mover_runtime_cost,
        ):
            _add_error(
                errors,
                f"transitionRuntimeCosts.{transition.edge_id}",
                "Transition cost does not match source runtime evidence",
            )


def _selected_providers(
    value: Any,
    errors: list[dict[str, str]],
) -> dict[str, str]:
    if not isinstance(value, dict):
        _add_error(errors, "calculationResult", "Expected an object")
        return {}
    l3 = value.get("L3")
    if not isinstance(l3, dict):
        _add_error(errors, "calculationResult.L3", "Expected an object")
        l3 = {}
    raw = {
        "L1": value.get("L1"),
        "L2": value.get("L2"),
        "L3_hot": l3.get("Hot"),
        "L3_cool": l3.get("Cool"),
        "L3_archive": l3.get("Archive"),
        "L4": value.get("L4"),
        "L5": value.get("L5"),
    }
    selected = {}
    for layer_key, label in raw.items():
        provider = _PROVIDER_LABELS.get(label) if isinstance(label, str) else None
        if provider is None:
            _add_error(
                errors,
                f"calculationResult.{layer_key}",
                "Selected provider is invalid",
            )
        else:
            selected[layer_key] = provider
    return selected


def _parse_model(model_type, value, field, errors):
    try:
        return model_type.model_validate(value)
    except ValidationError as exc:
        for item in exc.errors(include_url=False)[:25]:
            location = tuple(item.get("loc") or ())
            if item.get("type") == "extra_forbidden" and location:
                location = location[:-1]
            suffix = ".".join(str(part) for part in location)
            _add_error(
                errors,
                f"{field}.{suffix}".rstrip("."),
                str(item.get("msg") or "Invalid value"),
            )
        return None


def _decimal_or_none(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, Decimal),
    ):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def _add_error(
    errors: list[dict[str, str]],
    field: str,
    message: str,
) -> None:
    if len(errors) < 50:
        errors.append({"field": field, "message": message})


def _raise_contract_error(errors: list[dict[str, str]]) -> None:
    raise OptimizerContractError(
        "Optimizer transfer pricing contract is invalid.",
        errors,
    )
