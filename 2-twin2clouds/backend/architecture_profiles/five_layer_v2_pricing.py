"""Versioned live-catalog pricing adapter for Five-layer v2.

The adapter contains formulas, never provider prices. Every rate is supplied by
the exact immutable provider pricing snapshots selected for a calculation.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .diagnostics import ArchitectureResolutionError
from .five_layer_v2_costing import (
    FORMULA_REF,
    ExpectedRouteOwner,
    expected_route_owners,
    selection_digest,
)
from .five_layer_v2_workload import ResolvedFiveLayerV2Workload


RATE_CARD_KEY = "fiveLayerV2"
RATE_CARD_SCHEMA_VERSION = "five-layer-v2-rate-card.v2"
_ROUTE_UNITS = {
    "source_runtime": "requests/month",
    "destination_operations": "operations/month",
    "cross_cloud_egress_bytes": "bytes/month",
}
_SOURCE_ROUTE_DIMENSIONS = frozenset({"source_runtime", "cross_cloud_egress_bytes"})
_DESTINATION_ROUTE_DIMENSIONS = frozenset({"destination_operations"})
_RATE_CARD_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "pricing_registry"
    / "five_layer_v2_rate_card.schema.json"
)


def _fail(field: str, message: str) -> None:
    raise ArchitectureResolutionError(
        "ARCH_PRICING_EVIDENCE_MISSING",
        field,
        message,
    )


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        _fail(field, "Pricing values must be decimal strings")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            field,
            "Pricing values must be decimal strings",
        ) from exc
    if not result.is_finite() or result < 0:
        _fail(field, "Pricing values must be finite and non-negative")
    return result


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal(1)))
    return format(normalized, "f")


def _only_keys(value: Mapping[str, Any], keys: set[str], field: str) -> None:
    if set(value) != keys:
        _fail(field, f"Expected exactly {sorted(keys)}")


@lru_cache(maxsize=1)
def _rate_card_validator() -> Draft202012Validator:
    try:
        schema = json.loads(_RATE_CARD_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Five-layer v2 rate-card schema is unavailable") from exc
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _rate_card(
    pricing: Mapping[str, Any],
    *,
    provider: str,
) -> Mapping[str, Any]:
    raw = pricing.get(RATE_CARD_KEY)
    if not isinstance(raw, Mapping):
        _fail(
            f"pricing.{provider}.{RATE_CARD_KEY}",
            "Published catalog has no Five-layer v2 rate card",
        )
    errors = sorted(
        _rate_card_validator().iter_errors(raw),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "$"
        _fail(
            f"pricing.{provider}.{RATE_CARD_KEY}.{path}",
            errors[0].message,
        )
    _only_keys(
        raw,
        {
            "schemaVersion",
            "baseCurrency",
            "currencyConversions",
            "formulaReference",
            "componentRates",
            "routeRates",
        },
        f"pricing.{provider}.{RATE_CARD_KEY}",
    )
    if (
        raw["schemaVersion"] != RATE_CARD_SCHEMA_VERSION
        or raw["baseCurrency"] != "USD"
        or raw["formulaReference"] != FORMULA_REF
        or not isinstance(raw["currencyConversions"], Mapping)
        or not isinstance(raw["componentRates"], Mapping)
        or not isinstance(raw["routeRates"], Mapping)
    ):
        _fail(
            f"pricing.{provider}.{RATE_CARD_KEY}",
            "Rate-card identity, currency, or collections are invalid",
        )
    return raw


def _currency_rate(
    card: Mapping[str, Any],
    *,
    provider: str,
    currency: str,
) -> Decimal:
    conversions = card["currencyConversions"]
    if currency not in {"USD", "EUR"} or currency not in conversions:
        _fail(
            f"pricing.{provider}.{RATE_CARD_KEY}.currencyConversions.{currency}",
            "Requested result currency has no pinned conversion rate",
        )
    rate = _decimal(
        conversions[currency],
        f"pricing.{provider}.{RATE_CARD_KEY}.currencyConversions.{currency}",
    )
    if rate <= 0:
        _fail(
            f"pricing.{provider}.{RATE_CARD_KEY}.currencyConversions.{currency}",
            "Currency conversion rate must be positive",
        )
    return rate


def _dimension_map(
    dimensions: object,
    *,
    field: str,
) -> dict[str, tuple[Decimal | str, str]]:
    if not isinstance(dimensions, list):
        _fail(field, "Dimensions must be a list")
    result: dict[str, tuple[Decimal | str, str]] = {}
    for item in dimensions:
        if not isinstance(item, Mapping):
            _fail(field, "Dimension entries must be objects")
        dimension_id = str(item.get("dimension_id", "")).rsplit(".", 1)[-1]
        unit = str(item.get("unit", ""))
        raw_value = item.get("value")
        if dimension_id in result or not dimension_id or not unit:
            _fail(field, "Dimension identities must be unique and complete")
        if unit == "enum":
            if not isinstance(raw_value, str) or not raw_value:
                _fail(field, "Enum dimensions must contain a string")
            result[dimension_id] = (raw_value, unit)
        else:
            result[dimension_id] = (
                _decimal(raw_value, f"{field}.{dimension_id}"),
                unit,
            )
    return result


def _matching_variant(
    variants: object,
    dimensions: Mapping[str, tuple[Decimal | str, str]],
    *,
    field: str,
) -> Mapping[str, Any]:
    if not isinstance(variants, list) or not variants:
        _fail(field, "At least one pricing variant is required")
    matches: list[Mapping[str, Any]] = []
    for index, variant in enumerate(variants):
        variant_field = f"{field}[{index}]"
        if not isinstance(variant, Mapping):
            _fail(variant_field, "Pricing variant must be an object")
        _only_keys(
            variant,
            {"selectors", "meters", "nonBillableDimensions"},
            variant_field,
        )
        selectors = variant["selectors"]
        if not isinstance(selectors, Mapping):
            _fail(f"{variant_field}.selectors", "Selectors must be an object")
        if all(
            key in dimensions and str(dimensions[key][0]) == str(expected)
            for key, expected in selectors.items()
        ):
            matches.append(variant)
    if len(matches) != 1:
        _fail(field, "Exactly one pricing variant must match the selection")
    return matches[0]


def _tiered_amount(
    quantity: Decimal,
    meter: Mapping[str, Any],
    *,
    field: str,
) -> Decimal:
    _only_keys(
        meter,
        {
            "dimension",
            "unit",
            "billingIncrement",
            "freeQuantity",
            "minimumCharge",
            "tiers",
        },
        field,
    )
    increment = _decimal(meter["billingIncrement"], f"{field}.billingIncrement")
    if increment <= 0:
        _fail(f"{field}.billingIncrement", "Billing increment must be positive")
    free = _decimal(meter["freeQuantity"], f"{field}.freeQuantity")
    minimum = _decimal(meter["minimumCharge"], f"{field}.minimumCharge")
    billable = max(Decimal(0), quantity - free)
    billable = (billable / increment).to_integral_value(
        rounding=ROUND_CEILING
    ) * increment
    tiers = meter["tiers"]
    if not isinstance(tiers, list) or not tiers:
        _fail(f"{field}.tiers", "At least one pricing tier is required")
    previous = Decimal(0)
    amount = Decimal(0)
    for index, tier in enumerate(tiers):
        tier_field = f"{field}.tiers[{index}]"
        if not isinstance(tier, Mapping):
            _fail(tier_field, "Pricing tier must be an object")
        _only_keys(tier, {"upTo", "pricePerUnit"}, tier_field)
        price = _decimal(tier["pricePerUnit"], f"{tier_field}.pricePerUnit")
        raw_upper = tier["upTo"]
        if raw_upper is None:
            if index != len(tiers) - 1:
                _fail(tier_field, "Only the final tier may be unbounded")
            upper = billable
        else:
            upper = _decimal(raw_upper, f"{tier_field}.upTo")
            if upper <= previous:
                _fail(tier_field, "Tier upper bounds must increase")
        amount += max(Decimal(0), min(billable, upper) - previous) * price
        previous = upper
        if previous >= billable:
            break
    if previous < billable:
        _fail(f"{field}.tiers", "Pricing tiers do not cover the billed quantity")
    return max(amount, minimum)


def _evaluate_variant(
    variant: Mapping[str, Any],
    dimensions: Mapping[str, tuple[Decimal | str, str]],
    *,
    expected_dimensions: frozenset[str],
    field: str,
) -> Decimal:
    meters = variant["meters"]
    non_billable = variant["nonBillableDimensions"]
    if not isinstance(meters, list) or not isinstance(non_billable, Mapping):
        _fail(field, "Meters and non-billable dimensions are required")
    billed_ids = [
        str(meter.get("dimension", ""))
        for meter in meters
        if isinstance(meter, Mapping)
    ]
    ignored_ids = [str(item) for item in non_billable]
    if (
        len(billed_ids) != len(set(billed_ids))
        or set(billed_ids) & set(ignored_ids)
        or set(billed_ids) | set(ignored_ids) != set(expected_dimensions)
        or set(expected_dimensions) != set(dimensions)
        or any(
            not isinstance(reason, str) or not reason.strip()
            for reason in non_billable.values()
        )
    ):
        _fail(field, "Every expected dimension must have exactly one price owner")
    amount = Decimal(0)
    for index, meter in enumerate(meters):
        meter_field = f"{field}.meters[{index}]"
        if not isinstance(meter, Mapping):
            _fail(meter_field, "Meter must be an object")
        dimension_id = str(meter.get("dimension", ""))
        quantity, unit = dimensions[dimension_id]
        if isinstance(quantity, str) or meter.get("unit") != unit:
            _fail(meter_field, "Meter unit or dimension type does not match")
        amount += _tiered_amount(quantity, meter, field=meter_field)
    return amount


def _price_component(
    card: Mapping[str, Any],
    selection: Mapping[str, Any],
    *,
    provider: str,
) -> Decimal:
    component_id = str(selection["implementation_component_id"])
    raw = card["componentRates"].get(component_id)
    field = f"pricing.{provider}.{RATE_CARD_KEY}.componentRates.{component_id}"
    if not isinstance(raw, Mapping) or set(raw) != {"variants"}:
        _fail(field, "Selected component has no strict rate card")
    dimensions = _dimension_map(selection["dimensions"], field=field)
    variant = _matching_variant(raw["variants"], dimensions, field=field)
    return _evaluate_variant(
        variant,
        dimensions,
        expected_dimensions=frozenset(dimensions),
        field=field,
    )


def _route_dimensions(
    route: ExpectedRouteOwner,
    workload: ResolvedFiveLayerV2Workload,
) -> dict[str, tuple[Decimal, str]]:
    scenario = workload.eventing_scenario
    core = workload.workload
    month_seconds = Decimal("2592000")
    interval_seconds = Decimal(str(core["deviceSendingIntervalInMinutes"])) * 60
    messages = (
        Decimal(int(core["numberOfDevices"])) * month_seconds / interval_seconds
    ).to_integral_value(rounding=ROUND_CEILING)
    payload_bytes = Decimal(str(core["averageSizeOfMessageInKb"])) * 1024
    event_attempts = (
        Decimal(int(scenario["events_per_month"]))
        * (
            Decimal(1)
            + Decimal(str(scenario["retry_share"]))
            + Decimal(str(scenario["replay_share"]))
        )
    ).to_integral_value(rounding=ROUND_CEILING)
    if route.route_class == "domain_event_cross_cloud":
        operations = event_attempts * len(route.domain_flow_ids)
        egress_bytes = operations * int(scenario["average_event_payload_bytes"])
    elif route.route_class == "twin_projection_cross_cloud":
        operations = (
            (
                Decimal(str(core["twinStateMaterializationsPerSecond"]))
                + Decimal(str(core["twinGraphUpdatesPerSecond"]))
            )
            * month_seconds
        ).to_integral_value(rounding=ROUND_CEILING)
        egress_bytes = operations * payload_bytes
    elif route.route_class in {
        "storage_hot_to_cool_cross_cloud",
        "storage_cool_to_archive_cross_cloud",
    }:
        operations = Decimal(8640)
        egress_bytes = messages * payload_bytes
    else:
        _fail(route.cost_owner_id, "Route class has no pricing quantity formula")
    return {
        "source_runtime": (operations, _ROUTE_UNITS["source_runtime"]),
        "destination_operations": (
            operations,
            _ROUTE_UNITS["destination_operations"],
        ),
        "cross_cloud_egress_bytes": (
            egress_bytes,
            _ROUTE_UNITS["cross_cloud_egress_bytes"],
        ),
    }


def _price_route_role(
    card: Mapping[str, Any],
    route: ExpectedRouteOwner,
    dimensions: Mapping[str, tuple[Decimal, str]],
    *,
    provider: str,
    role: str,
) -> Decimal:
    raw = card["routeRates"].get(route.route_class)
    field = (
        f"pricing.{provider}.{RATE_CARD_KEY}.routeRates."
        f"{route.route_class}.{role}Variants"
    )
    key = f"{role}Variants"
    if not isinstance(raw, Mapping) or set(raw) != {
        "sourceVariants",
        "destinationVariants",
    }:
        _fail(field, "Cross-cloud route has no strict role rate card")
    role_dimensions = (
        _SOURCE_ROUTE_DIMENSIONS if role == "source" else _DESTINATION_ROUTE_DIMENSIONS
    )
    selected_dimensions = {
        dimension_id: dimensions[dimension_id] for dimension_id in role_dimensions
    }
    variant = _matching_variant(raw[key], selected_dimensions, field=field)
    return _evaluate_variant(
        variant,
        selected_dimensions,
        expected_dimensions=role_dimensions,
        field=field,
    )


def _allocate(amount: Decimal, item_ids: tuple[str, ...]) -> list[dict[str, str]]:
    if not item_ids:
        _fail("route.allocations", "Route cost requires an allocation owner")
    share = amount / len(item_ids)
    allocations = []
    allocated = Decimal(0)
    for index, item_id in enumerate(item_ids):
        value = amount - allocated if index == len(item_ids) - 1 else share
        allocated += value
        allocations.append({"item_id": item_id, "monthly_amount": _decimal_text(value)})
    return allocations


class FiveLayerV2CatalogCostLedgerResolver:
    """Build exact candidate ledgers from immutable provider rate cards."""

    def __init__(self, pricing_by_provider: Mapping[str, Mapping[str, Any]]) -> None:
        self._pricing = pricing_by_provider

    def resolve(
        self,
        specification: Mapping[str, Any],
        assignment: Mapping[str, str],
        workload: ResolvedFiveLayerV2Workload,
    ) -> Mapping[str, Any]:
        currency = str(specification["currency"])
        evidence = {
            str(item["provider"]): str(item["digest"])
            for item in specification["optimization_context"]["pricing_evidence_refs"]
        }
        cards = {
            provider: _rate_card(
                self._pricing.get(provider, {}),
                provider=provider,
            )
            for provider in evidence
        }
        currency_rates = {
            provider: _currency_rate(
                card,
                provider=provider,
                currency=currency,
            )
            for provider, card in cards.items()
        }
        if len(set(currency_rates.values())) != 1:
            _fail(
                f"pricing.{RATE_CARD_KEY}.currencyConversions.{currency}",
                "Provider rate cards disagree on the pinned currency conversion",
            )
        component_costs = []
        for selection in specification["component_selections"]:
            provider = str(selection["provider"])
            component_id = str(selection["implementation_component_id"])
            amount = (
                _price_component(cards[provider], selection, provider=provider)
                * currency_rates[provider]
            )
            component_costs.append(
                {
                    "component_id": component_id,
                    "cost_owner_id": f"cost::{component_id}",
                    "selection_digest": selection_digest(selection),
                    "formula_reference": FORMULA_REF,
                    "pricing_evidence_digest": evidence[provider],
                    "monthly_amount": _decimal_text(amount),
                }
            )
        route_costs = []
        for route in expected_route_owners(assignment, workload):
            dimensions = _route_dimensions(route, workload)
            amount = (
                _price_route_role(
                    cards[route.source_provider],
                    route,
                    dimensions,
                    provider=route.source_provider,
                    role="source",
                )
                * currency_rates[route.source_provider]
                + _price_route_role(
                    cards[route.destination_provider],
                    route,
                    dimensions,
                    provider=route.destination_provider,
                    role="destination",
                )
                * currency_rates[route.destination_provider]
            )
            route_costs.append(
                {
                    "cost_owner_id": route.cost_owner_id,
                    "route_class": route.route_class,
                    "pair": route.pair,
                    "domain_flow_ids": list(route.domain_flow_ids),
                    "workload_digest": route.workload_digest,
                    "formula_reference": FORMULA_REF,
                    "pricing_evidence_digests": {
                        "source": evidence[route.source_provider],
                        "destination": evidence[route.destination_provider],
                    },
                    "monthly_amount": _decimal_text(amount),
                    "allocations": _allocate(
                        amount,
                        route.allocation_item_ids,
                    ),
                }
            )
        return {
            "schema_version": "five-layer-v2-cost-ledger.v1",
            "currency": currency,
            "component_costs": component_costs,
            "route_costs": route_costs,
        }

    def __call__(
        self,
        specification: Mapping[str, Any],
        assignment: Mapping[str, str],
        workload: ResolvedFiveLayerV2Workload,
    ) -> Mapping[str, Any]:
        return self.resolve(specification, assignment, workload)


def build_five_layer_v2_catalog_cost_ledger_resolver(
    pricing_by_provider: Mapping[str, Mapping[str, Any]],
) -> Callable[
    [Mapping[str, Any], Mapping[str, str], ResolvedFiveLayerV2Workload],
    Mapping[str, Any],
]:
    return FiveLayerV2CatalogCostLedgerResolver(pricing_by_provider)
