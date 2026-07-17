"""
GCP Cloud Functions Cost Calculator
=====================================

Calculates GCP Cloud Functions costs using the CE (Execution-Based) formula.

Pricing Model:
    - Invocation cost: Price per million invocations
    - Compute cost: Price per GB-second + networking
    - Free tier: 2M invocations + 400,000 GB-seconds per month
"""

from typing import Dict, Any
from ..types import GCPComponent, FormulaType
from ...deployment_profiles import (
    GCP_STANDARD_FUNCTION_MEMORY_MB,
    STANDARD_FUNCTION_DURATION_MS,
)
from ...formulas import execution_based_cost, required_first_unit_price


class GCPCloudFunctionsCalculator:
    """
    GCP Cloud Functions cost calculator for L2 Data Processing.
    
    Uses: CE formula (execution-based)
    
    Pricing keys:
        - pricing["gcp"]["functions"]["requestPrice"] or ["invocationPrice"]
        - pricing["gcp"]["functions"]["durationPrice"] or ["gbSecondPrice"]
        - per-million request keys are normalized at the calculator boundary
        - pricing["gcp"]["functions"]["freeInvocations"]
        - pricing["gcp"]["functions"]["freeGBSeconds"]
    """
    
    component_type = GCPComponent.CLOUD_FUNCTIONS
    formula_type = FormulaType.CE
    
    DEFAULT_DURATION_MS = STANDARD_FUNCTION_DURATION_MS
    DEFAULT_MEMORY_MB = GCP_STANDARD_FUNCTION_MEMORY_MB
    
    def calculate_cost(
        self,
        executions: float,
        pricing: Dict[str, Any],
        duration_ms: float = None,
        memory_mb: float = None
    ) -> float:
        """
        Calculate GCP Cloud Functions monthly cost.
        
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
        
        p = pricing["gcp"]["functions"]
        request_price = required_first_unit_price(
            p,
            (
                ("requestPrice", 1),
                ("invocationPrice", 1),
                ("pricePerRequest", 1),
                ("pricePerMillionRequests", 1_000_000),
                ("pricePerMillionInvocations", 1_000_000),
            ),
            label="gcp.functions.request",
        )
        compute_price = required_first_unit_price(
            p,
            (
                ("durationPrice", 1),
                ("gbSecondPrice", 1),
                ("pricePerGbSecond", 1),
                ("pricePerGiBSecond", 1),
            ),
            label="gcp.functions.compute_gb_second",
        )
        
        # Convert to GB-seconds
        memory_gb = memory_mb / 1024
        compute_seconds = executions * duration_ms * 0.001
        compute_gb_seconds = compute_seconds * memory_gb
        
        return execution_based_cost(
            price_per_execution=request_price,
            num_executions=executions,
            free_executions=p.get("freeInvocations", p.get("freeRequests", 0)),
            price_per_compute_unit=compute_price,
            total_compute_units=compute_gb_seconds,
            free_compute_units=p.get("freeGBSeconds", p.get("freeComputeTime", 0))
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
