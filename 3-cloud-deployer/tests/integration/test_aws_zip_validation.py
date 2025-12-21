"""
AWS Lambda ZIP structure validation test.

Validates that package_builder creates Lambda ZIPs with correct structure:
- lambda_function.py handler exists
- _shared/ folder is included
- No syntax errors in Python files
"""
import pytest
import zipfile
from pathlib import Path

from src.providers.terraform.package_builder import build_aws_lambda_packages


class TestAWSLambdaZipStructure:
    """Verify AWS Lambda ZIPs have correct structure."""
    
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
    def aws_packages(self, tmp_path, all_aws_config):
        """Build AWS Lambda packages using template project."""
        import shutil
        
        # Copy template project to tmp_path
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        # Build packages
        terraform_dir = tmp_path / "terraform" # Dummy path
        packages = build_aws_lambda_packages(terraform_dir, project_path, all_aws_config)
        return packages
    
    def test_dispatcher_zip_has_handler(self, aws_packages):
        """Dispatcher ZIP should have lambda_function.py."""
        if "aws_dispatcher" not in aws_packages:
            pytest.skip("dispatcher not built (may not exist in source)")
        
        zip_path = aws_packages["aws_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files, "Must have lambda_function.py handler"
    
    def test_dispatcher_zip_has_shared_folder(self, aws_packages):
        """Dispatcher ZIP should have _shared/ folder."""
        if "aws_dispatcher" not in aws_packages:
            pytest.skip("dispatcher not built")
        
        zip_path = aws_packages["aws_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0, "Must have _shared/ folder"
    
    def test_persister_zip_structure(self, aws_packages):
        """Persister ZIP should have correct structure."""
        if "aws_persister" not in aws_packages:
            pytest.skip("persister not built")
        
        zip_path = aws_packages["aws_persister"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
            
            # Check for _shared
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0
    
    def test_hot_reader_zip_structure(self, aws_packages):
        """Hot-reader ZIP should have correct structure."""
        if "aws_hot-reader" not in aws_packages:
            pytest.skip("hot-reader not built")
        
        zip_path = aws_packages["aws_hot-reader"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    def test_all_zips_have_no_syntax_errors(self, aws_packages):
        """All Lambda ZIPs should have valid Python syntax."""
        for package_name, zip_path in aws_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Check all .py files for syntax errors
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")
