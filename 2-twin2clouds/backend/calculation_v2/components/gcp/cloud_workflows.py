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
from ...formulas import action_based_cost, required_first_unit_price


class GCPCloudWorkflowsCalculator:
    """
    GCP Cloud Workflows cost calculator for L2 orchestration (optional).
    
    Uses: CA formula (action-based)
    
    Pricing keys:
        - pricing["gcp"]["cloudWorkflows"]["pricePerInternalStep"]
        - pricing["gcp"]["cloudWorkflows"]["pricePerExternalStep"]
        - legacy ["pricePerStep"] or ["stepPrice"] for a single per-step price
    """
    
    component_type = GCPComponent.CLOUD_WORKFLOWS
    formula_type = FormulaType.CA
    
    # Default: ~3 steps per execution
    DEFAULT_STEPS_PER_EXECUTION = 3
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        steps_per_execution: int = None,
        external_steps_per_execution: int = 0,
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
        total_steps = executions * steps_per_execution
        external_steps = executions * external_steps_per_execution
        internal_steps = max(0, total_steps - external_steps)

        if any(
            key in p
            for key in (
                "pricePerInternalStep",
                "pricePerExternalStep",
                "pricePer1kInternalSteps",
                "pricePer1kExternalSteps",
            )
        ):
            internal_price = required_first_unit_price(
                p,
                (
                    ("pricePerInternalStep", 1),
                    ("pricePer1kInternalSteps", 1_000),
                ),
                label="gcp.workflows.internal_step",
            )
            external_price = required_first_unit_price(
                p,
                (
                    ("pricePerExternalStep", 1),
                    ("pricePer1kExternalSteps", 1_000),
                ),
                label="gcp.workflows.external_step",
            )
            return (
                action_based_cost(internal_price, internal_steps)
                + action_based_cost(external_price, external_steps)
            )

        price_per_step = required_first_unit_price(
            p,
            (
                ("pricePerStep", 1),
                ("stepPrice", 1),
                ("pricePer1kSteps", 1_000),
            ),
            label="gcp.workflows.step",
        )
        return action_based_cost(
            price_per_action=price_per_step,
            num_actions=total_steps
        )
