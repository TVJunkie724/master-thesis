"""
Tests for the function registry.

Tests the new function registry system that replaces hardcoded function lists.
"""
import pytest
from src.function_registry import (
    STATIC_FUNCTIONS, Layer, FunctionDefinition,
    get_by_layer, get_by_provider, get_l0_for_config, get_terraform_output_map
)


class TestRegistryStructure:
    """Tests for registry data structure and integrity."""
    
    def test_all_functions_have_unique_names_per_layer(self):
        """Each (layer, name) combination should be unique."""
        seen = set()
        for f in STATIC_FUNCTIONS:
            key = (f.layer, f.name)
            assert key not in seen, f"Duplicate: {f.name} in {f.layer}"
            seen.add(key)
    
    def test_all_functions_have_valid_providers(self):
        """All functions should have at least one provider."""
        for f in STATIC_FUNCTIONS:
            assert len(f.providers) > 0, f"{f.name} has no providers"
            for provider in f.providers:
                assert provider in ["aws", "azure", "gcp"], f"Invalid provider: {provider}"
    
    def test_l0_functions_have_boundaries(self):
        """All L0 glue functions should have boundary definitions."""
        l0_funcs = get_by_layer(Layer.L0_GLUE)
        for f in l0_funcs:
            assert f.boundary is not None, f"L0 function {f.name} missing boundary"
            assert len(f.boundary) == 2, f"Boundary should be (source, target) tuple"
    
    def test_safe_name_conversion(self):
        """safe_name should convert hyphens to underscores."""
        func = FunctionDefinition("hot-reader", Layer.L3_STORAGE)
        assert func.safe_name == "hot_reader"
        
        func2 = FunctionDefinition("dispatcher", Layer.L1_ACQUISITION)
        assert func2.safe_name == "dispatcher"


class TestQueryFunctions:
    """Tests for registry query functions."""
    
    def test_get_by_layer_l1(self):
        """Should return L1 acquisition functions."""
        l1_funcs = get_by_layer(Layer.L1_ACQUISITION)
        assert len(l1_funcs) >= 1
        assert any(f.name == "dispatcher" for f in l1_funcs)
    
    def test_get_by_layer_l2(self):
        """Should return L2 processing functions."""
        l2_funcs = get_by_layer(Layer.L2_PROCESSING)
        assert len(l2_funcs) >= 1
        assert any(f.name == "persister" for f in l2_funcs)
    
    def test_get_by_layer_l3(self):
        """Should return L3 storage functions."""
        l3_funcs = get_by_layer(Layer.L3_STORAGE)
        assert len(l3_funcs) >= 4
        names = [f.name for f in l3_funcs]
        assert "hot-reader" in names
        assert "hot-to-cold-mover" in names
    
    def test_get_by_provider_azure(self):
        """Should return all Azure-compatible functions."""
        azure_funcs = get_by_provider("azure")
        assert len(azure_funcs) > 0
        # All should have azure in providers
        for f in azure_funcs:
            assert "azure" in f.providers
    
    def test_get_by_provider_aws(self):
        """Should return all AWS-compatible functions."""
        aws_funcs = get_by_provider("aws")
        assert len(aws_funcs) > 0
        for f in aws_funcs:
            assert "aws" in f.providers


class TestL0GlueLogic:
    """Tests for L0 cross-cloud glue function logic."""
    
    def test_l0_empty_for_single_cloud(self):
        """Should return empty list when all providers are the same."""
        config = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure",
        }
        funcs = get_l0_for_config(config, "azure")
        assert funcs == []
    
    def test_l0_ingestion_for_l1_l2_boundary(self):
        """Should include ingestion when L1 != L2 and L2 is target."""
        config = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure",
        }
        funcs = get_l0_for_config(config, "azure")
        assert "ingestion" in funcs
    
    def test_l0_hot_writer_for_l2_l3_boundary(self):
        """Should include hot-writer when L2 != L3_hot and L3_hot is target."""
        config = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure",
        }
        funcs = get_l0_for_config(config, "azure")
        assert "hot-writer" in funcs
    
    def test_l0_multiple_boundaries(self):
        """Should include multiple glue functions for multiple boundaries."""
        config = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "gcp",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure",
        }
        funcs = get_l0_for_config(config, "azure")
        # L1->L2 boundary: ingestion on Azure
        assert "ingestion" in funcs
        # L3->L4 boundary: adt-pusher on Azure (if exists)
        # Note: depends on registry definition


class TestTerraformOutputMap:
    """Tests for Terraform output key generation."""
    
    def test_output_map_format_aws(self):
        """AWS output map should have correct key format."""
        output_map = get_terraform_output_map("aws")
        
        # Check that keys follow pattern: {provider}_l{layer}_{name}_function_name
        for key, value in output_map.items():
            assert key.startswith("aws_l"), f"Key should start with 'aws_l': {key}"
            assert key.endswith("_function_name"), f"Key should end with '_function_name': {key}"
    
    def test_output_map_contains_dispatcher(self):
        """Output map should include dispatcher function."""
        output_map = get_terraform_output_map("aws")
        assert "aws_l1_dispatcher_function_name" in output_map
        assert output_map["aws_l1_dispatcher_function_name"] == "dispatcher"
    
    def test_output_map_contains_persister(self):
        """Output map should include persister function."""
        output_map = get_terraform_output_map("azure")
        assert "azure_l2_persister_function_name" in output_map
        assert output_map["azure_l2_persister_function_name"] == "persister"
    
    def test_output_map_layer_filter(self):
        """Should filter by layer when specified."""
        l1_map = get_terraform_output_map("aws", Layer.L1_ACQUISITION)
        
        # All keys should be L1
        for key in l1_map.keys():
            assert "_l1_" in key, f"Expected L1 key, got: {key}"


class TestFunctionDefinition:
    """Tests for FunctionDefinition dataclass."""
    
    def test_get_dir_name_uses_name_by_default(self):
        """get_dir_name should return name if dir_name not set."""
        func = FunctionDefinition("dispatcher", Layer.L1_ACQUISITION)
        assert func.get_dir_name() == "dispatcher"
    
    def test_get_dir_name_uses_dir_name_override(self):
        """get_dir_name should return dir_name if set."""
        func = FunctionDefinition(
            "l0-ingestion",
            Layer.L0_GLUE,
            dir_name="ingestion"
        )
        assert func.get_dir_name() == "ingestion"
    
    def test_optional_flag(self):
        """Optional functions should be marked correctly."""
        func = FunctionDefinition("event-checker", Layer.L2_PROCESSING, is_optional=True)
        assert func.is_optional is True
        
        func2 = FunctionDefinition("dispatcher", Layer.L1_ACQUISITION)
        assert func2.is_optional is False
