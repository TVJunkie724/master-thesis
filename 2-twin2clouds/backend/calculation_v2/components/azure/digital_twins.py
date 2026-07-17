"""Azure Digital Twins billable-quantity cost calculator."""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict

from ..types import AzureComponent, FormulaType
from ...formulas import (
    action_based_cost,
    first_unit_price,
    message_based_cost,
    required_first_unit_price,
)


@dataclass(frozen=True, slots=True)
class AzureDigitalTwinsCostBreakdown:
    operation_cost: float
    query_unit_cost: float
    routed_message_cost: float

    @property
    def total_cost(self) -> float:
        return self.operation_cost + self.query_unit_cost + self.routed_message_cost


class AzureDigitalTwinsCalculator:
    """Calculate ADT operation, query-unit, and routed-message charges."""

    component_type = AzureComponent.DIGITAL_TWINS
    formula_type = FormulaType.CA

    def calculate_cost(
        self,
        billable_operations: float,
        billable_query_units: float,
        billable_messages: float,
        pricing: Dict[str, Any],
    ) -> float:
        return self.calculate_breakdown(
            billable_operations=billable_operations,
            billable_query_units=billable_query_units,
            billable_messages=billable_messages,
            pricing=pricing,
        ).total_cost

    def calculate_breakdown(
        self,
        *,
        billable_operations: float,
        billable_query_units: float,
        billable_messages: float,
        pricing: Dict[str, Any],
    ) -> AzureDigitalTwinsCostBreakdown:
        operations = _quantity("billable_operations", billable_operations)
        query_units = _quantity("billable_query_units", billable_query_units)
        messages = _quantity("billable_messages", billable_messages)
        prices = pricing["azure"]["azureDigitalTwins"]

        operation_price = required_first_unit_price(
            prices,
            (
                ("pricePerOperation", 1),
                ("operationPricePer1k", 1_000),
                ("operationPrice", 1_000),
                ("pricePer1kOperations", 1_000),
                ("pricePerMillionOperations", 1_000_000),
            ),
            label="Azure Digital Twins operation",
        )
        query_unit_price = required_first_unit_price(
            prices,
            (
                ("pricePerQueryUnit", 1),
                ("queryPricePer1k", 1_000),
                ("queryPrice", 1_000),
                ("pricePer1kQueryUnits", 1_000),
            ),
            label="Azure Digital Twins query unit",
        )

        message_candidates = (
            ("pricePerMessage", 1),
            ("messagePricePer1k", 1_000),
            ("messagePrice", 1_000),
            ("pricePer1kMessages", 1_000),
        )
        message_price = (
            first_unit_price(prices, message_candidates)
            if messages == 0
            else required_first_unit_price(
                prices,
                message_candidates,
                label="Azure Digital Twins routed message",
            )
        )

        return AzureDigitalTwinsCostBreakdown(
            operation_cost=action_based_cost(operation_price, operations),
            query_unit_cost=action_based_cost(query_unit_price, query_units),
            routed_message_cost=message_based_cost(message_price, messages),
        )


def _quantity(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return normalized
