"""
GCP Cloud Function ZIP structure validation test.

Validates that package_builder creates Cloud Function ZIPs with correct structure:
- main.py handler exists
- _shared/ folder is included
- requirements.txt exists
- No syntax errors in Python files

Covers ALL GCP function categories:
- L0 Glue functions (multicloud boundary triggers)
- L1-L4 Core functions (dispatcher, persister, hot-reader, etc.)
- User functions (processors, event_actions, event-feedback)
"""
import pytest
import zipfile
import shutil
from pathlib import Path

from src.providers.terraform.package_builder import (
    build_gcp_cloud_function_packages,
    build_user_packages,
)


class TestGCPCoreFunctions:
    """Verify GCP Core Cloud Function ZIPs (L1-L4) have correct structure."""
    
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
            "layer_5_provider": "google",
        }
    
    @pytest.fixture
    def gcp_packages(self, tmp_path, all_gcp_config):
        """Build GCP Cloud Function packages using template project."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        terraform_dir = tmp_path / "terraform"
        packages = build_gcp_cloud_function_packages(terraform_dir, project_path, all_gcp_config)
        return packages
    
    # =========================================================================
    # L1: Data Acquisition
    # =========================================================================
    
    def test_dispatcher_zip_has_handler(self, gcp_packages):
        """Dispatcher ZIP should have main.py."""
        if "gcp_dispatcher" not in gcp_packages:
            pytest.skip("dispatcher not built")
        
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
    
    def test_connector_zip_structure(self, gcp_packages):
        """Connector ZIP should have correct structure."""
        if "gcp_connector" not in gcp_packages:
            pytest.skip("connector not built")
        
        zip_path = gcp_packages["gcp_connector"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    # =========================================================================
    # L2: Processing
    # =========================================================================
    
    def test_persister_zip_structure(self, gcp_packages):
        """Persister ZIP should have correct structure."""
        if "gcp_persister" not in gcp_packages:
            pytest.skip("persister not built")
        
        zip_path = gcp_packages["gcp_persister"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
            assert "requirements.txt" in files
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0
    
    def test_processor_wrapper_zip_structure(self, gcp_packages):
        """Processor wrapper ZIP should have correct structure."""
        if "gcp_processor_wrapper" not in gcp_packages:
            pytest.skip("processor_wrapper not built")
        
        zip_path = gcp_packages["gcp_processor_wrapper"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    # =========================================================================
    # L3: Storage
    # =========================================================================
    
    def test_hot_reader_zip_structure(self, gcp_packages):
        """Hot-reader ZIP should have correct structure."""
        if "gcp_hot-reader" not in gcp_packages:
            pytest.skip("hot-reader not built")
        
        zip_path = gcp_packages["gcp_hot-reader"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    def test_hot_reader_last_entry_zip_structure(self, gcp_packages):
        """Hot-reader-last-entry ZIP should have correct structure."""
        if "gcp_hot-reader-last-entry" not in gcp_packages:
            pytest.skip("hot-reader-last-entry not built")
        
        zip_path = gcp_packages["gcp_hot-reader-last-entry"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    def test_hot_to_cold_mover_zip_structure(self, gcp_packages):
        """Hot-to-cold-mover ZIP should have correct structure."""
        if "gcp_hot-to-cold-mover" not in gcp_packages:
            pytest.skip("hot-to-cold-mover not built")
        
        zip_path = gcp_packages["gcp_hot-to-cold-mover"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    def test_cold_to_archive_mover_zip_structure(self, gcp_packages):
        """Cold-to-archive-mover ZIP should have correct structure."""
        if "gcp_cold-to-archive-mover" not in gcp_packages:
            pytest.skip("cold-to-archive-mover not built")
        
        zip_path = gcp_packages["gcp_cold-to-archive-mover"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    # =========================================================================
    # Syntax Validation (all core ZIPs)
    # =========================================================================
    
    def test_all_core_zips_have_no_syntax_errors(self, gcp_packages):
        """All Cloud Function ZIPs should have valid Python syntax."""
        for package_name, zip_path in gcp_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")


class TestGCPL0GlueFunctions:
    """Verify GCP L0 Glue functions (multicloud boundary triggers)."""
    
    @pytest.fixture
    def multicloud_gcp_l3_config(self):
        """Config where GCP is L3 (hot), receiving data from non-GCP L2."""
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
            "layer_4_provider": "google",
            "layer_5_provider": "google",
        }
    
    @pytest.fixture
    def l0_packages(self, tmp_path, multicloud_gcp_l3_config):
        """Build L0 GCP Cloud Function packages for multicloud config."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        terraform_dir = tmp_path / "terraform"
        packages = build_gcp_cloud_function_packages(terraform_dir, project_path, multicloud_gcp_l3_config)
        return packages
    
    def test_hot_writer_zip_created(self, l0_packages):
        """Hot-writer ZIP should be created for L2(AWS)->L3(GCP) boundary."""
        if "gcp_hot-writer" not in l0_packages:
            pytest.skip("hot-writer not built (boundary may not trigger)")
        
        zip_path = l0_packages["gcp_hot-writer"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0, "L0 glue should have _shared/"
    
    def test_l0_zips_have_no_syntax_errors(self, l0_packages):
        """All L0 Cloud Function ZIPs should have valid Python syntax."""
        for package_name, zip_path in l0_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")


class TestGCPUserFunctions:
    """Verify GCP User Function ZIPs (processors, event_actions, event-feedback)."""
    
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
            "layer_5_provider": "google",
        }
    
    @pytest.fixture
    def user_packages(self, tmp_path, all_gcp_config):
        """Build user function packages using template project."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        packages = build_user_packages(project_path, all_gcp_config)
        return {"packages": packages, "build_dir": project_path / ".build" / "google"}
    
    # =========================================================================
    # Processors
    # =========================================================================
    
    def test_processor_zips_created_for_all_devices(self, user_packages):
        """Processor ZIPs should be created for all devices in config."""
        packages = user_packages["packages"]
        
        expected_processors = [
            "processor-temperature-sensor-1",
            "processor-temperature-sensor-2", 
            "processor-pressure-sensor-1",
        ]
        
        for proc_name in expected_processors:
            assert proc_name in packages, f"Missing processor: {proc_name}"
    
    def test_processor_zip_has_handler(self, user_packages):
        """Processor ZIPs should have main.py."""
        packages = user_packages["packages"]
        
        for name, zip_path in packages.items():
            if name.startswith("processor-"):
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    files = zf.namelist()
                    assert "main.py" in files, f"{name} missing main.py"
    
    def test_processor_zip_has_shared(self, user_packages):
        """Processor ZIPs should have _shared/ folder."""
        packages = user_packages["packages"]
        
        for name, zip_path in packages.items():
            if name.startswith("processor-"):
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    files = zf.namelist()
                    shared_files = [f for f in files if f.startswith("_shared/")]
                    assert len(shared_files) > 0, f"{name} missing _shared/"
    
    # =========================================================================
    # Event Actions
    # =========================================================================
    
    def test_event_action_zips_created(self, user_packages):
        """Event action ZIPs should be created for events in config."""
        packages = user_packages["packages"]
        
        expected_actions = [
            "high-temperature-callback",
            "high-temperature-callback-2",
        ]
        
        for action_name in expected_actions:
            assert action_name in packages, f"Missing event action: {action_name}"
    
    def test_event_action_zip_has_handler(self, user_packages):
        """Event action ZIPs should have main.py."""
        packages = user_packages["packages"]
        
        action_names = ["high-temperature-callback", "high-temperature-callback-2"]
        
        for name in action_names:
            if name in packages:
                with zipfile.ZipFile(packages[name], 'r') as zf:
                    files = zf.namelist()
                    assert "main.py" in files, f"{name} missing main.py"
    
    # =========================================================================
    # Event Feedback
    # =========================================================================
    
    def test_event_feedback_zip_exists(self, user_packages):
        """Event feedback ZIP should exist."""
        packages = user_packages["packages"]
        assert "event-feedback" in packages, "Missing event-feedback ZIP"
    
    def test_event_feedback_zip_has_handler(self, user_packages):
        """Event feedback ZIP should have main.py."""
        packages = user_packages["packages"]
        
        if "event-feedback" not in packages:
            pytest.skip("event-feedback not built")
        
        with zipfile.ZipFile(packages["event-feedback"], 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
    
    # =========================================================================
    # Syntax Validation (all user ZIPs)
    # =========================================================================
    
    def test_all_user_zips_have_no_syntax_errors(self, user_packages):
        """All user function ZIPs should have valid Python syntax."""
        packages = user_packages["packages"]
        
        for package_name, zip_path in packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")
