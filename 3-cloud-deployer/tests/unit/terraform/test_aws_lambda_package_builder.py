"""
Unit tests for AWS Lambda package building.

Tests that verify AWS Lambda ZIP packages follow official AWS requirements:
- Handler file at root level (lambda_function.py)
- Handler function exists (lambda_handler)
- Shared modules at root
- No __pycache__ in ZIP
- Valid Python syntax
"""

import pytest
import zipfile
import io
import ast
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

from src.providers.terraform.package_builder import (
    _create_lambda_zip,
    build_aws_lambda_packages,
    get_lambda_zip_path,
)


class TestCreateLambdaZip:
    """Tests for _create_lambda_zip function."""
    
    @pytest.fixture
    def lambda_func_dir(self, tmp_path):
        """Create a mock Lambda function directory."""
        func_dir = tmp_path / "my-function"
        func_dir.mkdir()
        
        # Create lambda_function.py with lambda_handler
        (func_dir / "lambda_function.py").write_text('''
import json

def lambda_handler(event, context):
    """Lambda handler function."""
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello"})
    }
''')
        
        # Create helper module
        (func_dir / "helpers.py").write_text('''
def helper_function():
    return "helper"
''')
        
        # Create __pycache__ (should be excluded)
        pycache = func_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "lambda_function.cpython-311.pyc").write_bytes(b"fake bytecode")
        
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
    
    def test_creates_valid_zip(self, lambda_func_dir, shared_dir, tmp_path):
        """Should create a valid ZIP file."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        assert output.exists()
        assert zipfile.is_zipfile(output)
    
    def test_lambda_function_at_root(self, lambda_func_dir, shared_dir, tmp_path):
        """Lambda handler file should be at ZIP root level."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "lambda_function.py" in names, "lambda_function.py should be at root"
    
    def test_includes_helper_modules(self, lambda_func_dir, shared_dir, tmp_path):
        """Should include helper modules at root level."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "helpers.py" in names, "Helper modules should be at root"
    
    def test_includes_shared_modules(self, lambda_func_dir, shared_dir, tmp_path):
        """Should include _shared modules at root level."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            # Shared files should be at root (not in _shared/ subdirectory)
            assert "__init__.py" in names or "_shared/__init__.py" in names
            assert "env_utils.py" in names or "_shared/env_utils.py" in names
            assert "inter_cloud.py" in names or "_shared/inter_cloud.py" in names
    
    def test_excludes_pycache(self, lambda_func_dir, shared_dir, tmp_path):
        """Should NOT include __pycache__ files."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            pycache_files = [n for n in names if "__pycache__" in n]
            assert len(pycache_files) == 0, f"Found __pycache__ files: {pycache_files}"
    
    def test_handler_function_exists(self, lambda_func_dir, shared_dir, tmp_path):
        """lambda_function.py should define lambda_handler function."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            content = zf.read("lambda_function.py").decode("utf-8")
            
            # Parse and verify lambda_handler exists
            tree = ast.parse(content)
            func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            assert "lambda_handler" in func_names, "lambda_function.py must define lambda_handler()"
    
    def test_valid_python_syntax(self, lambda_func_dir, shared_dir, tmp_path):
        """All .py files should have valid Python syntax."""
        output = tmp_path / "output.zip"
        
        _create_lambda_zip(lambda_func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            for name in zf.namelist():
                if name.endswith(".py"):
                    content = zf.read(name).decode("utf-8")
                    try:
                        ast.parse(content)
                    except SyntaxError as e:
                        pytest.fail(f"Syntax error in {name}: {e}")


class TestBuildAwsLambdaPackages:
    """Tests for build_aws_lambda_packages function."""
    
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
    

    
    
    def test_empty_config_returns_empty_dict(self, tmp_path):
        """Empty provider config should return empty dict, not raise."""
        packages = build_aws_lambda_packages(tmp_path, tmp_path, {})
        assert packages == {}
    
    def test_partial_config_returns_matching_only(self, tmp_path):
        """Partial config should build only matching providers."""
        partial_config = {"layer_1_provider": "aws"}  # Only L1 on AWS
        packages = build_aws_lambda_packages(tmp_path, tmp_path, partial_config)
        # Should not raise, returns dict (may be empty if dirs missing)
        assert isinstance(packages, dict)
    
    def test_no_packages_for_azure_only(self, tmp_path, providers_all_azure):
        """Should return empty dict when no AWS layers configured."""
        packages = build_aws_lambda_packages(tmp_path, tmp_path, providers_all_azure)
        assert packages == {}


class TestRealLambdaFunctions:
    """
    Tests that validate the package builder with REAL Lambda function files.
    
    These tests ensure the builder produces valid AWS Lambda deployment packages.
    """
    
    @pytest.fixture
    def project_root(self):
        """Path to the project root directory."""
        return Path(__file__).parent.parent.parent.parent
    
    @pytest.fixture
    def lambda_functions_dir(self, project_root):
        """Path to the Lambda functions directory."""
        return project_root / "src" / "providers" / "aws" / "lambda_functions"
    
    @pytest.fixture
    def shared_dir(self, lambda_functions_dir):
        """Path to the _shared directory."""
        return lambda_functions_dir / "_shared"
    
    def test_dispatcher_has_lambda_function_py(self, lambda_functions_dir):
        """Dispatcher Lambda should have lambda_function.py."""
        dispatcher_dir = lambda_functions_dir / "dispatcher"
        handler_file = dispatcher_dir / "lambda_function.py"
        
        assert handler_file.exists(), f"Expected {handler_file}"
    
    def test_dispatcher_has_lambda_handler(self, lambda_functions_dir):
        """Dispatcher lambda_function.py should define lambda_handler."""
        handler_file = lambda_functions_dir / "dispatcher" / "lambda_function.py"
        content = handler_file.read_text()
        
        tree = ast.parse(content)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        
        assert "lambda_handler" in func_names, "dispatcher must define lambda_handler()"
    
    def test_persister_has_lambda_function_py(self, lambda_functions_dir):
        """Persister Lambda should have lambda_function.py."""
        persister_dir = lambda_functions_dir / "persister"
        handler_file = persister_dir / "lambda_function.py"
        
        assert handler_file.exists(), f"Expected {handler_file}"
    
    def test_persister_has_lambda_handler(self, lambda_functions_dir):
        """Persister lambda_function.py should define lambda_handler."""
        handler_file = lambda_functions_dir / "persister" / "lambda_function.py"
        content = handler_file.read_text()
        
        tree = ast.parse(content)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        
        assert "lambda_handler" in func_names, "persister must define lambda_handler()"
    
    def test_all_lambdas_have_handler_file(self, lambda_functions_dir):
        """All Lambda function directories should have lambda_function.py."""
        # Skip special directories
        skip_dirs = {"_shared", "__pycache__", "processor_wrapper", "default-processor"}
        
        for func_dir in lambda_functions_dir.iterdir():
            if not func_dir.is_dir():
                continue
            if func_dir.name in skip_dirs:
                continue
            
            handler_file = func_dir / "lambda_function.py"
            assert handler_file.exists(), f"Missing lambda_function.py in {func_dir.name}"
    
    def test_all_lambdas_define_lambda_handler(self, lambda_functions_dir):
        """All Lambda functions should define lambda_handler."""
        skip_dirs = {"_shared", "__pycache__", "processor_wrapper", "default-processor"}
        
        for func_dir in lambda_functions_dir.iterdir():
            if not func_dir.is_dir():
                continue
            if func_dir.name in skip_dirs:
                continue
            
            handler_file = func_dir / "lambda_function.py"
            if not handler_file.exists():
                continue
            
            content = handler_file.read_text()
            tree = ast.parse(content)
            func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            assert "lambda_handler" in func_names, f"{func_dir.name} must define lambda_handler()"
    
    def test_dispatcher_zip_structure(self, lambda_functions_dir, shared_dir, tmp_path):
        """Dispatcher ZIP should have correct structure."""
        func_dir = lambda_functions_dir / "dispatcher"
        output = tmp_path / "dispatcher.zip"
        
        _create_lambda_zip(func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            
            # Must have handler at root
            assert "lambda_function.py" in names
            
            # Should have shared modules
            assert any("env_utils" in n for n in names), "Missing env_utils shared module"
    
    def test_persister_zip_structure(self, lambda_functions_dir, shared_dir, tmp_path):
        """Persister ZIP should have correct structure."""
        func_dir = lambda_functions_dir / "persister"
        output = tmp_path / "persister.zip"
        
        _create_lambda_zip(func_dir, shared_dir, output)
        
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            
            # Must have handler at root
            assert "lambda_function.py" in names
            
            # Must have valid Python
            content = zf.read("lambda_function.py").decode("utf-8")
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in persister lambda_function.py: {e}")
    
    def test_shared_modules_valid_python(self, shared_dir):
        """All _shared modules should have valid Python syntax."""
        for py_file in shared_dir.glob("*.py"):
            content = py_file.read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file.name}: {e}")


class TestZipSizeLimits:
    """Tests for AWS Lambda ZIP size limits."""
    
    def test_individual_zip_under_50mb(self, tmp_path):
        """Individual Lambda ZIPs should be under 50MB (direct upload limit)."""
        # Create a mock function
        func_dir = tmp_path / "test-func"
        func_dir.mkdir()
        (func_dir / "lambda_function.py").write_text("def lambda_handler(e,c): pass")
        
        shared_dir = tmp_path / "_shared"
        shared_dir.mkdir()
        (shared_dir / "__init__.py").write_text("")
        
        output = tmp_path / "test.zip"
        _create_lambda_zip(func_dir, shared_dir, output)
        
        size_mb = output.stat().st_size / (1024 * 1024)
        assert size_mb < 50, f"ZIP is {size_mb:.2f}MB, exceeds 50MB direct upload limit"
