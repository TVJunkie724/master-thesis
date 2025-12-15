"""
AWS Step Functions Cost Calculator
===================================

Calculates AWS Step Functions (orchestration) costs using the CA (Action-Based) formula.

Pricing Model:
    - Standard Workflows: Price per state transition
    - Express Workflows: Price per request + duration (not implemented here)
    
This calculator assumes Standard Workflows, which is typical for IoT orchestration.
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import action_based_cost


class AWSStepFunctionsCalculator:
    """
    AWS Step Functions cost calculator for L2 orchestration (optional).
    
    Uses: CA formula (action-based)
    
    Pricing keys:
        - pricing["aws"]["stepFunctions"]["pricePerStateTransition"]
        
    This is an optional L2 component, enabled when:
        - use_event_checking=True AND trigger_notification_workflow=True
    """
    
    component_type = AWSComponent.STEP_FUNCTIONS
    formula_type = FormulaType.CA
    
    # Default: 3 state transitions per message
    # (e.g., Start → Process → Notify → End)
    DEFAULT_ACTIONS_PER_MESSAGE = 3
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        actions_per_execution: int = None
    ) -> float:
        """
        Calculate AWS Step Functions monthly cost.
        
        Args:
            executions: Number of workflow executions
            pricing: Full pricing dictionary
            actions_per_execution: State transitions per execution
            
        Returns:
            Monthly cost in USD
        """
        actions_per_execution = actions_per_execution or self.DEFAULT_ACTIONS_PER_MESSAGE
        
        price_per_action = pricing["aws"]["stepFunctions"]["pricePerStateTransition"]
        total_actions = executions * actions_per_execution
        
        return action_based_cost(
            price_per_action=price_per_action,
            num_actions=total_actions
        )
