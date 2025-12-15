"""
Azure Logic Apps Cost Calculator
==================================

Calculates Azure Logic Apps costs using the CA (Action-Based) formula.

Pricing Model:
    - Action executions: Price per action
    - Connector executions: Different prices for standard/enterprise connectors

Logic Apps is used for orchestration in Azure, similar to AWS Step Functions.
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import action_based_cost


class AzureLogicAppsCalculator:
    """
    Azure Logic Apps cost calculator for L2 orchestration (optional).
    
    Uses: CA formula (action-based)
    
    Pricing keys:
        - pricing["azure"]["logicApps"]["pricePerAction"]
    """
    
    component_type = AzureComponent.LOGIC_APPS
    formula_type = FormulaType.CA
    
    # Default: Similar to Step Functions, ~3 actions per execution
    DEFAULT_ACTIONS_PER_EXECUTION = 3
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        actions_per_execution: int = None
    ) -> float:
        """
        Calculate Azure Logic Apps monthly cost.
        
        Args:
            executions: Number of workflow executions
            pricing: Full pricing dictionary
            actions_per_execution: Actions per execution
            
        Returns:
            Monthly cost in USD
        """
        actions_per_execution = actions_per_execution or self.DEFAULT_ACTIONS_PER_EXECUTION
        
        p = pricing["azure"]["logicApps"]
        price_per_action = p.get("pricePerAction", p.get("actionPrice", 0))
        total_actions = executions * actions_per_execution
        
        return action_based_cost(
            price_per_action=price_per_action,
            num_actions=total_actions
        )
