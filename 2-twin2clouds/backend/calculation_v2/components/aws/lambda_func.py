"""
AWS Lambda Cost Calculator
==========================

Calculates AWS Lambda serverless compute costs using the CE (Execution-Based) formula.

Pricing Model:
    - Request cost: Price per invocation
    - Compute cost: Price per GB-second of execution time
    - Free tier: 1M requests + 400,000 GB-seconds per month

This calculator is also used for cross-cloud glue functions
(connector, ingestion, writer, reader) since they all use Lambda pricing.
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import execution_based_cost


class AWSLambdaCalculator:
    """
    AWS Lambda cost calculator for L2 Data Processing.
    
    Uses: CE formula (execution-based)
    
    Pricing keys:
        - pricing["aws"]["lambda"]["requestPrice"]
        - pricing["aws"]["lambda"]["durationPrice"]
        - pricing["aws"]["lambda"]["freeRequests"]
        - pricing["aws"]["lambda"]["freeComputeTime"]
        
    Note: This calculator is also used for glue functions since they
    use the same Lambda pricing. See GlueRole enum for role types.
    """
    
    component_type = AWSComponent.LAMBDA
    formula_type = FormulaType.CE
    
    # Default assumptions (from current implementation: aws.py lines 346-347)
    # These match the deployer's Lambda configuration (MemorySize=128)
    # Using consistent values across AWS/Azure/GCP ensures fair cost comparison.
    DEFAULT_DURATION_MS = 100   # Conservative estimate for simple data processing
    DEFAULT_MEMORY_MB = 128     # Matches deployer Lambda config
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        duration_ms: float = None,
        memory_mb: float = None
    ) -> float:
        """
        Calculate AWS Lambda monthly cost.
        
        Args:
            executions: Number of Lambda invocations
            pricing: Full pricing dictionary
            duration_ms: Average execution duration in milliseconds
            memory_mb: Allocated memory in MB
            
        Returns:
            Monthly cost in USD
        """
        duration_ms = duration_ms or self.DEFAULT_DURATION_MS
        memory_mb = memory_mb or self.DEFAULT_MEMORY_MB
        
        p = pricing["aws"]["lambda"]
        
        # Convert to GB-seconds for pricing calculation
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
        """
        Calculate cost for a glue function (connector, ingestion, writer, reader).
        
        Glue functions are just Lambda functions with standard config.
        This is a convenience method matching the old API.
        
        Args:
            messages: Number of messages processed
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        return self.calculate_cost(
            executions=messages,
            pricing=pricing,
            duration_ms=self.DEFAULT_DURATION_MS,
            memory_mb=self.DEFAULT_MEMORY_MB
        )
