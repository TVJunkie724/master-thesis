"""
AWS EventBridge Cost Calculator
================================

Calculates AWS EventBridge costs using the CA (Action-Based) formula.

Pricing Model:
    - Events: Price per million events published
    
EventBridge is used in the architecture for:
    - Error handling (routing errors to error handlers)
    - Event-driven notifications
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import action_based_cost, required_first_unit_price


class AWSEventBridgeCalculator:
    """
    AWS EventBridge cost calculator for L2 error handling (optional).
    
    Uses: CA formula (action-based)
    
    Pricing keys:
        - pricing["aws"]["eventBridge"]["pricePerMillionEvents"]
        
    This is an optional L2 component, enabled when:
        - integrate_error_handling=True
    """
    
    component_type = AWSComponent.EVENTBRIDGE
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        events: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate AWS EventBridge monthly cost.
        
        Args:
            events: Number of events published
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        price_per_event = required_first_unit_price(
            pricing["aws"]["eventBridge"],
            (
                ("pricePerEvent", 1),
                ("eventPrice", 1),
                ("pricePerMillionEvents", 1_000_000),
            ),
            label="aws.eventBridge.event",
        )
        
        return action_based_cost(
            price_per_action=price_per_event,
            num_actions=events
        )
