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
from ...formulas import action_based_cost, first_unit_price, message_based_cost


class AzureDigitalTwinsCalculator:
    """
    Azure Digital Twins cost calculator for L4 Twin Management.
    
    Uses: CA formula (for operations) + CM formula (for messages)
    
    Pricing keys:
        Preferred:
        - pricing["azure"]["azureDigitalTwins"]["pricePerOperation"]
        - pricing["azure"]["azureDigitalTwins"]["pricePerQueryUnit"]
        - pricing["azure"]["azureDigitalTwins"]["pricePerMessage"]
        Legacy Azure Retail Prices keys:
        - pricing["azure"]["azureDigitalTwins"]["operationPrice"] (per 1K)
        - pricing["azure"]["azureDigitalTwins"]["queryPrice"] (per 1K)
        - pricing["azure"]["azureDigitalTwins"]["messagePrice"] (per 1K)
    """
    
    component_type = AzureComponent.DIGITAL_TWINS
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        operations_per_month: float,
        queries_per_month: float,
        messages_per_month: float,
        pricing: Dict[str, Any],
        query_units_per_query: float | None = None,
    ) -> float:
        """
        Calculate Azure Digital Twins monthly cost.
        
        Args:
            operations_per_month: Number of CRUD operations
            queries_per_month: Number of twin queries
            messages_per_month: Number of property update messages
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["azure"]["azureDigitalTwins"]
        
        # Azure Retail Prices exposes ADT message, operation, and query meters
        # as 1K blocks. Keep compatibility with already-normalized explicit
        # keys, but normalize historical raw keys here at the boundary.
        op_price = first_unit_price(
            p,
            (
                ("pricePerOperation", 1),
                ("operationPricePer1k", 1_000),
                ("operationPrice", 1_000),
                ("pricePer1kOperations", 1_000),
                ("pricePerMillionOperations", 1_000_000),
            ),
        )
        operation_cost = action_based_cost(
            price_per_action=op_price,
            num_actions=operations_per_month
        )
        
        # Query cost (CA formula)
        query_price = first_unit_price(
            p,
            (
                ("pricePerQueryUnit", 1),
                ("queryPricePer1k", 1_000),
                ("queryPrice", 1_000),
                ("pricePer1kQueryUnits", 1_000),
            ),
        )
        query_unit_weight = (
            float(query_units_per_query)
            if query_units_per_query is not None
            else self._default_query_units_per_query(p)
        )
        query_cost = action_based_cost(
            price_per_action=query_price,
            num_actions=queries_per_month * query_unit_weight,
        )
        
        # Message cost (CM formula)
        message_price = first_unit_price(
            p,
            (
                ("pricePerMessage", 1),
                ("messagePricePer1k", 1_000),
                ("messagePrice", 1_000),
                ("pricePer1kMessages", 1_000),
            ),
        )
        message_cost = message_based_cost(
            price_per_message=message_price,
            num_messages=messages_per_month
        )
        
        return operation_cost + query_cost + message_cost

    @staticmethod
    def _default_query_units_per_query(pricing: Dict[str, Any]) -> float:
        tiers = pricing.get("queryUnitTiers") or []
        if not tiers:
            return 1.0
        first_tier = min(
            tiers,
            key=lambda tier: float(tier.get("lower", 0) or 0),
        )
        return float(first_tier.get("value") or 1.0)
