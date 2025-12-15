"""
Builder Pattern: Layer Result Builder
======================================
Provides fluent API for constructing cost calculation result objects.

This module provides:
- LayerResultBuilder: Builder class for layer cost results
- LayerResult: TypedDict for type-safe result structure (imported from base)

Usage:
    from backend.calculation.builders import LayerResultBuilder
    
    result = (LayerResultBuilder("AWS")
        .set_cost(123.45)
        .set_data_size(10.5)
        .set_messages(1000000)
        .add_component("storageCost", 50.00)
        .add_component("computeCost", 73.45)
        .build())
"""

from typing import Dict, Any, Optional, List


class LayerResultBuilder:
    """
    Builder for constructing LayerResult dictionaries.
    
    Provides a fluent API with method chaining for building
    cost calculation result objects. Includes validation to
    ensure required fields are present.
    
    Example:
        >>> result = (LayerResultBuilder("AWS")
        ...     .set_cost(100.0)
        ...     .set_data_size(10.0)
        ...     .add_component("storageCost", 50.0)
        ...     .add_component("computeCost", 50.0)
        ...     .build())
        >>> result["provider"]
        'AWS'
        >>> result["totalMonthlyCost"]
        100.0
    """
    
    def __init__(self, provider: str):
        """
        Initialize builder with provider name.
        
        Args:
            provider: Provider name ("AWS", "Azure", or "GCP")
        """
        self._result: Dict[str, Any] = {
            "provider": provider
        }
        self._components: Dict[str, float] = {}
    
    def set_cost(self, total_monthly_cost: float) -> "LayerResultBuilder":
        """
        Set the total monthly cost.
        
        Args:
            total_monthly_cost: Total cost in USD
            
        Returns:
            Self for method chaining
        """
        self._result["totalMonthlyCost"] = total_monthly_cost
        return self
    
    def set_data_size(self, data_size_in_gb: float) -> "LayerResultBuilder":
        """
        Set the data size in GB.
        
        Args:
            data_size_in_gb: Data volume in gigabytes
            
        Returns:
            Self for method chaining
        """
        self._result["dataSizeInGB"] = data_size_in_gb
        return self
    
    def set_messages(self, total_messages_per_month: float) -> "LayerResultBuilder":
        """
        Set the total messages per month.
        
        Args:
            total_messages_per_month: Message count
            
        Returns:
            Self for method chaining
        """
        self._result["totalMessagesPerMonth"] = total_messages_per_month
        return self
    
    def add_component(self, name: str, cost: float) -> "LayerResultBuilder":
        """
        Add a cost breakdown component.
        
        Use this for detailed cost breakdowns (e.g., entityCost, apiCost).
        Components are stored separately and can be included in the final output.
        
        Args:
            name: Component name (e.g., "entityCost", "storageCost")
            cost: Component cost in USD
            
        Returns:
            Self for method chaining
        """
        self._components[name] = cost
        return self
    
    def include_components(self) -> "LayerResultBuilder":
        """
        Include all added components in the final result.
        
        Returns:
            Self for method chaining
        """
        self._result.update(self._components)
        return self
    
    def auto_sum_cost(self) -> "LayerResultBuilder":
        """
        Automatically calculate totalMonthlyCost from components.
        
        Sums all added components and sets as the total monthly cost.
        
        Returns:
            Self for method chaining
        """
        if self._components:
            self._result["totalMonthlyCost"] = sum(self._components.values())
        return self
    
    def validate(self) -> "LayerResultBuilder":
        """
        Validate that required fields are present.
        
        Raises:
            ValueError: If required fields are missing
            
        Returns:
            Self for method chaining
        """
        if "provider" not in self._result:
            raise ValueError("LayerResult requires 'provider' field")
        if "totalMonthlyCost" not in self._result:
            raise ValueError("LayerResult requires 'totalMonthlyCost' field")
        return self
    
    def build(self, validate: bool = True) -> Dict[str, Any]:
        """
        Build and return the final LayerResult dictionary.
        
        Args:
            validate: If True, validates required fields before returning
            
        Returns:
            Dictionary with layer cost result
            
        Raises:
            ValueError: If validation enabled and required fields missing
        """
        if validate:
            self.validate()
        return dict(self._result)


class CostBreakdownBuilder:
    """
    Builder for constructing detailed cost breakdown reports.
    
    Used for building the complete cost optimization result
    with all provider comparisons and layer breakdowns.
    """
    
    def __init__(self):
        """Initialize an empty cost breakdown."""
        self._result: Dict[str, Any] = {
            "providers": {},
            "layers": {},
            "cheapestPath": None,
            "totalOptimizedCost": 0.0
        }
    
    def add_provider_costs(
        self,
        provider: str,
        costs: Dict[str, Any]
    ) -> "CostBreakdownBuilder":
        """
        Add cost calculations for a provider.
        
        Args:
            provider: Provider name
            costs: Dictionary of layer costs
            
        Returns:
            Self for method chaining
        """
        self._result["providers"][provider] = costs
        return self
    
    def set_cheapest_path(self, path: Dict[str, Any]) -> "CostBreakdownBuilder":
        """
        Set the optimal architecture path.
        
        Args:
            path: Dictionary with path and cost details
            
        Returns:
            Self for method chaining
        """
        self._result["cheapestPath"] = path
        return self
    
    def set_total_cost(self, cost: float) -> "CostBreakdownBuilder":
        """
        Set the total optimized cost.
        
        Args:
            cost: Total optimized monthly cost
            
        Returns:
            Self for method chaining
        """
        self._result["totalOptimizedCost"] = cost
        return self
    
    def build(self) -> Dict[str, Any]:
        """
        Build and return the final cost breakdown.
        
        Returns:
            Complete cost optimization result dictionary
        """
        return dict(self._result)
