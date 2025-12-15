"""
Unit tests for function_bundler module.

Tests the bundling of Azure Functions into per-app ZIP packages.
"""

import pytest
import zipfile
import io
from pathlib import Path
from unittest.mock import patch

from src.providers.azure.layers.function_bundler import (
    bundle_l0_functions,
    bundle_l1_functions,
    bundle_l2_functions,
    bundle_l3_functions,
    BundleError,
)


class TestBundleL0Functions:
    """Tests for bundle_l0_functions (per-boundary conditional)."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create shared files
        (azure_funcs / "requirements.txt").write_text("azure-functions")
        (azure_funcs / "host.json").write_text('{"version": "2.0"}')
        
        # Create function directories
        for func_name in ["ingestion", "hot-writer", "hot-reader", "dispatcher"]:
            func_dir = azure_funcs / func_name
            func_dir.mkdir()
            (func_dir / "__init__.py").write_text(f"# {func_name}")
            (func_dir / "function.json").write_text("{}")
        
        return tmp_path
    
    def test_requires_project_path(self):
        """Should raise ValueError if project_path is None."""
        with pytest.raises(ValueError, match="project_path is required"):
            bundle_l0_functions(None, {})
    
    def test_requires_provider_config(self, azure_functions_dir):
        """Should raise ValueError if provider config keys missing."""
        with pytest.raises(ValueError, match="Missing required provider config"):
            bundle_l0_functions(str(azure_functions_dir), {})
    
    def test_no_glue_for_single_cloud(self, azure_functions_dir):
        """Should return None when all providers are same (no cross-cloud)."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        
        zip_bytes, funcs = bundle_l0_functions(str(azure_functions_dir), providers)
        
        assert zip_bytes is None
        assert funcs == []
    
    def test_bundles_ingestion_for_l1_l2_boundary(self, azure_functions_dir):
        """Should include ingestion when L1 != L2 and L2 is azure."""
        providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        
        zip_bytes, funcs = bundle_l0_functions(str(azure_functions_dir), providers)
        
        assert zip_bytes is not None
        assert "ingestion" in funcs
        
        # Verify ZIP contains the function
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any("ingestion" in name for name in names)
    
    def test_bundles_hot_writer_for_l2_l3_boundary(self, azure_functions_dir):
        """Should include hot-writer when L2 != L3_hot and L3_hot is azure."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        
        zip_bytes, funcs = bundle_l0_functions(str(azure_functions_dir), providers)
        
        assert zip_bytes is not None
        assert "hot-writer" in funcs


class TestBundleL1Functions:
    """Tests for bundle_l1_functions."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create dispatcher function
        dispatcher = azure_funcs / "dispatcher"
        dispatcher.mkdir()
        (dispatcher / "__init__.py").write_text("# dispatcher")
        (dispatcher / "function.json").write_text("{}")
        
        return tmp_path
    
    def test_bundles_dispatcher(self, azure_functions_dir):
        """Should bundle dispatcher function."""
        zip_bytes = bundle_l1_functions(str(azure_functions_dir))
        
        assert zip_bytes is not None
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any("dispatcher" in name for name in names)


class TestBundleL2Functions:
    """Tests for bundle_l2_functions."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create persister function
        persister = azure_funcs / "persister"
        persister.mkdir()
        (persister / "__init__.py").write_text("# persister")
        
        # Create optional event-checker
        event_checker = azure_funcs / "event-checker"
        event_checker.mkdir()
        (event_checker / "__init__.py").write_text("# event-checker")
        
        return tmp_path
    
    def test_bundles_persister(self, azure_functions_dir):
        """Should bundle persister function."""
        zip_bytes = bundle_l2_functions(str(azure_functions_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any("persister" in name for name in names)
    
    def test_includes_event_checker_if_exists(self, azure_functions_dir):
        """Should include event-checker if it exists."""
        zip_bytes = bundle_l2_functions(str(azure_functions_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any("event-checker" in name for name in names)


class TestBundleL3Functions:
    """Tests for bundle_l3_functions."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create L3 functions
        for func_name in ["hot-reader", "hot-reader-last-entry", "hot-cold-mover", "cold-archive-mover"]:
            func_dir = azure_funcs / func_name
            func_dir.mkdir()
            (func_dir / "__init__.py").write_text(f"# {func_name}")
        
        return tmp_path
    
    def test_bundles_all_l3_functions(self, azure_functions_dir):
        """Should bundle all L3 functions."""
        zip_bytes = bundle_l3_functions(str(azure_functions_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any("hot-reader" in name for name in names)
            assert any("hot-cold-mover" in name for name in names)
