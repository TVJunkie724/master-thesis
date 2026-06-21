"""
Azure Digital Twins Cost Calculator
=====================================

Calculates Azure Digital Twins costs using CA (Action-Based) + CM (Message-Based) formulas.

Pricing Model:
    - Operations: Price per million operations
    - Queries: Price per query unit
    - Messages: Price per message (for property updates)
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import action_based_cost, message_based_cost


class AzureDigitalTwinsCalculator:
    """
    Azure Digital Twins cost calculator for L4 Twin Management.
    
    Uses: CA formula (for operations) + CM formula (for messages)
    
    Pricing keys:
        - pricing["azure"]["azureDigitalTwins"]["operationPrice"] (per million)
        - pricing["azure"]["azureDigitalTwins"]["queryPrice"]
        - pricing["azure"]["azureDigitalTwins"]["messagePrice"]
    """
    
    component_type = AzureComponent.DIGITAL_TWINS
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        operations_per_month: float,
        queries_per_month: float,
        messages_per_month: float,
        pricing: Dict[str, Any],
        query_units_per_query: float = None
    ) -> float:
        """
        Calculate Azure Digital Twins monthly cost.
        
        Args:
            operations_per_month: Number of CRUD operations
            queries_per_month: Number of twin queries
            messages_per_month: Number of property update messages
            pricing: Full pricing dictionary
            query_units_per_query: Optional explicit query-unit weight per query
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["azure"]["azureDigitalTwins"]
        
        # Operations cost (CA formula)
        op_price = self._normalize_price(
            p.get("operationPrice", p.get("pricePerMillionOperations", 0)),
            p.get("operationPriceUnit", "per_1k"),
        )
        operation_cost = action_based_cost(
            price_per_action=op_price,
            num_actions=operations_per_month
        )
        
        # Query cost (CA formula over query units)
        query_units = queries_per_month * (
            query_units_per_query
            if query_units_per_query is not None
            else self._default_query_units_per_query(p)
        )
        query_price = self._normalize_price(
            p.get("queryPrice", 0),
            p.get("queryPriceUnit", "per_1k"),
        )
        query_cost = action_based_cost(
            price_per_action=query_price,
            num_actions=query_units
        )
        
        # Message cost (CM formula)
        message_price = self._normalize_price(
            p.get("messagePrice", 0),
            p.get("messagePriceUnit", "per_1k"),
        )
        message_cost = message_based_cost(
            price_per_message=message_price,
            num_messages=messages_per_month
        )
        
        return operation_cost + query_cost + message_cost

    def _normalize_price(self, price: float, unit: str) -> float:
        unit = (unit or "").lower()
        if unit in {"per_action", "per_message", "per_query_unit", "per_unit"}:
            return float(price)
        if unit in {"per_1k", "per_1000"}:
            return float(price) / 1_000
        if unit in {"per_100k", "per_100000"}:
            return float(price) / 100_000
        if unit in {"per_million", "per_1m", "per_1000000"}:
            return float(price) / 1_000_000
        raise ValueError(f"Unsupported Azure Digital Twins price unit: {unit}")

    def _default_query_units_per_query(self, pricing: Dict[str, Any]) -> float:
        tiers = pricing.get("queryUnitTiers") or []
        if not tiers:
            return 1.0
        first_tier = min(tiers, key=lambda item: item.get("lower", 0))
        return float(first_tier.get("value", 1.0))
