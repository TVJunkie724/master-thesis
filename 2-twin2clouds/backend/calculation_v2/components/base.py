"""
Base Classes for Component Calculators
======================================

This module defines the Protocol (interface) that all component
calculators must implement, plus common utilities.
"""

from typing import Protocol, Dict, Any, runtime_checkable
from .types import FormulaType


@runtime_checkable
class ResourceCalculator(Protocol):
    """
    Protocol (interface) for individual resource cost calculators.
    
    Each component calculator must:
    1. Define which component it calculates (component_type)
    2. Define which formula it uses (formula_type)
    3. Implement calculate_cost() to return the monthly cost
    
    The calculate_cost method signature varies by component:
    - Some take executions, others take volume_gb, etc.
    - The Protocol is loose to allow flexibility
    """
    
    formula_type: FormulaType
    
    def calculate_cost(self, **kwargs) -> float:
        """
        Calculate the monthly cost for this component.
        
        Args:
            **kwargs: Component-specific parameters
            
        Returns:
            Monthly cost in USD
        """
        ...


class CalculatorBase:
    """
    Base class with common utilities for calculators.
    
    Provides helper methods for extracting pricing keys safely.
    """
    
    @staticmethod
    def get_pricing_value(pricing: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
        """
        Safely extract a nested value from pricing dict.
        
        Args:
            pricing: The pricing dictionary
            *keys: Path of keys to traverse
            default: Default value if not found
            
        Returns:
            The pricing value or default
            
        Example:
            get_pricing_value(pricing, "aws", "lambda", "requestPrice")
            # Returns pricing["aws"]["lambda"]["requestPrice"] or 0.0
        """
        current = pricing
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return float(current) if current is not None else default
