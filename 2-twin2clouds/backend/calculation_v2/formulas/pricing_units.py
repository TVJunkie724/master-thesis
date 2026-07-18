"""
Unit and tier helpers for provider pricing calculations.

Provider APIs frequently return prices in billing blocks such as 1K, 10K,
100K, or 1M operations. Calculators should convert those values at the
boundary and then multiply only normalized per-unit prices by workload values.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any


@dataclass(frozen=True, slots=True)
class CapacityTierSelection:
    """Exact provider capacity tier selected for a monthly workload."""

    tier_id: str
    sku: str
    capacity: int
    billable_quantity: float
    included_quantity_per_unit: float
    unit_price: float
    total_cost: float


def unit_price(raw_price: float | int | str | None, source_quantity: float = 1.0) -> float:
    """Convert a provider block price into a normalized price per one unit."""
    if raw_price is None:
        return 0.0
    quantity = float(source_quantity)
    if quantity <= 0:
        raise ValueError("source_quantity must be greater than zero")
    return float(raw_price) / quantity


def first_unit_price(
    pricing: Mapping[str, Any],
    candidates: Iterable[tuple[str, float]],
    *,
    default: float = 0.0,
) -> float:
    """
    Return the first available pricing key normalized to one unit.

    candidates contains `(key, source_quantity)` pairs. For example, a value in
    `pricePer1kRequests` should use `source_quantity=1000`.
    """
    for key, source_quantity in candidates:
        if key in pricing and pricing[key] is not None:
            return unit_price(pricing[key], source_quantity)
    return float(default)


def required_first_unit_price(
    pricing: Mapping[str, Any],
    candidates: Iterable[tuple[str, float]],
    *,
    label: str,
) -> float:
    """Return a normalized unit price or fail when no candidate key is present."""
    candidate_list = tuple(candidates)
    for key, source_quantity in candidate_list:
        if key in pricing and pricing[key] is not None:
            return unit_price(pricing[key], source_quantity)
    keys = ", ".join(key for key, _ in candidate_list)
    raise ValueError(f"Missing required pricing field for {label}: one of {keys}")


def billable_1kb_units(item_count: float, average_size_kb: float) -> float:
    """Return billable one-KB units using a ceiling increment per item."""
    return billable_block_units(
        item_count,
        average_size_kb,
        block_size_kb=1.0,
    )


def billable_block_units(
    item_count: float,
    average_size_kb: float,
    *,
    block_size_kb: float,
) -> float:
    """Return billable units using a provider-specific size block per item."""

    count = _finite_non_negative("item_count", item_count)
    if count == 0:
        return 0.0

    size = _finite_positive("average_size_kb", average_size_kb)
    block_size = _finite_positive("block_size_kb", block_size_kb)
    try:
        increment = int(
            (Decimal(str(size)) / Decimal(str(block_size))).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
    except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
        raise ValueError(
            "message size and billing block must be finite positive numbers"
        ) from exc
    return count * max(1, increment)


def capacity_tier_cost(
    quantity: float,
    tiers: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    included_quantity_key: str = "threshold",
    limit_key: str = "limit",
    price_key: str = "price",
    minimum_paid_units: int = 1,
) -> float:
    """
    Calculate cheapest unit-tier cost for services sold as monthly units.

    This fits Azure IoT Hub-style pricing: every paid tier has a monthly unit
    price and an included message capacity per unit. The implementation chooses
    the cheapest valid tier for the requested quantity.
    """
    usage = _finite_non_negative("quantity", quantity)
    if usage == 0:
        return 0.0

    return select_capacity_tier(
        usage,
        tiers,
        included_quantity_key=included_quantity_key,
        limit_key=limit_key,
        price_key=price_key,
        minimum_paid_units=minimum_paid_units,
    ).total_cost


def select_capacity_tier(
    quantity: float,
    tiers: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    tier_skus: Mapping[str, str] | None = None,
    maximum_units_by_sku: Mapping[str, int] | None = None,
    quantity_by_sku: Mapping[str, float] | None = None,
    included_quantity_key: str = "threshold",
    limit_key: str = "limit",
    price_key: str = "price",
    minimum_paid_units: int = 1,
) -> CapacityTierSelection:
    """Return the cheapest valid tier together with its exact SKU and capacity."""

    usage = _finite_positive("quantity", quantity)
    if (
        isinstance(minimum_paid_units, bool)
        or not isinstance(minimum_paid_units, int)
        or minimum_paid_units < 1
    ):
        raise ValueError("minimum_paid_units must be a positive integer")

    sku_map = dict(tier_skus or {})
    maximums = dict(maximum_units_by_sku or {})
    quantities = dict(quantity_by_sku or {})
    candidates: list[CapacityTierSelection] = []
    for tier_id, tier in _named_tier_items(tiers):
        sku = str(sku_map.get(tier_id) or tier.get("sku") or tier_id)
        if not sku:
            raise ValueError(f"pricing tier {tier_id!r} has no stable SKU")
        candidate_usage = _finite_positive(
            f"quantity_by_sku[{sku}]",
            quantities.get(sku, usage),
        )

        price = _to_float(tier.get(price_key), 0.0)
        limit = _normalize_limit(tier.get(limit_key))
        if price == 0:
            included_quantity = _first_positive_value(
                tier,
                included_quantity_key,
                "messagesPerUnit",
                "includedMessagesPerUnit",
                limit_key,
            )
        else:
            included_quantity = _to_float(
                _first_present(
                    tier,
                    included_quantity_key,
                    "messagesPerUnit",
                    "includedMessagesPerUnit",
                    limit_key,
                ),
                0.0,
            )
        if included_quantity <= 0:
            continue

        if price == 0:
            if candidate_usage > included_quantity:
                continue
            units = 1
        elif price > 0:
            if sku not in maximums and candidate_usage > limit:
                continue
            units = max(
                int(math.ceil(candidate_usage / included_quantity)),
                minimum_paid_units,
            )
        else:
            continue

        maximum_units = maximums.get(sku)
        if maximum_units is not None:
            if (
                isinstance(maximum_units, bool)
                or not isinstance(maximum_units, int)
                or maximum_units < 1
            ):
                raise ValueError(f"maximum capacity for {sku} is invalid")
            if units > maximum_units:
                continue

        candidates.append(
            CapacityTierSelection(
                tier_id=tier_id,
                sku=sku,
                capacity=units,
                billable_quantity=candidate_usage,
                included_quantity_per_unit=included_quantity,
                unit_price=price,
                total_cost=units * price,
            )
        )

    if not candidates:
        raise ValueError(
            "pricing tiers do not contain a valid paid tier for quantity"
        )
    return min(
        candidates,
        key=lambda candidate: (
            candidate.total_cost,
            candidate.sku,
            candidate.capacity,
        ),
    )


def tiered_unit_cost(
    quantity: float,
    tiers: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    limit_key: str = "limit",
    price_key: str = "price",
) -> float:
    """
    Calculate cumulative tiered usage cost for already normalized unit prices.

    Tier limits are absolute upper bounds. Each tier's price is expected to be
    normalized to one usage unit before this helper is called.
    """
    remaining = float(quantity)
    if remaining <= 0:
        return 0.0

    total = 0.0
    previous_limit = 0.0
    for tier in _tier_items(tiers):
        limit = _normalize_limit(tier.get(limit_key))
        if limit <= previous_limit:
            continue

        tier_quantity = min(remaining, limit - previous_limit)
        total += tier_quantity * _to_float(tier.get(price_key), 0.0)
        remaining -= tier_quantity
        previous_limit = limit
        if remaining <= 0:
            break

    if remaining > 0:
        raise ValueError("pricing tiers do not cover the requested quantity")
    return total


def _tier_items(
    tiers: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(tiers, Mapping):
        values = list(tiers.values())
    else:
        values = list(tiers)
    return sorted(values, key=lambda tier: _normalize_limit(tier.get("limit")))


def _named_tier_items(
    tiers: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(tiers, Mapping):
        items = [(str(key), value) for key, value in tiers.items()]
    else:
        items = []
        for index, tier in enumerate(tiers):
            tier_id = str(tier.get("tier_id") or tier.get("sku") or index)
            items.append((tier_id, tier))
    if any(not isinstance(tier, Mapping) for _, tier in items):
        raise ValueError("pricing tiers must contain objects")
    return sorted(
        items,
        key=lambda item: (
            _normalize_limit(item[1].get("limit")),
            item[0],
        ),
    )


def _normalize_limit(limit: Any) -> float:
    if limit is None:
        return float("inf")
    if isinstance(limit, str) and limit.lower() == "infinity":
        return float("inf")
    return float(limit)


def _to_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_positive_value(
    source: Mapping[str, Any],
    *keys: str,
) -> float:
    for key in keys:
        if key not in source or source[key] is None:
            continue
        candidate = _to_float(source[key], 0.0)
        if candidate > 0:
            return candidate
    return 0.0


def _first_present(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return None


def _finite_non_negative(name: str, value: Any) -> float:
    if isinstance(value, (bool, str, bytes)) or value is None:
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return normalized


def _finite_positive(name: str, value: Any) -> float:
    normalized = _finite_non_negative(name, value)
    if normalized <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return normalized
