"""
Unit tests for tfvars_generator module.

Tests the generation of Terraform variables from project configuration files.
"""

import pytest
import json
import tempfile
from pathlib import Path

from src.tfvars_generator import (
    generate_tfvars,
    ConfigurationError,
    _load_config,
    _load_credentials,
    _load_providers,
    _load_iot_devices,
)


class TestLoadConfig:
    """Tests for _load_config function."""
    
    def test_requires_config_file(self, tmp_path):
        """Should raise ConfigurationError if config.json missing."""
        with pytest.raises(ConfigurationError, match="config.json not found"):
            _load_config(tmp_path)
    
    def test_requires_digital_twin_name(self, tmp_path):
        """Should raise ConfigurationError if digital_twin_name missing."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"mode": "DEBUG"}))
        
        with pytest.raises(ConfigurationError, match="digital_twin_name is required"):
            _load_config(tmp_path)
    
    def test_loads_valid_config(self, tmp_path):
        """Should load valid config with required fields."""
        config = {
            "digital_twin_name": "test-twin",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))
        
        result = _load_config(tmp_path)
        
        assert result["digital_twin_name"] == "test-twin"
        assert result["layer_3_hot_to_cold_interval_days"] == 30
        assert result["layer_3_cold_to_archive_interval_days"] == 90
    
    def test_minimal_config(self, tmp_path):
        """Should work with only digital_twin_name."""
        config = {"digital_twin_name": "minimal-twin"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))
        
        result = _load_config(tmp_path)
        
        assert result["digital_twin_name"] == "minimal-twin"
        # Storage intervals should not be in result if not in config
        assert "layer_3_hot_to_cold_interval_days" not in result or result.get("layer_3_hot_to_cold_interval_days") is None


class TestLoadCredentials:
    """Tests for _load_credentials function."""
    
    def test_requires_credentials_file(self, tmp_path):
        """Should raise ConfigurationError if credentials file missing."""
        with pytest.raises(ConfigurationError, match="config_credentials.json not found"):
            _load_credentials(tmp_path)
    
    def test_requires_azure_fields(self, tmp_path):
        """Should raise ConfigurationError if azure fields missing."""
        creds = {"azure": {"azure_subscription_id": "sub123"}}
        creds_file = tmp_path / "config_credentials.json"
        creds_file.write_text(json.dumps(creds))
        
        with pytest.raises(ConfigurationError, match="Missing required Azure credential"):
            _load_credentials(tmp_path)
    
    def test_loads_azure_credentials(self, tmp_path):
        """Should load valid Azure credentials."""
        creds = {
            "azure": {
                "azure_subscription_id": "sub123",
                "azure_client_id": "client123",
                "azure_client_secret": "secret123",
                "azure_tenant_id": "tenant123",
                "azure_region": "westeurope"
            }
        }
        creds_file = tmp_path / "config_credentials.json"
        creds_file.write_text(json.dumps(creds))
        
        result = _load_credentials(tmp_path)
        
        assert result["azure_subscription_id"] == "sub123"
        assert result["azure_client_id"] == "client123"
        assert result["azure_region"] == "westeurope"
        # IoT Hub region should fall back to main region
        assert result["azure_region_iothub"] == "westeurope"
    
    def test_loads_aws_credentials(self, tmp_path):
        """Should load valid AWS credentials."""
        creds = {
            "aws": {
                "aws_access_key_id": "AKIATEST",
                "aws_secret_access_key": "secret",
                "aws_region": "eu-central-1"
            }
        }
        creds_file = tmp_path / "config_credentials.json"
        creds_file.write_text(json.dumps(creds))
        
        result = _load_credentials(tmp_path)
        
        assert result["aws_access_key_id"] == "AKIATEST"
        assert result["aws_region"] == "eu-central-1"


class TestLoadProviders:
    """Tests for _load_providers function."""
    
    def test_requires_providers_file(self, tmp_path):
        """Should raise ConfigurationError if providers file missing."""
        with pytest.raises(ConfigurationError, match="config_providers.json not found"):
            _load_providers(tmp_path)
    
    def test_requires_all_layer_providers(self, tmp_path):
        """Should raise ConfigurationError if any provider missing."""
        providers = {"layer_1_provider": "azure"}
        providers_file = tmp_path / "config_providers.json"
        providers_file.write_text(json.dumps(providers))
        
        with pytest.raises(ConfigurationError, match="Missing required provider config"):
            _load_providers(tmp_path)
    
    def test_loads_all_providers(self, tmp_path):
        """Should load all provider configurations."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        providers_file = tmp_path / "config_providers.json"
        providers_file.write_text(json.dumps(providers))
        
        result = _load_providers(tmp_path)
        
        assert result["layer_1_provider"] == "azure"
        assert result["layer_2_provider"] == "aws"


class TestLoadIotDevices:
    """Tests for _load_iot_devices function."""
    
    def test_requires_devices_file(self, tmp_path):
        """Should raise ConfigurationError if devices file missing."""
        with pytest.raises(ConfigurationError, match="config_iot_devices.json not found"):
            _load_iot_devices(tmp_path)
    
    def test_requires_array_format(self, tmp_path):
        """Should raise ConfigurationError if not an array."""
        devices_file = tmp_path / "config_iot_devices.json"
        devices_file.write_text(json.dumps({"devices": []}))  # Wrong format
        
        with pytest.raises(ConfigurationError, match="must be an array"):
            _load_iot_devices(tmp_path)
    
    def test_loads_devices_array(self, tmp_path):
        """Should load devices as array."""
        devices = [
            {"id": "sensor-1", "properties": [{"name": "temp"}]}
        ]
        devices_file = tmp_path / "config_iot_devices.json"
        devices_file.write_text(json.dumps(devices))
        
        result = _load_iot_devices(tmp_path)
        
        assert len(result["iot_devices"]) == 1
        assert result["iot_devices"][0]["id"] == "sensor-1"


class TestGenerateTfvars:
    """Tests for generate_tfvars function."""
    
    @pytest.fixture
    def complete_project(self, tmp_path):
        """Create a complete project structure for testing."""
        # config.json
        (tmp_path / "config.json").write_text(json.dumps({
            "digital_twin_name": "test-twin"
        }))
        
        # config_credentials.json
        (tmp_path / "config_credentials.json").write_text(json.dumps({
            "azure": {
                "azure_subscription_id": "sub",
                "azure_client_id": "client",
                "azure_client_secret": "secret",
                "azure_tenant_id": "tenant",
                "azure_region": "westeurope"
            }
        }))
        
        # config_providers.json
        (tmp_path / "config_providers.json").write_text(json.dumps({
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }))
        
        # config_iot_devices.json
        (tmp_path / "config_iot_devices.json").write_text(json.dumps([
            {"id": "sensor-1", "properties": []}
        ]))
        
        return tmp_path
    
    def test_requires_project_path(self):
        """Should raise ValueError if project_path is None."""
        with pytest.raises(ValueError, match="project_path is required"):
            generate_tfvars(None, "/tmp/output.json")
    
    def test_generates_tfvars_file(self, complete_project, tmp_path):
        """Should generate tfvars.json file."""
        output_path = tmp_path / "terraform" / "generated.tfvars.json"
        
        result = generate_tfvars(str(complete_project), str(output_path))
        
        assert output_path.exists()
        assert result["digital_twin_name"] == "test-twin"
        assert result["layer_1_provider"] == "azure"
        
        # Verify file content matches
        with open(output_path) as f:
            written = json.load(f)
        assert written == result
