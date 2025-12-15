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
        pricing: Dict[str, Any]
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
        
        # Operations cost (CA formula)
        op_price_per_million = p.get("operationPrice", p.get("pricePerMillionOperations", 0))
        op_price = op_price_per_million / 1_000_000
        operation_cost = action_based_cost(
            price_per_action=op_price,
            num_actions=operations_per_month
        )
        
        # Query cost (CA formula)
        query_price = p.get("queryPrice", 0)
        query_cost = action_based_cost(
            price_per_action=query_price,
            num_actions=queries_per_month
        )
        
        # Message cost (CM formula)
        message_price = p.get("messagePrice", 0)
        message_cost = message_based_cost(
            price_per_message=message_price,
            num_messages=messages_per_month
        )
        
        return operation_cost + query_cost + message_cost
