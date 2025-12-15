"""
Azure Event Grid Cost Calculator
=================================

Calculates Azure Event Grid costs using the CA (Action-Based) formula.

Pricing Model:
    - Operations: Price per million operations
    
Event Grid is used for event routing, similar to AWS EventBridge.
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import action_based_cost


class AzureEventGridCalculator:
    """
    Azure Event Grid cost calculator for L2 error handling (optional).
    
    Uses: CA formula (action-based)
    
    Pricing keys:
        - pricing["azure"]["eventGrid"]["pricePerMillionOperations"]
    """
    
    component_type = AzureComponent.EVENT_GRID
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        events: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate Azure Event Grid monthly cost.
        
        Args:
            events: Number of events published
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["azure"]["eventGrid"]
        price_per_million = p.get("pricePerMillionOperations", p.get("pricePerMillionEvents", 0))
        price_per_event = price_per_million / 1_000_000
        
        return action_based_cost(
            price_per_action=price_per_event,
            num_actions=events
        )
