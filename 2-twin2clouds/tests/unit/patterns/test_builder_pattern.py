"""
Tests for Builder Pattern Implementation
=========================================
Tests the LayerResultBuilder and CostBreakdownBuilder classes.
"""

import pytest
from backend.calculation.builders import LayerResultBuilder, CostBreakdownBuilder


# =============================================================================
# LayerResultBuilder Tests
# =============================================================================

class TestLayerResultBuilder:
    """Test LayerResultBuilder functionality."""
    
    def test_basic_build(self):
        """Builder should create a valid result with required fields."""
        result = (LayerResultBuilder("AWS")
            .set_cost(100.0)
            .build())
        
        assert result["provider"] == "AWS"
        assert result["totalMonthlyCost"] == 100.0
    
    def test_method_chaining(self):
        """All builder methods should return self for chaining."""
        builder = LayerResultBuilder("Azure")
        
        # Each method should return the builder itself
        assert builder.set_cost(50.0) is builder
        assert builder.set_data_size(10.0) is builder
        assert builder.set_messages(1000) is builder
        assert builder.add_component("test", 10.0) is builder
    
    def test_set_data_size(self):
        """Data size should be included in result."""
        result = (LayerResultBuilder("GCP")
            .set_cost(100.0)
            .set_data_size(25.5)
            .build())
        
        assert result["dataSizeInGB"] == 25.5
    
    def test_set_messages(self):
        """Message count should be included in result."""
        result = (LayerResultBuilder("AWS")
            .set_cost(100.0)
            .set_messages(1000000.0)
            .build())
        
        assert result["totalMessagesPerMonth"] == 1000000.0
    
    def test_add_component(self):
        """Components should be stored and available for inclusion."""
        result = (LayerResultBuilder("Azure")
            .set_cost(100.0)
            .add_component("storageCost", 60.0)
            .add_component("computeCost", 40.0)
            .include_components()
            .build())
        
        assert result["storageCost"] == 60.0
        assert result["computeCost"] == 40.0
    
    def test_components_not_included_by_default(self):
        """Components should not appear in result unless explicitly included."""
        result = (LayerResultBuilder("AWS")
            .set_cost(100.0)
            .add_component("hidden", 50.0)
            .build())
        
        assert "hidden" not in result
    
    def test_auto_sum_cost(self):
        """Auto sum should calculate total from components."""
        result = (LayerResultBuilder("GCP")
            .add_component("compute", 30.0)
            .add_component("storage", 20.0)
            .add_component("network", 10.0)
            .auto_sum_cost()
            .build())
        
        assert result["totalMonthlyCost"] == pytest.approx(60.0)
    
    def test_validation_missing_cost(self):
        """Validation should fail if totalMonthlyCost is missing."""
        builder = LayerResultBuilder("AWS")
        
        with pytest.raises(ValueError, match="totalMonthlyCost"):
            builder.validate()
    
    def test_build_without_validation(self):
        """Build with validate=False should skip validation."""
        result = (LayerResultBuilder("AWS")
            .build(validate=False))
        
        assert result["provider"] == "AWS"
        assert "totalMonthlyCost" not in result  # Missing but allowed
    
    def test_complete_example(self):
        """Full realistic example of builder usage."""
        result = (LayerResultBuilder("AWS")
            .set_cost(123.45)
            .set_data_size(10.5)
            .set_messages(4380000)
            .add_component("entityCost", 50.0)
            .add_component("apiCost", 43.45)
            .add_component("storageCost", 30.0)
            .include_components()
            .build())
        
        assert result == {
            "provider": "AWS",
            "totalMonthlyCost": 123.45,
            "dataSizeInGB": 10.5,
            "totalMessagesPerMonth": 4380000,
            "entityCost": 50.0,
            "apiCost": 43.45,
            "storageCost": 30.0,
        }


# =============================================================================
# CostBreakdownBuilder Tests
# =============================================================================

class TestCostBreakdownBuilder:
    """Test CostBreakdownBuilder functionality."""
    
    def test_basic_build(self):
        """Builder should create a valid breakdown structure."""
        result = CostBreakdownBuilder().build()
        
        assert "providers" in result
        assert "layers" in result
        assert "cheapestPath" in result
        assert "totalOptimizedCost" in result
    
    def test_add_provider_costs(self):
        """Provider costs should be added correctly."""
        result = (CostBreakdownBuilder()
            .add_provider_costs("aws", {"l1": 100, "l2": 200})
            .add_provider_costs("azure", {"l1": 90, "l2": 180})
            .build())
        
        assert "aws" in result["providers"]
        assert result["providers"]["aws"]["l1"] == 100
        assert "azure" in result["providers"]
    
    def test_set_cheapest_path(self):
        """Cheapest path should be set correctly."""
        path = {"path": ["aws-l1", "azure-l2"], "cost": 150.0}
        result = (CostBreakdownBuilder()
            .set_cheapest_path(path)
            .build())
        
        assert result["cheapestPath"] == path
    
    def test_set_total_cost(self):
        """Total optimized cost should be set correctly."""
        result = (CostBreakdownBuilder()
            .set_total_cost(299.99)
            .build())
        
        assert result["totalOptimizedCost"] == 299.99


# =============================================================================
# Edge Cases
# =============================================================================

class TestBuilderEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_cost(self):
        """Zero cost should be valid."""
        result = (LayerResultBuilder("AWS")
            .set_cost(0.0)
            .build())
        
        assert result["totalMonthlyCost"] == 0.0
    
    def test_negative_cost_allowed(self):
        """Negative costs are allowed (credits/refunds)."""
        result = (LayerResultBuilder("AWS")
            .set_cost(-10.0)
            .build())
        
        assert result["totalMonthlyCost"] == -10.0
    
    def test_overwrite_component(self):
        """Adding same component twice should overwrite."""
        result = (LayerResultBuilder("AWS")
            .set_cost(100.0)
            .add_component("storage", 50.0)
            .add_component("storage", 75.0)  # Overwrites
            .include_components()
            .build())
        
        assert result["storage"] == 75.0
    
    def test_empty_provider_name(self):
        """Empty provider name should still work."""
        result = (LayerResultBuilder("")
            .set_cost(100.0)
            .build())
        
        assert result["provider"] == ""
