import json
import pytest
from pathlib import Path
from src.core.config_loader import load_project_config, load_credentials, get_required_providers, ConfigurationError

@pytest.fixture
def sample_project_dir(tmp_path):
    """Create a temporary project directory with sample config files."""
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    
    # config.json
    config_data = {
        "digital_twin_name": "test-twin",
        "hot_storage_size_in_days": 7,
        "cold_storage_size_in_days": 30,
        "mode": "DEBUG"
    }
    (project_dir / "config.json").write_text(json.dumps(config_data))
    
    # config_iot_devices.json
    iot_data = {
        "devices": [
            {"id": "d1", "name": "device1"}
        ]
    }
    (project_dir / "config_iot_devices.json").write_text(json.dumps(iot_data))
    
    # config_providers.json
    providers_data = {
        "layer_1_provider": "aws",
        "layer_2_provider": "azure",
        "layer_4_provider": "aws"
    }
    (project_dir / "config_providers.json").write_text(json.dumps(providers_data))
    
    return project_dir

def test_load_project_config_success(sample_project_dir):
    """Test loading a valid project configuration."""
    config = load_project_config(sample_project_dir)
    
    assert config.digital_twin_name == "test-twin"
    assert config.hot_storage_size_in_days == 7
    assert config.cold_storage_size_in_days == 30
    assert config.mode == "DEBUG"
    assert len(config.iot_devices) == 1
    assert config.iot_devices[0]["id"] == "d1"
    assert config.providers["layer_1_provider"] == "aws"

def test_load_project_config_missing_required_file(sample_project_dir):
    """Test that missing required file raises ConfigurationError."""
    # Delete a required file
    (sample_project_dir / "config_iot_devices.json").unlink()
    
    with pytest.raises(ConfigurationError) as exc:
        load_project_config(sample_project_dir)
    
    assert "Required configuration file not found" in str(exc.value)

def test_load_project_config_missing_required_field(sample_project_dir):
    """Test that missing required field in config.json raises ConfigurationError."""
    # Overwrite config.json with missing field
    config_data = {
        "digital_twin_name": "test-twin",
        # Missing storage fields
        "mode": "DEBUG"
    }
    (sample_project_dir / "config.json").write_text(json.dumps(config_data))
    
    with pytest.raises(ConfigurationError) as exc:
        load_project_config(sample_project_dir)
    
    assert "Missing required field" in str(exc.value)

def test_load_credentials(sample_project_dir):
    """Test loading credentials files."""
    # Create aws credentials
    aws_creds = {"aws_access_key_id": "123"}
    (sample_project_dir / "config_credentials_aws.json").write_text(json.dumps(aws_creds))
    
    creds = load_credentials(sample_project_dir)
    
    assert "aws" in creds
    assert creds["aws"] == aws_creds
    assert "azure" not in creds  # File not created

def test_get_required_providers(sample_project_dir):
    """Test extracting required providers from config."""
    config = load_project_config(sample_project_dir)
    # config_providers.json has "aws" and "azure"
    
    providers = get_required_providers(config)
    assert "aws" in providers
    assert "azure" in providers
    assert len(providers) == 2
