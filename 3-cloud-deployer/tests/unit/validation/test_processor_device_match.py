"""
Unit tests for processor folder validation against device configuration.

Tests the check_processor_folders_match_devices() validation function.
"""

import pytest
from pathlib import Path
import json
import tempfile
import shutil

from src.validation.core import check_processor_folders_match_devices, build_context
from src.validation.accessors import DirectoryAccessor


class TestProcessorDeviceMatch:
    """Test suite for processor folder validation."""
    
    def setup_method(self):
        """Create a temporary project directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_path = self.temp_dir / "test_project"
        self.project_path.mkdir()
        
        # Create required directories
        (self.project_path / "azure_functions" / "processors").mkdir(parents=True)
        (self.project_path / "cloud_functions" / "processors").mkdir(parents=True)
        (self.project_path / "lambda_functions" / "processors").mkdir(parents=True)
    
    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_config_json(self):
        """Helper to create minimal config.json for context building."""
        config = {"digital_twin_name": "test-twin", "providers": {}}
        (self.project_path / "config.json").write_text(json.dumps(config))
    
    def _create_providers_json(self, l2_provider="azure"):
        """Helper to create config_providers.json."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": l2_provider,
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "none",
            "layer_3_archive_provider": "none",
            "layer_4_provider": "none",
            "layer_5_provider": "none"
        }
        (self.project_path / "config_providers.json").write_text(json.dumps(providers))
    
    def _create_device_config(self, devices):
        """Helper to create config_iot_devices.json."""
        config_path = self.project_path / "config_iot_devices.json"
        config_path.write_text(json.dumps(devices, indent=2))
        # Store devices for later use in context setup
        self._devices = devices
    
    def _create_processor_folder(self, provider, device_id):
        """Helper to create a processor folder."""
        if provider == "azure":
            folder = self.project_path / "azure_functions" / "processors" / device_id
        elif provider == "gcp":
            folder = self.project_path / "cloud_functions" / "processors" / device_id
        elif provider == "aws":
            folder = self.project_path / "lambda_functions" / "processors" / device_id
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        folder.mkdir(parents=True, exist_ok=True)
        # Create a dummy function file
        if provider == "azure":
            (folder / "function_app.py").write_text("# Azure processor")
        elif provider == "gcp":
            (folder / "main.py").write_text("# GCP processor")
        elif provider == "aws":
            (folder / "lambda_function.py").write_text("# AWS processor")
    
    def _get_accessor_and_context(self):
        """Helper to build accessor and context with manually populated iot_config."""
        accessor = DirectoryAccessor(self.project_path)
        ctx = build_context(accessor)
        # Manually populate iot_config (simpler than calling full schema validation)
        ctx.iot_config = getattr(self, '_devices', [])
        return accessor, ctx
    
    def test_all_processors_exist_azure(self):
        """Test validation passes when all processor folders exist for Azure."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "pressure-sensor-1", "name": "Pressure Sensor 1"}
        ]
        self._create_config_json()
        self._create_providers_json("azure")
        self._create_device_config(devices)
        
        # Create processor folders
        self._create_processor_folder("azure", "temperature-sensor-1")
        self._create_processor_folder("azure", "pressure-sensor-1")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should not raise
        check_processor_folders_match_devices(accessor, ctx, "azure")
    
    def test_missing_processor_folder_azure(self):
        """Test validation fails when a processor folder is missing for Azure."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "pressure-sensor-1", "name": "Pressure Sensor 1"}
        ]
        self._create_config_json()
        self._create_providers_json("azure")
        self._create_device_config(devices)
        
        # Only create one processor folder
        self._create_processor_folder("azure", "temperature-sensor-1")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should raise ValueError
        with pytest.raises(ValueError, match="pressure-sensor-1"):
            check_processor_folders_match_devices(accessor, ctx, "azure")
    
    def test_all_processors_exist_gcp(self):
        """Test validation passes when all processor folders exist for GCP."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "temperature-sensor-2", "name": "Temp Sensor 2"}
        ]
        self._create_config_json()
        self._create_providers_json("google")
        self._create_device_config(devices)
        
        # Create processor folders
        self._create_processor_folder("gcp", "temperature-sensor-1")
        self._create_processor_folder("gcp", "temperature-sensor-2")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should not raise
        check_processor_folders_match_devices(accessor, ctx, "google")
    
    def test_missing_processor_folder_gcp(self):
        """Test validation fails when a processor folder is missing for GCP."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "temperature-sensor-2", "name": "Temp Sensor 2"}
        ]
        self._create_config_json()
        self._create_providers_json("google")
        self._create_device_config(devices)
        
        # Only create one processor folder
        self._create_processor_folder("gcp", "temperature-sensor-1")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should raise ValueError
        with pytest.raises(ValueError, match="temperature-sensor-2"):
            check_processor_folders_match_devices(accessor, ctx, "google")
    
    def test_all_processors_exist_aws(self):
        """Test validation passes when all processor folders exist for AWS."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "pressure-sensor-1", "name": "Pressure Sensor 1"}
        ]
        self._create_config_json()
        self._create_providers_json("aws")
        self._create_device_config(devices)
        
        # Create processor folders
        self._create_processor_folder("aws", "temperature-sensor-1")
        self._create_processor_folder("aws", "pressure-sensor-1")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should not raise
        check_processor_folders_match_devices(accessor, ctx, "aws")
    
    def test_missing_processor_folder_aws(self):
        """Test validation fails when a processor folder is missing for AWS."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "pressure-sensor-1", "name": "Pressure Sensor 1"}
        ]
        self._create_config_json()
        self._create_providers_json("aws")
        self._create_device_config(devices)
        
        # Only create one processor folder
        self._create_processor_folder("aws", "temperature-sensor-1")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should raise ValueError
        with pytest.raises(ValueError, match="pressure-sensor-1"):
            check_processor_folders_match_devices(accessor, ctx, "aws")
    
    def test_empty_device_config(self):
        """Test validation passes when there are no devices."""
        self._create_config_json()
        self._create_providers_json("azure")
        self._create_device_config([])
        
        accessor, ctx = self._get_accessor_and_context()
        # Should not raise
        check_processor_folders_match_devices(accessor, ctx, "azure")
    
    def test_duplicate_device_ids(self):
        """Test validation handles duplicate device IDs correctly."""
        devices = [
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1"},
            {"id": "temperature-sensor-1", "name": "Temp Sensor 1 Duplicate"}
        ]
        self._create_config_json()
        self._create_providers_json("azure")
        self._create_device_config(devices)
        
        # Create processor folder once
        self._create_processor_folder("azure", "temperature-sensor-1")
        
        accessor, ctx = self._get_accessor_and_context()
        # Should not raise (duplicates should be handled)
        check_processor_folders_match_devices(accessor, ctx, "azure")
