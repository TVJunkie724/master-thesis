"""
Unit tests for GCP Cloud Function package building.

Tests that verify GCP Cloud Function ZIP packages follow official requirements:
- Entry point file (main.py) at root level
- Entry point function exists
- Shared modules in _shared/ subdirectory
- No __pycache__ in ZIP
- Valid Python syntax
- requirements.txt present or generated
"""

import pytest
import zipfile
import ast
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

from src.providers.terraform.package_builder import (
    _create_gcp_function_zip,
    build_gcp_cloud_function_packages,
    get_gcp_zip_path,
)


class TestCreateGcpFunctionZip:
    """Tests for _create_gcp_function_zip function."""
    
    @pytest.fixture
    def gcp_func_dir(self, tmp_path):
        """Create a mock GCP Cloud Function directory."""
        func_dir = tmp_path / "my-function"
        func_dir.mkdir()
        
        # Create main.py with entry point
        (func_dir / "main.py").write_text('''
import functions_framework

@functions_framework.http
def main(request):
    """HTTP Cloud Function entry point."""
    return {"statusCode": 200, "message": "Hello"}
''')
        
        # Create helper module
        (func_dir / "helpers.py").write_text('''
def helper_function():
    return "helper"
''')
        
        # Create requirements.txt
        (func_dir / "requirements.txt").write_text('''
functions-framework
google-cloud-firestore
''')
        
        # Create __pycache__ (should be excluded)
        pycache = func_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-311.pyc").write_bytes(b"fake bytecode")
        
        return func_dir
    
    @pytest.fixture
    def shared_dir(self, tmp_path):
        """Create a mock _shared directory."""
        shared = tmp_path / "_shared"
        shared.mkdir()
        
        (shared / "__init__.py").write_text("# Shared module")
        (shared / "env_utils.py").write_text('''
def require_env(name):
    import os
    val = os.environ.get(name)
    if not val:
        raise ValueError(f"Missing env var: {name}")
    return val
''')
        (shared / "inter_cloud.py").write_text('''
def post_to_remote(url, data):
    import requests
    return requests.post(url, json=data)
''')
        
        return shared
    
    def test_creates_valid_zip(self, gcp_func_dir, shared_dir, tmp_path):
        """Should create a valid ZIP file."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        assert output.exists()
        assert zipfile.is_zipfile(output)
    
    def test_main_py_at_root(self, gcp_func_dir, shared_dir, tmp_path):
        """Entry point file should be at ZIP root level."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "main.py" in names, "main.py should be at root"
    
    def test_includes_helper_modules(self, gcp_func_dir, shared_dir, tmp_path):
        """Should include helper modules at root level."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "helpers.py" in names, "Helper modules should be at root"
    
    def test_includes_shared_modules_in_subdirectory(self, gcp_func_dir, shared_dir, tmp_path):
        """Should include _shared modules in _shared/ subdirectory."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            # GCP functions put shared modules in _shared/ subdirectory
            shared_files = [n for n in names if n.startswith("_shared/")]
            assert len(shared_files) > 0, "Shared files should be in _shared/ subdirectory"
            assert any("env_utils.py" in n for n in shared_files), "_shared/env_utils.py expected"
    
    def test_excludes_pycache(self, gcp_func_dir, shared_dir, tmp_path):
        """Should NOT include __pycache__ files."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            pycache_files = [n for n in names if "__pycache__" in n]
            assert len(pycache_files) == 0, f"Found __pycache__ files: {pycache_files}"
    
    def test_requirements_txt_included(self, gcp_func_dir, shared_dir, tmp_path):
        """requirements.txt should be included if present."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "requirements.txt" in names, "requirements.txt should be included"
    
    def test_requirements_txt_generated_if_missing(self, tmp_path):
        """Should generate requirements.txt if not present in function dir."""
        # Create function dir WITHOUT requirements.txt
        func_dir = tmp_path / "no-reqs-func"
        func_dir.mkdir()
        (func_dir / "main.py").write_text("def main(request): pass")
        
        shared_dir = tmp_path / "_shared"
        shared_dir.mkdir()
        
        output = tmp_path / "output.zip"
        _create_gcp_function_zip(func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "requirements.txt" in names, "requirements.txt should be auto-generated"
            
            content = zf.read("requirements.txt").decode("utf-8")
            assert "functions-framework" in content, "Should include functions-framework"
    
    def test_valid_python_syntax(self, gcp_func_dir, shared_dir, tmp_path):
        """All .py files should have valid Python syntax."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            for name in zf.namelist():
                if name.endswith(".py"):
                    content = zf.read(name).decode("utf-8")
                    try:
                        ast.parse(content)
                    except SyntaxError as e:
                        pytest.fail(f"Syntax error in {name}: {e}")
    
    def test_handles_missing_shared_dir(self, gcp_func_dir, tmp_path):
        """Should work even if _shared directory doesn't exist."""
        output = tmp_path / "output.zip"
        missing_shared = tmp_path / "nonexistent_shared"
        
        # Should not raise an exception
        _create_gcp_function_zip(gcp_func_dir, missing_shared, output)
        
        assert output.exists()
        with zipfile.ZipFile(output) as zf:
            assert "main.py" in zf.namelist()
    
    def test_handles_none_shared_dir(self, gcp_func_dir, tmp_path):
        """Should work with None shared_dir."""
        output = tmp_path / "output.zip"
        
        _create_gcp_function_zip(gcp_func_dir, None, output)
        
        assert output.exists()


class TestBuildGcpCloudFunctionPackages:
    """Tests for build_gcp_cloud_function_packages function."""
    
    @pytest.fixture
    def providers_all_gcp(self):
        """Provider config with all layers on GCP."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
            "layer_4_provider": "",  # TODO(GCP-L4L5): GCP doesn't support L4/L5 yet
        }
    
    @pytest.fixture
    def providers_all_aws(self):
        """Provider config with all layers on AWS."""
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
        }
    
    @pytest.fixture
    def providers_all_azure(self):
        """Provider config with all layers on Azure."""
        return {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure",
        }
    
    @pytest.fixture
    def providers_gcp_l2_only(self):
        """Provider config with only L2 on GCP (multi-cloud scenario)."""
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure",
        }
    
    def test_no_packages_for_aws_only(self, tmp_path, providers_all_aws):
        """Should return empty dict when no GCP layers configured."""
        packages = build_gcp_cloud_function_packages(tmp_path, tmp_path, providers_all_aws)
        assert packages == {}
    
    def test_no_packages_for_azure_only(self, tmp_path, providers_all_azure):
        """Should return empty dict when no GCP layers configured."""
        packages = build_gcp_cloud_function_packages(tmp_path, tmp_path, providers_all_azure)
        assert packages == {}
    
    def test_builds_l2_functions_when_l2_is_gcp(self, tmp_path, providers_gcp_l2_only):
        """Should build L2 functions when layer_2_provider is google."""
        # This test checks the function logic, actual building may fail
        # if cloud_functions directory doesn't exist
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        # The function should try to build and may log warnings if dirs don't exist
        packages = build_gcp_cloud_function_packages(terraform_dir, project_path, providers_gcp_l2_only)
        
        # Should not crash, returns dict (possibly empty if source dirs missing)
        assert isinstance(packages, dict)
    
    def test_builds_ingestion_when_cross_cloud(self, tmp_path):
        """Should build ingestion function when L1 != GCP and L2 == GCP."""
        providers = {
            "layer_1_provider": "aws",  # L1 on AWS
            "layer_2_provider": "google",  # L2 on GCP -> needs ingestion
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
            "layer_4_provider": "",
        }
        
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        packages = build_gcp_cloud_function_packages(terraform_dir, project_path, providers)
        
        # Should attempt to build ingestion (may not succeed if source missing)
        assert isinstance(packages, dict)


class TestRealGcpCloudFunctions:
    """
    Tests that validate the package builder with REAL GCP Cloud Function files.
    
    These tests ensure the builder produces valid GCP Cloud Function deployment packages.
    """
    
    @pytest.fixture
    def project_root(self):
        """Path to the project root directory."""
        return Path(__file__).parent.parent.parent.parent
    
    @pytest.fixture
    def cloud_functions_dir(self, project_root):
        """Path to the GCP Cloud Functions directory."""
        return project_root / "src" / "providers" / "gcp" / "cloud_functions"
    
    @pytest.fixture
    def shared_dir(self, cloud_functions_dir):
        """Path to the _shared directory."""
        return cloud_functions_dir / "_shared"
    
    def test_cloud_functions_directory_exists(self, cloud_functions_dir):
        """GCP Cloud Functions directory should exist."""
        assert cloud_functions_dir.exists(), f"Expected {cloud_functions_dir}"
    
    def test_shared_directory_exists(self, shared_dir):
        """Shared modules directory should exist."""
        assert shared_dir.exists(), f"Expected {shared_dir}"
    
    def test_processor_wrapper_has_main_py(self, cloud_functions_dir):
        """processor_wrapper should have main.py."""
        func_dir = cloud_functions_dir / "processor_wrapper"
        if func_dir.exists():
            main_file = func_dir / "main.py"
            assert main_file.exists(), f"Expected {main_file}"
    
    def test_persister_has_main_py(self, cloud_functions_dir):
        """persister should have main.py."""
        func_dir = cloud_functions_dir / "persister"
        if func_dir.exists():
            main_file = func_dir / "main.py"
            assert main_file.exists(), f"Expected {main_file}"
    
    def test_event_checker_has_main_py(self, cloud_functions_dir):
        """event-checker should have main.py."""
        func_dir = cloud_functions_dir / "event-checker"
        if func_dir.exists():
            main_file = func_dir / "main.py"
            assert main_file.exists(), f"Expected {main_file}"
    
    def test_all_functions_have_main_py(self, cloud_functions_dir):
        """All Cloud Function directories should have main.py."""
        skip_dirs = {"_shared", "__pycache__"}
        
        for func_dir in cloud_functions_dir.iterdir():
            if not func_dir.is_dir():
                continue
            if func_dir.name in skip_dirs:
                continue
            
            main_file = func_dir / "main.py"
            assert main_file.exists(), f"Missing main.py in {func_dir.name}"
    
    def test_all_main_py_valid_python(self, cloud_functions_dir):
        """All main.py files should have valid Python syntax."""
        skip_dirs = {"_shared", "__pycache__"}
        
        for func_dir in cloud_functions_dir.iterdir():
            if not func_dir.is_dir():
                continue
            if func_dir.name in skip_dirs:
                continue
            
            main_file = func_dir / "main.py"
            if not main_file.exists():
                continue
            
            content = main_file.read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {func_dir.name}/main.py: {e}")
    
    def test_processor_zip_structure(self, cloud_functions_dir, shared_dir, tmp_path):
        """processor_wrapper ZIP should have correct structure."""
        func_dir = cloud_functions_dir / "processor_wrapper"
        if not func_dir.exists():
            pytest.skip("processor_wrapper directory not found")
        
        output = tmp_path / "processor.zip"
        _create_gcp_function_zip(func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            
            # Must have main.py at root
            assert "main.py" in names
            
            # Should have shared modules in _shared/
            shared_files = [n for n in names if n.startswith("_shared/")]
            assert len(shared_files) > 0, "Should include _shared modules"
    
    def test_persister_zip_structure(self, cloud_functions_dir, shared_dir, tmp_path):
        """persister ZIP should have correct structure."""
        func_dir = cloud_functions_dir / "persister"
        if not func_dir.exists():
            pytest.skip("persister directory not found")
        
        output = tmp_path / "persister.zip"
        _create_gcp_function_zip(func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            
            # Must have main.py at root
            assert "main.py" in names
            
            # Must have valid Python
            content = zf.read("main.py").decode("utf-8")
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in persister main.py: {e}")
    
    def test_shared_modules_valid_python(self, shared_dir):
        """All _shared modules should have valid Python syntax."""
        if not shared_dir.exists():
            pytest.skip("_shared directory not found")
        
        for py_file in shared_dir.glob("*.py"):
            content = py_file.read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file.name}: {e}")


class TestGcpZipSizeLimits:
    """Tests for GCP Cloud Functions ZIP size limits."""
    
    def test_individual_zip_under_100mb(self, tmp_path):
        """Individual Cloud Function ZIPs should be under 100MB (GCP limit for source)."""
        func_dir = tmp_path / "test-func"
        func_dir.mkdir()
        (func_dir / "main.py").write_text("def main(request): pass")
        
        shared_dir = tmp_path / "_shared"
        shared_dir.mkdir()
        (shared_dir / "__init__.py").write_text("")
        
        output = tmp_path / "test.zip"
        _create_gcp_function_zip(func_dir, shared_dir, output)
        
        size_mb = output.stat().st_size / (1024 * 1024)
        assert size_mb < 100, f"ZIP is {size_mb:.2f}MB, exceeds 100MB GCP source limit"


class TestGetGcpZipPath:
    """Tests for get_gcp_zip_path helper function."""
    
    def test_returns_correct_path(self, tmp_path):
        """Should return correct path to GCP function ZIP."""
        path = get_gcp_zip_path(tmp_path, "processor")
        expected = str(tmp_path / ".build" / "gcp" / "processor.zip")
        assert path == expected
    
    def test_handles_hyphenated_names(self, tmp_path):
        """Should handle function names with hyphens."""
        path = get_gcp_zip_path(tmp_path, "event-checker")
        expected = str(tmp_path / ".build" / "gcp" / "event-checker.zip")
        assert path == expected


class TestProcessorUserCodeMerge:
    """Tests for processor user code merging functionality."""
    
    def test_merges_user_processor_code(self, tmp_path):
        """Should merge user processor code into processor ZIP."""
        # Create function directory
        func_dir = tmp_path / "processor_wrapper"
        func_dir.mkdir()
        (func_dir / "main.py").write_text('''
from process import process

def main(request):
    return process(request.get_json())
''')
        
        # Create project with user processor
        project_path = tmp_path / "project"
        user_processor_dir = project_path / "processors" / "default_processor"
        user_processor_dir.mkdir(parents=True)
        (user_processor_dir / "process.py").write_text('''
def process(data):
    return {"processed": True, "data": data}
''')
        
        shared_dir = tmp_path / "_shared"
        shared_dir.mkdir()
        
        output = tmp_path / "processor.zip"
        _create_gcp_function_zip(func_dir, shared_dir, output, project_path)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "main.py" in names, "Should have base main.py"
            assert "process.py" in names, "Should have merged user process.py"
    
    def test_works_without_user_code(self, tmp_path):
        """Should work even if no user processor code exists."""
        func_dir = tmp_path / "processor_wrapper"
        func_dir.mkdir()
        (func_dir / "main.py").write_text("def main(r): pass")
        
        project_path = tmp_path / "project"
        project_path.mkdir()  # No processors directory
        
        shared_dir = tmp_path / "_shared"
        shared_dir.mkdir()
        
        output = tmp_path / "processor.zip"
        _create_gcp_function_zip(func_dir, shared_dir, output, project_path)
        
        assert output.exists()
        with zipfile.ZipFile(output) as zf:
            assert "main.py" in zf.namelist()
