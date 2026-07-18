import json
import pytest
from tests.utils.deployment_specification import (
    deployment_manifest,
    load_specification,
    provider_config_for_specification,
)
from src.core.config_loader import (
    ProjectConfigLoader,
    load_project_config,
    load_optimization_flags,
    load_credentials,
    get_required_providers,
    normalize_optimization_flags,
    normalize_provider_mapping,
    normalize_provider_name,
    ConfigurationError,
)
from src.core.executable_topology import (
    UnsupportedErrorHandlingTopologyError,
)
from src.core.project_storage import ProjectStorage

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


def test_optimizer_result_flags_are_normalized_into_project_config(
    sample_project_dir,
):
    (sample_project_dir / "config_optimization.json").write_text(
        json.dumps(
            {
                "result": {
                    "inputParamsUsed": {
                        "useEventChecking": True,
                        "returnFeedbackToDevice": True,
                    }
                }
            }
        )
    )

    config = load_project_config(sample_project_dir)

    assert config.optimization["useEventChecking"] is True
    assert config.optimization["returnFeedbackToDevice"] is True
    assert config.optimization["triggerNotificationWorkflow"] is False
    assert config.is_optimization_enabled("useEventChecking") is True


def test_flat_optimization_flags_remain_supported_during_migration():
    flags = normalize_optimization_flags(
        {
            "useEventChecking": True,
            "triggerNotificationWorkflow": True,
        }
    )

    assert flags["useEventChecking"] is True
    assert flags["triggerNotificationWorkflow"] is True
    assert flags["returnFeedbackToDevice"] is False


def test_invalid_optimization_flag_type_fails_closed():
    flags = normalize_optimization_flags({"useEventChecking": "true"})

    assert flags["useEventChecking"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"integrateErrorHandling": True},
        {
            "result": {
                "inputParamsUsed": {
                    "integrateErrorHandling": True,
                }
            }
        },
    ],
)
def test_unsupported_error_handling_topology_is_rejected(payload):
    with pytest.raises(
        UnsupportedErrorHandlingTopologyError,
        match="UNSUPPORTED_ERROR_HANDLING_TOPOLOGY",
    ):
        normalize_optimization_flags(payload)


def test_tolerant_optimization_loader_does_not_swallow_topology_violation(
    sample_project_dir,
):
    (sample_project_dir / "config_optimization.json").write_text(
        json.dumps({"integrateErrorHandling": True})
    )

    with pytest.raises(UnsupportedErrorHandlingTopologyError):
        load_optimization_flags(sample_project_dir)


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


def test_provider_alias_normalization_is_centralized():
    assert normalize_provider_name("google") == "gcp"
    assert normalize_provider_name("gcp") == "gcp"
    assert normalize_provider_mapping({
        "layer_1_provider": "google",
        "layer_2_provider": "azure",
    }) == {
        "layer_1_provider": "gcp",
        "layer_2_provider": "azure",
    }


def test_load_project_config_normalizes_google_provider(sample_project_dir):
    providers_path = sample_project_dir / "config_providers.json"
    providers_path.write_text(json.dumps({
        "layer_1_provider": "google",
        "layer_2_provider": "google",
        "layer_3_hot_provider": "google",
        "layer_4_provider": "google",
    }))

    config = load_project_config(sample_project_dir)

    assert config.providers["layer_1_provider"] == "gcp"
    assert config.providers["layer_4_provider"] == "gcp"
    assert config.hierarchy == []


def test_project_config_loader_loads_bundle_through_project_storage(tmp_path):
    specification = load_specification("mixed-providers.json")
    providers = provider_config_for_specification(specification)
    providers = {
        key: "google" if value == "gcp" else value
        for key, value in providers.items()
    }
    project_dir = tmp_path / "upload" / "factory"
    project_dir.mkdir(parents=True)
    (project_dir / "config.json").write_text(json.dumps({
        "digital_twin_name": "factory",
        "hot_storage_size_in_days": 7,
        "cold_storage_size_in_days": 30,
        "mode": "DEBUG",
    }))
    (project_dir / "config_iot_devices.json").write_text("[]")
    (project_dir / "config_providers.json").write_text(json.dumps(providers))
    (project_dir / "config_credentials.json").write_text(json.dumps({
        "aws": {"aws_access_key_id": "key"},
    }))
    (project_dir / "deployment_manifest.json").write_text(
        json.dumps(
            deployment_manifest(
                specification,
                providers=providers,
                resource_name="factory",
            )
        )
    )

    bundle = ProjectConfigLoader(ProjectStorage(tmp_path)).load_bundle("factory")

    assert bundle.project_name == "factory"
    assert bundle.project_path == project_dir
    assert "gcp" in bundle.config.providers.values()
    assert bundle.credentials["aws"]["aws_access_key_id"] == "key"
    assert bundle.deployment_manifest["manifest_version"] == "2.0"
    assert bundle.validated_deployment_manifest is not None
