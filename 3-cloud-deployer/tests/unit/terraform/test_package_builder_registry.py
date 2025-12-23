"""
Tests for package_builder.py registry integration.

Verifies that package_builder uses function_registry.get_functions_for_provider_build()
instead of hardcoded function lists.
"""
import pytest
from src.function_registry import get_functions_for_provider_build


class TestRegistryFunctionLists:
    """Verify registry returns correct functions for each provider config."""
    
    @pytest.fixture
    def all_aws_config(self):
        """Config where all layers are on AWS."""
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
        }
    
    @pytest.fixture
    def all_azure_config(self):
        """Config where all layers are on Azure."""
        return {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure",
        }
    
    @pytest.fixture
    def all_gcp_config(self):
        """Config where all layers are on GCP (uses 'google' in config)."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
            "layer_4_provider": "google",
        }
    
    # =========================================================================
    # AWS Tests
    # =========================================================================
    
    def test_aws_includes_l1_functions(self, all_aws_config):
        """AWS should include L1 dispatcher and connector."""
        functions = get_functions_for_provider_build("aws", all_aws_config)
        assert "dispatcher" in functions, "L1 dispatcher should be included"
        assert "connector" in functions, "L1 connector should be included"
    
    def test_aws_includes_l2_functions(self, all_aws_config):
        """AWS should include L2 persister."""
        functions = get_functions_for_provider_build("aws", all_aws_config)
        assert "persister" in functions, "L2 persister should be included"
    
    def test_aws_includes_l3_functions(self, all_aws_config):
        """AWS should include L3 storage functions."""
        functions = get_functions_for_provider_build("aws", all_aws_config)
        assert "hot-reader" in functions, "L3 hot-reader should be included"
        assert "hot-to-cold-mover" in functions, "L3 hot-to-cold-mover should be included"
        assert "cold-to-archive-mover" in functions, "L3 cold-to-archive-mover should be included"
    
    def test_aws_includes_l4_functions(self, all_aws_config):
        """AWS should include L4 digital twin functions."""
        functions = get_functions_for_provider_build("aws", all_aws_config)
        assert "digital-twin-data-connector" in functions, "L4 connector should be included"
    
    def test_aws_excludes_l0_when_same_cloud(self, all_aws_config):
        """AWS should NOT include L0 glue when all layers are on same cloud."""
        functions = get_functions_for_provider_build("aws", all_aws_config)
        assert "ingestion" not in functions, "L0 ingestion should NOT be included (same cloud)"
        assert "hot-writer" not in functions, "L0 hot-writer should NOT be included (same cloud)"
    
    def test_aws_l0_triggered_by_cross_cloud_boundary(self):
        """AWS should include L0 ingestion when L1→L2 crosses clouds."""
        cross_cloud_config = {
            "layer_1_provider": "google",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
        }
        functions = get_functions_for_provider_build("aws", cross_cloud_config)
        assert "ingestion" in functions, "L0 ingestion should be triggered by L1(gcp)→L2(aws) boundary"
    
    # =========================================================================
    # Azure Tests
    # =========================================================================
    
    def test_azure_includes_expected_functions(self, all_azure_config):
        """Azure should include dispatcher, persister, and adt-updater."""
        functions = get_functions_for_provider_build("azure", all_azure_config)
        assert "dispatcher" in functions, "L1 dispatcher should be included"
        assert "persister" in functions, "L2 persister should be included"
        assert "adt-updater" in functions, "L4 adt-updater should be included"
    
    def test_azure_includes_l3_functions(self, all_azure_config):
        """Azure should include L3 storage functions."""
        functions = get_functions_for_provider_build("azure", all_azure_config)
        assert "hot-reader" in functions, "L3 hot-reader should be included"
        assert "hot-to-cold-mover" in functions, "L3 hot-to-cold-mover should be included"
    
    # =========================================================================
    # GCP Tests
    # =========================================================================
    
    def test_gcp_handles_google_config_name(self, all_gcp_config):
        """
        GCP should handle 'google' in config vs 'gcp' in registry.
        
        This is a critical test for the naming mismatch fix.
        """
        functions = get_functions_for_provider_build("gcp", all_gcp_config)
        assert len(functions) > 0, "GCP should return functions when config uses 'google'"
        assert "dispatcher" in functions, "GCP should include dispatcher"
        assert "persister" in functions, "GCP should include persister"
    
    def test_gcp_excludes_azure_only_functions(self, all_gcp_config):
        """GCP should NOT include Azure-only functions."""
        functions = get_functions_for_provider_build("gcp", all_gcp_config)
        assert "adt-updater" not in functions, "Azure-only adt-updater should NOT be in GCP"
    
    def test_gcp_excludes_aws_only_functions(self, all_gcp_config):
        """GCP should NOT include AWS-only functions."""
        functions = get_functions_for_provider_build("gcp", all_gcp_config)
        # digital-twin-data-connector is AWS-only (TwinMaker)
        assert "digital-twin-data-connector" not in functions, "AWS-only connector should NOT be in GCP"


class TestOptionalFunctionsWithFlags:
    """Tests for optional function inclusion based on optimization flags."""
    
    @pytest.fixture
    def all_aws_config(self):
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws",
        }
    
    def test_event_checker_excluded_without_flag(self, all_aws_config):
        """event-checker should be EXCLUDED when useEventChecking is False."""
        functions = get_functions_for_provider_build("aws", all_aws_config, {})
        assert "event-checker" not in functions, "event-checker should NOT be included without flag"
    
    def test_event_checker_included_with_flag(self, all_aws_config):
        """event-checker should be INCLUDED when useEventChecking is True."""
        functions = get_functions_for_provider_build(
            "aws", all_aws_config, {"useEventChecking": True}
        )
        assert "event-checker" in functions, "event-checker SHOULD be included when useEventChecking=True"
    
    def test_event_feedback_excluded_without_flag(self, all_aws_config):
        """event-feedback should be EXCLUDED when returnFeedbackToDevice is False."""
        functions = get_functions_for_provider_build("aws", all_aws_config, {})
        assert "event-feedback" not in functions, "event-feedback should NOT be included without flag"
    
    def test_event_feedback_included_with_flag(self, all_aws_config):
        """event-feedback should be INCLUDED when returnFeedbackToDevice is True."""
        functions = get_functions_for_provider_build(
            "aws", all_aws_config, {"returnFeedbackToDevice": True}
        )
        assert "event-feedback" in functions, "event-feedback SHOULD be included when returnFeedbackToDevice=True"
    
    def test_both_optional_functions_included(self, all_aws_config):
        """Both optional functions should be included when both flags are True."""
        functions = get_functions_for_provider_build(
            "aws", all_aws_config, 
            {"useEventChecking": True, "returnFeedbackToDevice": True}
        )
        assert "event-checker" in functions, "event-checker should be included"
        assert "event-feedback" in functions, "event-feedback should be included"
    
    def test_azure_optional_functions_with_flags(self):
        """Azure should also respect optimization flags for optional functions."""
        azure_config = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
        }
        functions = get_functions_for_provider_build(
            "azure", azure_config, {"useEventChecking": True}
        )
        assert "event-checker" in functions, "Azure event-checker should be included with flag"


class TestNoHardcodedLists:
    """Meta-tests to verify no hardcoded lists in package_builder.py."""
    
    def test_no_append_in_source(self):
        """Verify no hardcoded .append() calls for functions_to_build."""
        import inspect
        from src.providers.terraform import package_builder
        
        source = inspect.getsource(package_builder)
        
        assert "functions_to_build.append" not in source, \
            "package_builder should not contain hardcoded .append() calls"
        assert "functions_to_build.extend" not in source, \
            "package_builder should not contain hardcoded .extend() calls"
    
    def test_imports_registry_function(self):
        """Verify package_builder imports the registry function."""
        import inspect
        from src.providers.terraform import package_builder
        
        source = inspect.getsource(package_builder)
        
        assert "from src.function_registry import" in source, \
            "package_builder should import from function_registry"
        assert "get_functions_for_provider_build" in source, \
            "package_builder should use get_functions_for_provider_build"
