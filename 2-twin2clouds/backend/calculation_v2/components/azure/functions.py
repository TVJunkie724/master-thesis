"""
Azure Functions Cost Calculator
================================

Calculates Azure Functions serverless compute costs using the CE (Execution-Based) formula.

Pricing Model:
    - Execution cost: Price per million executions
    - Compute cost: Price per GB-second
    - Free tier: 1M executions + 400,000 GB-seconds per month

Similar to AWS Lambda, this calculator is also used for cross-cloud glue functions.
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import execution_based_cost


class AzureFunctionsCalculator:
    """
    Azure Functions cost calculator for L2 Data Processing.
    
    Uses: CE formula (execution-based)
    
    Pricing keys:
        - pricing["azure"]["functions"]["requestPrice"]
        - pricing["azure"]["functions"]["durationPrice"]
        - pricing["azure"]["functions"]["freeRequests"]
        - pricing["azure"]["functions"]["freeComputeTime"]
        
    Note: This calculator is also used for glue functions since they
    use the same Functions pricing.
    """
    
    component_type = AzureComponent.FUNCTIONS
    formula_type = FormulaType.CE
    
    # Default assumptions (consistent with AWS Lambda for fair comparison)
    DEFAULT_DURATION_MS = 100
    DEFAULT_MEMORY_MB = 128
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        duration_ms: float = None,
        memory_mb: float = None
    ) -> float:
        """
        Calculate Azure Functions monthly cost.
        
        Args:
            executions: Number of function invocations
            pricing: Full pricing dictionary
            duration_ms: Average execution duration in milliseconds
            memory_mb: Allocated memory in MB
            
        Returns:
            Monthly cost in USD
        """
        duration_ms = duration_ms or self.DEFAULT_DURATION_MS
        memory_mb = memory_mb or self.DEFAULT_MEMORY_MB
        
        p = pricing["azure"]["functions"]
        
        # Convert to GB-seconds
        memory_gb = memory_mb / 1024
        compute_seconds = executions * duration_ms * 0.001
        compute_gb_seconds = compute_seconds * memory_gb
        
        return execution_based_cost(
            price_per_execution=p["requestPrice"],
            num_executions=executions,
            free_executions=p["freeRequests"],
            price_per_compute_unit=p["durationPrice"],
            total_compute_units=compute_gb_seconds,
            free_compute_units=p["freeComputeTime"]
        )
    
    def calculate_glue_function_cost(
        self,
        messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Convenience method for glue function cost calculation."""
        return self.calculate_cost(
            executions=messages,
            pricing=pricing,
            duration_ms=self.DEFAULT_DURATION_MS,
            memory_mb=self.DEFAULT_MEMORY_MB
        )
