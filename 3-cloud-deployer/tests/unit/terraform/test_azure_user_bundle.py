"""
Tests for Azure user function bundling (process.py pattern).
"""

import pytest
import zipfile
import io
import os
import json
from pathlib import Path
from src.providers.terraform.package_builder import build_azure_user_bundle

class TestAzureUserBundle:
    
    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a mock project directory."""
        proj = tmp_path / "project"
        proj.mkdir()
        (proj / "azure_functions").mkdir()
        return proj
        
    def test_skips_non_azure_provider(self, project_dir):
        """Should return None if layer_2_provider is not azure."""
        providers = {"layer_2_provider": "aws"}
        result = build_azure_user_bundle(project_dir, providers)
        assert result is None

    def test_skips_missing_directory(self, tmp_path):
        """Should return None if azure_functions directory missing."""
        providers = {"layer_2_provider": "azure"}
        # tmp_path has no azure_functions
        result = build_azure_user_bundle(tmp_path, providers)
        assert result is None
        
    def test_skips_empty_functions(self, project_dir):
        """Should return None if no user functions found."""
        providers = {"layer_2_provider": "azure"}
        result = build_azure_user_bundle(project_dir, providers)
        assert result is None

    def test_process_py_pattern_bundled(self, project_dir):
        """Should discover and bundle process.py functions."""
        user_funcs = project_dir / "azure_functions"
        
        # Create processor with process.py
        p1 = user_funcs / "processors" / "p1"
        p1.mkdir(parents=True)
        (p1 / "process.py").write_text("""
def process(payload):
    return payload
""")
        
        providers = {"layer_2_provider": "azure"}
        zip_path = build_azure_user_bundle(project_dir, providers)
        
        assert zip_path is not None
        assert zip_path.exists()
        
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "function_app.py" in names
            content = zf.read("function_app.py").decode('utf-8')
            # Check register call
            assert "register_functions" in content
            assert "p1" in content

    def test_legacy_function_app_ignored(self, project_dir):
        """Legacy function_app.py should be IGNORED."""
        user_funcs = project_dir / "azure_functions"
        
        # Create legacy function
        l1 = user_funcs / "processors" / "legacy1"
        l1.mkdir(parents=True)
        (l1 / "function_app.py").write_text("LEGACY CODE")
        
        providers = {"layer_2_provider": "azure"}
        zip_path = build_azure_user_bundle(project_dir, providers)
        
        # Should be None because we only have legacy, which is ignored
        assert zip_path is None

    def test_mixed_patterns(self, project_dir):
        """Should only bundle process.py functions, ignoring legacy ones."""
        user_funcs = project_dir / "azure_functions"
        
        # Valid process.py
        p1 = user_funcs / "processors" / "p1"
        p1.mkdir(parents=True)
        (p1 / "process.py").write_text("def process(x): return x")
        
        # Legacy function_app.py
        l1 = user_funcs / "processors" / "legacy1"
        l1.mkdir(parents=True)
        (l1 / "function_app.py").write_text("LEGACY")
        
        providers = {"layer_2_provider": "azure"}
        zip_path = build_azure_user_bundle(project_dir, providers)
        
        assert zip_path is not None
        
        with zipfile.ZipFile(zip_path) as zf:
            content = zf.read("function_app.py").decode('utf-8')
            assert "p1" in content
            assert "legacy1" not in content
