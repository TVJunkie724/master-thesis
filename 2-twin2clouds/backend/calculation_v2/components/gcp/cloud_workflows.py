"""
GCP Cloud Workflows Cost Calculator
=====================================

Calculates GCP Cloud Workflows costs using the CA (Action-Based) formula.

Pricing Model:
    - Steps: Price per step (state transition)
    - Similar to AWS Step Functions and Azure Logic Apps
"""

from typing import Dict, Any
from ..types import GCPComponent, FormulaType
from ...formulas import action_based_cost


class GCPCloudWorkflowsCalculator:
    """
    GCP Cloud Workflows cost calculator for L2 orchestration (optional).
    
    Uses: CA formula (action-based)
    
    Pricing keys:
        - pricing["gcp"]["cloudWorkflows"]["pricePerStep"]
    """
    
    component_type = GCPComponent.CLOUD_WORKFLOWS
    formula_type = FormulaType.CA
    
    # Default: ~3 steps per execution
    DEFAULT_STEPS_PER_EXECUTION = 3
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        steps_per_execution: int = None
    ) -> float:
        """
        Calculate GCP Cloud Workflows monthly cost.
        
        Args:
            executions: Number of workflow executions
            pricing: Full pricing dictionary
            steps_per_execution: Steps per execution
            
        Returns:
            Monthly cost in USD
        """
        steps_per_execution = steps_per_execution or self.DEFAULT_STEPS_PER_EXECUTION
        
        p = pricing["gcp"]["cloudWorkflows"]
        price_per_step = p.get("pricePerStep", p.get("stepPrice", 0))
        total_steps = executions * steps_per_execution
        
        return action_based_cost(
            price_per_action=price_per_step,
            num_actions=total_steps
        )
