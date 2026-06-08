"""
Unit and tier helpers for provider pricing calculations.

Provider APIs frequently return prices in billing blocks such as 1K, 10K,
100K, or 1M operations. Calculators should convert those values at the
boundary and then multiply only normalized per-unit prices by workload values.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


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
    usage = float(quantity)
    if usage <= 0:
        return 0.0

    tier_list = _tier_items(tiers)
    free_candidates = [
        tier for tier in tier_list if _to_float(tier.get(price_key), 0.0) == 0.0
    ]
    for tier in free_candidates:
        limit = _normalize_limit(tier.get(limit_key))
        if usage <= limit:
            return 0.0

    costs: list[float] = []
    for tier in tier_list:
        price = _to_float(tier.get(price_key), 0.0)
        if price <= 0:
            continue

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

        limit = _normalize_limit(tier.get(limit_key))
        if usage > limit:
            continue

        units = max(int(math.ceil(usage / included_quantity)), minimum_paid_units)
        costs.append(units * price)

    if not costs:
        raise ValueError("pricing tiers do not contain a valid paid tier for quantity")
    return min(costs)


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


def _first_present(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return None
