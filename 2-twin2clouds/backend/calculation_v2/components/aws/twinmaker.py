"""AWS IoT TwinMaker Standard pricing for the thesis PoC."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from ..types import AWSComponent, FormulaType


@dataclass(frozen=True, slots=True)
class TwinMakerStandardCost:
    total: float
    entity_cost: float
    query_cost: float
    api_call_cost: float
    entity_count: int
    entity_price_per_month: float
    queries_per_month: float
    query_price: float
    api_calls_per_month: float
    api_call_price: float


class AWSTwinMakerCalculator:
    """Calculate the one pinned Standard pricing mode used by the PoC."""

    component_type = AWSComponent.TWINMAKER
    formula_type = FormulaType.CA

    def calculate_standard_cost(
        self,
        *,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Mapping[str, Any],
    ) -> TwinMakerStandardCost:
        entity_count = _nonnegative_integer("entity_count", entity_count)
        queries = _nonnegative_number("queries_per_month", queries_per_month)
        api_calls = _nonnegative_number("api_calls_per_month", api_calls_per_month)
        aws = _required_mapping(pricing.get("aws"), "aws")
        rates = _required_mapping(aws.get("iotTwinMaker"), "aws.iotTwinMaker")
        usage_rates = _required_mapping(
            rates.get("usageRates"),
            "aws.iotTwinMaker.usageRates",
        )
        entity_price = _positive_price(usage_rates, "entityPricePerMonth")
        query_price = _positive_price(usage_rates, "queryPrice")
        api_price = _positive_price(
            usage_rates,
            "unifiedDataAccessApiCallPrice",
        )
        entity_cost = entity_count * entity_price
        query_cost = queries * query_price
        api_call_cost = api_calls * api_price
        return TwinMakerStandardCost(
            total=entity_cost + query_cost + api_call_cost,
            entity_cost=entity_cost,
            query_cost=query_cost,
            api_call_cost=api_call_cost,
            entity_count=entity_count,
            entity_price_per_month=entity_price,
            queries_per_month=queries,
            query_price=query_price,
            api_calls_per_month=api_calls,
            api_call_price=api_price,
        )

    def calculate_cost(
        self,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Mapping[str, Any],
        model_storage_gb: float = 0.0,
    ) -> float:
        """Compatibility entry point with strict Standard semantics."""
        if model_storage_gb:
            raise ValueError(
                "AWS TwinMaker model storage has no approved pricing contract."
            )
        return self.calculate_standard_cost(
            entity_count=entity_count,
            queries_per_month=queries_per_month,
            api_calls_per_month=api_calls_per_month,
            pricing=pricing,
        ).total


def _required_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} pricing object is required.")
    return value


def _positive_price(mapping: Mapping[str, Any], key: str) -> float:
    value = _nonnegative_number(key, mapping.get(key))
    if value <= 0:
        raise ValueError(f"{key} must be positive.")
    return value


def _nonnegative_number(label: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0:
        raise ValueError(f"{label} must be finite and non-negative.")
    return normalized


def _nonnegative_integer(label: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return value
