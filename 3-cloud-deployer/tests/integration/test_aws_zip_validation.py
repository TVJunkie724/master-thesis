"""
AWS Lambda ZIP structure validation test.

Validates that package_builder creates Lambda ZIPs with correct structure:
- lambda_function.py handler exists
- _shared/ folder is included
- No syntax errors in Python files

Covers ALL AWS function categories:
- L0 Glue functions (multicloud boundary triggers)
- L1-L4 Core functions (dispatcher, persister, hot-reader, etc.)
- User functions (processors, event_actions, event-feedback)
"""
import pytest
import zipfile
import json
import shutil
from pathlib import Path

from src.providers.terraform.package_builder import (
    build_aws_lambda_packages,
    build_user_packages,
)


class TestAWSCoreFunctions:
    """Verify AWS Core Lambda ZIPs (L1-L4) have correct structure."""
    
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
            "layer_5_provider": "aws",
        }
    
    @pytest.fixture
    def aws_packages(self, tmp_path, all_aws_config):
        """Build AWS Lambda packages using template project."""
        # Copy template project to tmp_path
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        # Build packages
        terraform_dir = tmp_path / "terraform"
        packages = build_aws_lambda_packages(terraform_dir, project_path, all_aws_config)
        return packages
    
    # =========================================================================
    # L1: Data Acquisition
    # =========================================================================
    
    def test_dispatcher_zip_has_handler(self, aws_packages):
        """Dispatcher ZIP should have lambda_function.py."""
        if "aws_dispatcher" not in aws_packages:
            pytest.skip("dispatcher not built")
        
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
    
    def test_connector_zip_structure(self, aws_packages):
        """Connector ZIP should have correct structure."""
        if "aws_connector" not in aws_packages:
            pytest.skip("connector not built")
        
        zip_path = aws_packages["aws_connector"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    # =========================================================================
    # L2: Processing
    # =========================================================================
    
    def test_persister_zip_structure(self, aws_packages):
        """Persister ZIP should have correct structure."""
        if "aws_persister" not in aws_packages:
            pytest.skip("persister not built")
        
        zip_path = aws_packages["aws_persister"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0
    
    def test_processor_wrapper_zip_structure(self, aws_packages):
        """Processor wrapper ZIP should have correct structure."""
        if "aws_processor_wrapper" not in aws_packages:
            pytest.skip("processor_wrapper not built")
        
        zip_path = aws_packages["aws_processor_wrapper"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    # =========================================================================
    # L3: Storage
    # =========================================================================
    
    def test_hot_reader_zip_structure(self, aws_packages):
        """Hot-reader ZIP should have correct structure."""
        if "aws_hot-reader" not in aws_packages:
            pytest.skip("hot-reader not built")
        
        zip_path = aws_packages["aws_hot-reader"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    def test_hot_reader_last_entry_zip_structure(self, aws_packages):
        """Hot-reader-last-entry ZIP should have correct structure."""
        if "aws_hot-reader-last-entry" not in aws_packages:
            pytest.skip("hot-reader-last-entry not built")
        
        zip_path = aws_packages["aws_hot-reader-last-entry"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    def test_hot_to_cold_mover_zip_structure(self, aws_packages):
        """Hot-to-cold-mover ZIP should have correct structure."""
        if "aws_hot-to-cold-mover" not in aws_packages:
            pytest.skip("hot-to-cold-mover not built")
        
        zip_path = aws_packages["aws_hot-to-cold-mover"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    def test_cold_to_archive_mover_zip_structure(self, aws_packages):
        """Cold-to-archive-mover ZIP should have correct structure."""
        if "aws_cold-to-archive-mover" not in aws_packages:
            pytest.skip("cold-to-archive-mover not built")
        
        zip_path = aws_packages["aws_cold-to-archive-mover"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    # =========================================================================
    # L4: Management
    # =========================================================================
    
    def test_digital_twin_data_connector_zip_structure(self, aws_packages):
        """Digital-twin-data-connector ZIP should have correct structure."""
        if "aws_digital-twin-data-connector" not in aws_packages:
            pytest.skip("digital-twin-data-connector not built")
        
        zip_path = aws_packages["aws_digital-twin-data-connector"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    def test_digital_twin_data_connector_last_entry_zip_structure(self, aws_packages):
        """Digital-twin-data-connector-last-entry ZIP should have correct structure."""
        if "aws_digital-twin-data-connector-last-entry" not in aws_packages:
            pytest.skip("digital-twin-data-connector-last-entry not built")
        
        zip_path = aws_packages["aws_digital-twin-data-connector-last-entry"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
    # =========================================================================
    # Syntax Validation (all core ZIPs)
    # =========================================================================
    
    def test_all_core_zips_have_no_syntax_errors(self, aws_packages):
        """All Lambda ZIPs should have valid Python syntax."""
        for package_name, zip_path in aws_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")


class TestAWSL0GlueFunctions:
    """Verify AWS L0 Glue functions (multicloud boundary triggers)."""
    
    @pytest.fixture
    def multicloud_aws_l3_config(self):
        """Config where AWS is L3 (hot), receiving data from non-AWS L2."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
            "layer_5_provider": "aws",
        }
    
    @pytest.fixture
    def l0_packages(self, tmp_path, multicloud_aws_l3_config):
        """Build L0 AWS Lambda packages for multicloud config."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        terraform_dir = tmp_path / "terraform"
        packages = build_aws_lambda_packages(terraform_dir, project_path, multicloud_aws_l3_config)
        return packages
    
    def test_hot_writer_zip_created(self, l0_packages):
        """Hot-writer ZIP should be created for L2(GCP)->L3(AWS) boundary."""
        if "aws_hot-writer" not in l0_packages:
            pytest.skip("hot-writer not built (boundary may not trigger)")
        
        zip_path = l0_packages["aws_hot-writer"]
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
            shared_files = [f for f in files if f.startswith("_shared/")]
            assert len(shared_files) > 0, "L0 glue should have _shared/"
    
    def test_l0_zips_have_no_syntax_errors(self, l0_packages):
        """All L0 Lambda ZIPs should have valid Python syntax."""
        for package_name, zip_path in l0_packages.items():
            with zipfile.ZipFile(zip_path, 'r') as zf:
                py_files = [f for f in zf.namelist() if f.endswith('.py')]
                
                for py_file in py_files:
                    content = zf.read(py_file).decode('utf-8')
                    try:
                        compile(content, py_file, 'exec')
                    except SyntaxError as e:
                        pytest.fail(f"{package_name}/{py_file} has syntax error: {e}")


class TestAWSUserFunctions:
    """Verify AWS User Function ZIPs (processors, event_actions, event-feedback)."""
    
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
            "layer_5_provider": "aws",
        }
    
    @pytest.fixture
    def user_packages(self, tmp_path, all_aws_config):
        """Build user function packages using template project."""
        source_path = Path("/app/upload/template")
        project_path = tmp_path / "project"
        
        if not source_path.exists():
            pytest.skip("Template project not found")
            
        shutil.copytree(source_path, project_path)
        
        # Build user packages
        packages = build_user_packages(project_path, all_aws_config)
        return {"packages": packages, "build_dir": project_path / ".build" / "aws"}
    
    # =========================================================================
    # Processors
    # =========================================================================
    
    def test_processor_zips_created_for_all_devices(self, user_packages):
        """Processor ZIPs should be created for all devices in config."""
        packages = user_packages["packages"]
        
        # Template has 3 devices: temperature-sensor-1, temperature-sensor-2, pressure-sensor-1
        expected_processors = [
            "processor-temperature-sensor-1",
            "processor-temperature-sensor-2", 
            "processor-pressure-sensor-1",
        ]
        
        for proc_name in expected_processors:
            assert proc_name in packages, f"Missing processor: {proc_name}"
    
    def test_processor_zip_has_handler(self, user_packages):
        """Processor ZIPs should have lambda_function.py."""
        packages = user_packages["packages"]
        
        for name, zip_path in packages.items():
            if name.startswith("processor-"):
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    files = zf.namelist()
                    assert "lambda_function.py" in files, f"{name} missing lambda_function.py"
    
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
        
        # Template has 2 event actions: high-temperature-callback, high-temperature-callback-2
        expected_actions = [
            "high-temperature-callback",
            "high-temperature-callback-2",
        ]
        
        for action_name in expected_actions:
            assert action_name in packages, f"Missing event action: {action_name}"
    
    def test_event_action_zip_has_handler(self, user_packages):
        """Event action ZIPs should have lambda_function.py."""
        packages = user_packages["packages"]
        
        action_names = ["high-temperature-callback", "high-temperature-callback-2"]
        
        for name in action_names:
            if name in packages:
                with zipfile.ZipFile(packages[name], 'r') as zf:
                    files = zf.namelist()
                    assert "lambda_function.py" in files, f"{name} missing lambda_function.py"
    
    # =========================================================================
    # Event Feedback
    # =========================================================================
    
    def test_event_feedback_zip_exists(self, user_packages):
        """Event feedback ZIP should exist."""
        packages = user_packages["packages"]
        assert "event-feedback" in packages, "Missing event-feedback ZIP"
    
    def test_event_feedback_zip_has_handler(self, user_packages):
        """Event feedback ZIP should have lambda_function.py."""
        packages = user_packages["packages"]
        
        if "event-feedback" not in packages:
            pytest.skip("event-feedback not built")
        
        with zipfile.ZipFile(packages["event-feedback"], 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
    
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
