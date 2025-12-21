"""
GCP Cloud Function ZIP structure validation test.

Validates that package_builder creates Cloud Function ZIPs with correct structure:
- main.py handler exists
- _shared/ folder is included
- requirements.txt exists
- No syntax errors in Python files
"""
import pytest
import zipfile
from pathlib import Path

from src.providers.terraform.package_builder import build_gcp_cloud_function_packages


class TestGCPCloudFunctionZipStructure:
    """Verify GCP Cloud Function ZIPs have correct structure."""
    
    @pytest.fixture
    def all_gcp_config(self):
        """Config where all layers are on GCP."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
            "layer_4_provider": "google",
        }
    
    @pytest.fixture
    def gcp_packages(self, tmp_path, all_gcp_config):
        """Build GCP Cloud Function packages using template project."""
        import shutil
        
        # Copy template project to tmp_path
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        # Build packages
        terraform_dir = tmp_path / "terraform" # Dummy path
        packages = build_gcp_cloud_function_packages(terraform_dir, project_path, all_gcp_config)
        return packages
    
    def test_dispatcher_zip_has_handler(self, gcp_packages):
        """Dispatcher ZIP should have main.py."""
        if "gcp_dispatcher" not in gcp_packages:
            pytest.skip("dispatcher not built (may not exist in source)")
        
        zip_path = gcp_packages["gcp_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files, "Must have main.py handler"
    
    def test_dispatcher_zip_has_requirements(self, gcp_packages):
        """Dispatcher ZIP should have requirements.txt."""
        if "gcp_dispatcher" not in gcp_packages:
            pytest.skip("dispatcher not built")
        
        zip_path = gcp_packages["gcp_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "requirements.txt" in files, "Must have requirements.txt"
    
    def test_dispatcher_zip_has_shared_folder(self, gcp_packages):
        """Dispatcher ZIP should have _shared/ folder."""
        if "gcp_dispatcher" not in gcp_packages:
            pytest.skip("dispatcher not built")
        
        zip_path = gcp_packages["gcp_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0, "Must have _shared/ folder"
    
    def test_persister_zip_structure(self, gcp_packages):
        """Persister ZIP should have correct structure."""
        if "gcp_persister" not in gcp_packages:
            pytest.skip("persister not built")
        
        zip_path = gcp_packages["gcp_persister"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
            assert "requirements.txt" in files
            
            # Check for _shared
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0
    
    def test_all_zips_have_no_syntax_errors(self, gcp_packages):
        """All Cloud Function ZIPs should have valid Python syntax."""
        for package_name, zip_path in gcp_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Check all .py files for syntax errors
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")
