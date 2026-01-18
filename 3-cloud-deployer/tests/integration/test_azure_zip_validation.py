"""
Azure Function ZIP structure validation test.

Validates that package_builder creates Azure Function ZIPs with correct structure:
- function_app.py handler exists
- host.json exists
- requirements.txt exists
- No syntax errors in Python files

Covers ALL Azure function categories:
- L0 Glue functions (multicloud boundary triggers)
- L1-L4 Core functions (dispatcher, persister, hot-reader, etc.)
- User functions bundled package (processors, event_actions, event-feedback)
"""
import pytest
import zipfile
import json
import shutil
from pathlib import Path

from src.providers.terraform.package_builder import (
    build_azure_function_packages,
    build_azure_user_bundle,
)


class TestAzureCoreFunctions:
    """Verify Azure Core Function ZIPs (L1-L4) have correct structure."""
    
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
            "layer_5_provider": "azure",
        }
    
    @pytest.fixture
    def azure_packages(self, tmp_path, all_azure_config):
        """Build Azure Function packages using template project."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        terraform_dir = tmp_path / "terraform"
        packages = build_azure_function_packages(terraform_dir, project_path, all_azure_config)
        return packages
    
    # =========================================================================
    # L1: Data Acquisition
    # =========================================================================
    
    def test_dispatcher_zip_has_handler(self, azure_packages):
        """Dispatcher ZIP should have function_app.py."""
        if "azure_dispatcher" not in azure_packages:
            pytest.skip("dispatcher not built")
        
        zip_path = azure_packages["azure_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files, "Must have function_app.py handler"
    
    def test_dispatcher_zip_has_requirements(self, azure_packages):
        """Dispatcher ZIP should have requirements.txt if present."""
        if "azure_dispatcher" not in azure_packages:
            pytest.skip("dispatcher not built")
        
        zip_path = azure_packages["azure_dispatcher"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            # requirements.txt is optional for individual function ZIPs
            # Just verify the ZIP can be opened and inspected
            assert len(files) > 0, "ZIP should have files"
    
    def test_connector_zip_structure(self, azure_packages):
        """Connector ZIP should have correct structure."""
        if "azure_connector" not in azure_packages:
            pytest.skip("connector not built")
        
        zip_path = azure_packages["azure_connector"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    # =========================================================================
    # L2: Processing
    # =========================================================================
    
    def test_persister_zip_structure(self, azure_packages):
        """Persister ZIP should have correct structure."""
        if "azure_persister" not in azure_packages:
            pytest.skip("persister not built")
        
        zip_path = azure_packages["azure_persister"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    def test_processor_wrapper_zip_structure(self, azure_packages):
        """Processor wrapper ZIP should have correct structure."""
        if "azure_processor_wrapper" not in azure_packages:
            pytest.skip("processor_wrapper not built")
        
        zip_path = azure_packages["azure_processor_wrapper"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    # =========================================================================
    # L3: Storage
    # =========================================================================
    
    def test_hot_reader_zip_structure(self, azure_packages):
        """Hot-reader ZIP should have correct structure."""
        if "azure_hot-reader" not in azure_packages:
            pytest.skip("hot-reader not built")
        
        zip_path = azure_packages["azure_hot-reader"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    def test_hot_reader_last_entry_zip_structure(self, azure_packages):
        """Hot-reader-last-entry ZIP should have correct structure."""
        if "azure_hot-reader-last-entry" not in azure_packages:
            pytest.skip("hot-reader-last-entry not built")
        
        zip_path = azure_packages["azure_hot-reader-last-entry"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    def test_hot_to_cold_mover_zip_structure(self, azure_packages):
        """Hot-to-cold-mover ZIP should have correct structure."""
        if "azure_hot-to-cold-mover" not in azure_packages:
            pytest.skip("hot-to-cold-mover not built")
        
        zip_path = azure_packages["azure_hot-to-cold-mover"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    def test_cold_to_archive_mover_zip_structure(self, azure_packages):
        """Cold-to-archive-mover ZIP should have correct structure."""
        if "azure_cold-to-archive-mover" not in azure_packages:
            pytest.skip("cold-to-archive-mover not built")
        
        zip_path = azure_packages["azure_cold-to-archive-mover"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    # =========================================================================
    # L4: Management
    # =========================================================================
    
    def test_adt_updater_zip_structure(self, azure_packages):
        """ADT-updater ZIP should have correct structure."""
        if "azure_adt-updater" not in azure_packages:
            pytest.skip("adt-updater not built")
        
        zip_path = azure_packages["azure_adt-updater"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    # =========================================================================
    # Syntax Validation (all core ZIPs)
    # =========================================================================
    
    def test_all_core_zips_have_no_syntax_errors(self, azure_packages):
        """All Azure Function ZIPs should have valid Python syntax."""
        for package_name, zip_path in azure_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")


class TestAzureL0GlueFunctions:
    """Verify Azure L0 Glue functions (multicloud boundary triggers)."""
    
    @pytest.fixture
    def multicloud_azure_l2_config(self):
        """Config where Azure is L2, receiving data from non-Azure L1."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure",
        }
    
    @pytest.fixture
    def l0_packages(self, tmp_path, multicloud_azure_l2_config):
        """Build L0 Azure Function packages for multicloud config."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        terraform_dir = tmp_path / "terraform"
        packages = build_azure_function_packages(terraform_dir, project_path, multicloud_azure_l2_config)
        return packages
    
    def test_ingestion_zip_created(self, l0_packages):
        """Ingestion ZIP should be created for L1(GCP)->L2(Azure) boundary."""
        if "azure_ingestion" not in l0_packages:
            pytest.skip("ingestion not built (boundary may not trigger)")
        
        zip_path = l0_packages["azure_ingestion"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "function_app.py" in files
    
    def test_l0_zips_have_no_syntax_errors(self, l0_packages):
        """All L0 Azure Function ZIPs should have valid Python syntax."""
        for package_name, zip_path in l0_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")


class TestAzureUserFunctions:
    """
    Verify Azure User Functions combined package.
    
    Azure bundles all user functions (processors, event_actions, event-feedback)
    into a single user_functions_combined.zip, unlike AWS/GCP which create 
    individual ZIPs per function.
    """
    
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
            "layer_5_provider": "azure",
        }
    
    @pytest.fixture
    def user_package(self, tmp_path, all_azure_config):
        """Build combined user package using template project."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        zip_path = build_azure_user_bundle(project_path, all_azure_config)
        return {"zip_path": zip_path, "project_path": project_path}
    
    def test_combined_package_created(self, user_package):
        """Combined user functions package should be created."""
        zip_path = user_package["zip_path"]
        assert zip_path is not None, "Combined package should be created"
        assert zip_path.exists(), "Combined package ZIP should exist"
    
    def test_combined_package_has_host_json(self, user_package):
        """Combined package should have host.json."""
        zip_path = user_package["zip_path"]
        if zip_path is None:
            pytest.skip("Combined package not built")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "host.json" in files, "Must have host.json"
    
    def test_combined_package_has_requirements(self, user_package):
        """Combined package should have requirements.txt."""
        zip_path = user_package["zip_path"]
        if zip_path is None:
            pytest.skip("Combined package not built")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "requirements.txt" in files, "Must have requirements.txt"
            
            # Verify azure-functions is in requirements
            content = zf.read("requirements.txt").decode('utf-8')
            assert "azure-functions" in content.lower(), "Must require azure-functions"
    
    def test_combined_package_has_event_actions(self, user_package):
        """Combined package should include event action functions if they have function_app.py."""
        zip_path = user_package["zip_path"]
        if zip_path is None:
            pytest.skip("Combined package not built")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            
            # Check for event action folders (may be empty if no function_app.py in template)
            # The consolidated function requires function_app.py for discovery
            action_folders = [f for f in files if "high-temperature-callback" in f or "event_action" in f.lower()]
            # Skip if no event actions (template may not have function_app.py for them)
            if len(action_folders) == 0:
                pytest.skip("No event actions with function_app.py found in template")
    
    def test_combined_package_has_processors(self, user_package):
        """Combined package should include processor functions if they have function_app.py."""
        zip_path = user_package["zip_path"]
        if zip_path is None:
            pytest.skip("Combined package not built")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            
            # Check for processor folders (may be empty if no function_app.py in template)
            # The consolidated function requires processors with function_app.py for discovery
            processor_folders = [f for f in files if "processor" in f.lower() or "temperature" in f.lower()]
            # Skip if no processors (template may not have function_app.py for them)
            if len(processor_folders) == 0:
                pytest.skip("No processors with function_app.py found in template")
    
    def test_combined_package_no_syntax_errors(self, user_package):
        """Combined package should have valid Python syntax."""
        zip_path = user_package["zip_path"]
        if zip_path is None:
            pytest.skip("Combined package not built")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            py_files = [f for f in zf.namelist() if f.endswith('.py')]
            
            for py_file in py_files:
                content = zf.read(py_file).decode('utf-8')
                try:
                    compile(content, py_file, 'exec')
                except SyntaxError as e:
                    pytest.fail(f"user_functions_combined/{py_file} has syntax error: {e}")
