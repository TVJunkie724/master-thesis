"""
Terraform Variables Generator.

This module converts the project's JSON configuration files into a Terraform
variables file (tfvars.json) that can be passed to terraform plan/apply.

Usage:
    from tfvars_generator import generate_tfvars
    
    generate_tfvars(
        project_path="/app/upload/my_project",
        output_path="/app/upload/my_project/terraform/generated.tfvars.json"
    )

Config Files Read:
    - config.json: digital_twin_name, storage intervals
    - config_credentials.json: Azure/AWS/GCP credentials
    - config_providers.json: Layer-to-provider mapping
    - config_iot_devices.json: IoT device definitions (array)
    - config_inter_cloud.json: Cross-cloud token (if exists)
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when a required configuration is missing or invalid."""
    pass


def generate_tfvars(project_path: str, output_path: str) -> dict:
    """
    Generate Terraform variables from project configuration files.
    
    Reads all configuration JSON files and produces a single tfvars.json
    file that Terraform can consume.
    
    Args:
        project_path: Absolute path to the project directory
        output_path: Absolute path for the output tfvars.json file
    
    Returns:
        Dictionary of generated variables (also written to output_path)
    
    Raises:
        ConfigurationError: If required configuration is missing
        ValueError: If project_path doesn't exist
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    project_dir = Path(project_path)
    if not project_dir.exists():
        raise ValueError(f"Project directory does not exist: {project_path}")
    
    tfvars = {}
    
    # Add project path for function code references
    tfvars["project_path"] = str(project_dir)
    
    # Load config.json (core settings)
    tfvars.update(_load_config(project_dir))
    
    # Load config_credentials.json (provider credentials)
    tfvars.update(_load_credentials(project_dir))
    
    # Load config_providers.json (layer-to-provider mapping)
    tfvars.update(_load_providers(project_dir))
    
    # Load config_iot_devices.json (device definitions)
    tfvars.update(_load_iot_devices(project_dir))
    
    # Load existing inter-cloud token if available
    tfvars.update(_load_inter_cloud(project_dir))
    
    # Write output file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(tfvars, f, indent=2)
    
    logger.info(f"✓ Generated tfvars: {output_path}")
    return tfvars


def _load_config(project_dir: Path) -> dict:
    """Load core settings from config.json."""
    config_file = project_dir / "config.json"
    
    if not config_file.exists():
        raise ConfigurationError(f"config.json not found in {project_dir}")
    
    with open(config_file) as f:
        config = json.load(f)
    
    # Required: digital_twin_name
    if "digital_twin_name" not in config:
        raise ConfigurationError("digital_twin_name is required in config.json")
    
    # Map config keys to Terraform variable names
    result = {
        "digital_twin_name": config["digital_twin_name"],
    }
    
    # Storage intervals (optional with Terraform defaults)
    if "hot_storage_size_in_days" in config:
        result["layer_3_hot_to_cold_interval_days"] = config["hot_storage_size_in_days"]
    
    if "cold_storage_size_in_days" in config:
        result["layer_3_cold_to_archive_interval_days"] = config["cold_storage_size_in_days"]
    
    return result


def _load_credentials(project_dir: Path) -> dict:
    """Load provider credentials from config_credentials.json."""
    creds_file = project_dir / "config_credentials.json"
    
    if not creds_file.exists():
        raise ConfigurationError(f"config_credentials.json not found in {project_dir}")
    
    with open(creds_file) as f:
        creds = json.load(f)
    
    tfvars = {}
    
    # Azure credentials - all fields required if azure section exists
    if "azure" in creds:
        azure = creds["azure"]
        required_azure = [
            "azure_subscription_id", "azure_client_id", "azure_client_secret",
            "azure_tenant_id", "azure_region"
        ]
        for field in required_azure:
            if field not in azure:
                raise ConfigurationError(f"Missing required Azure credential: {field}")
        
        tfvars["azure_subscription_id"] = azure["azure_subscription_id"]
        tfvars["azure_client_id"] = azure["azure_client_id"]
        tfvars["azure_client_secret"] = azure["azure_client_secret"]
        tfvars["azure_tenant_id"] = azure["azure_tenant_id"]
        tfvars["azure_region"] = azure["azure_region"]
        # IoT Hub region - falls back to main region if not specified
        tfvars["azure_region_iothub"] = azure.get("azure_region_iothub") or azure["azure_region"]
    
    # AWS credentials - all fields required if aws section exists
    if "aws" in creds:
        aws = creds["aws"]
        required_aws = ["aws_access_key_id", "aws_secret_access_key", "aws_region"]
        for field in required_aws:
            if field not in aws:
                raise ConfigurationError(f"Missing required AWS credential: {field}")
        
        tfvars["aws_access_key_id"] = aws["aws_access_key_id"]
        tfvars["aws_secret_access_key"] = aws["aws_secret_access_key"]
        tfvars["aws_region"] = aws["aws_region"]
    
    # GCP credentials - all fields required if gcp section exists
    if "gcp" in creds:
        gcp = creds["gcp"]
        required_gcp = ["gcp_project_id", "gcp_region"]
        for field in required_gcp:
            if field not in gcp:
                raise ConfigurationError(f"Missing required GCP credential: {field}")
        
        tfvars["gcp_project_id"] = gcp["gcp_project_id"]
        tfvars["gcp_region"] = gcp["gcp_region"]
        
        # GCP credentials file path (read and embed as JSON string)
        if "gcp_credentials_file" in gcp:
            creds_file_path = Path(gcp["gcp_credentials_file"])
            if creds_file_path.exists():
                with open(creds_file_path) as f:
                    tfvars["gcp_credentials_json"] = f.read()
    
    return tfvars


def _load_providers(project_dir: Path) -> dict:
    """Load layer-to-provider mapping from config_providers.json."""
    providers_file = project_dir / "config_providers.json"
    
    if not providers_file.exists():
        raise ConfigurationError(f"config_providers.json not found in {project_dir}")
    
    with open(providers_file) as f:
        providers = json.load(f)
    
    # Required provider keys
    required_keys = [
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_hot_provider",
        "layer_3_cold_provider",
        "layer_3_archive_provider",
        "layer_4_provider",
        "layer_5_provider",
    ]
    
    for key in required_keys:
        if key not in providers:
            raise ConfigurationError(f"Missing required provider config: {key}")
    
    return {key: providers[key] for key in required_keys}


def _load_iot_devices(project_dir: Path) -> dict:
    """Load IoT device definitions from config_iot_devices.json."""
    devices_file = project_dir / "config_iot_devices.json"
    
    if not devices_file.exists():
        raise ConfigurationError(f"config_iot_devices.json not found in {project_dir}")
    
    with open(devices_file) as f:
        devices = json.load(f)
    
    # File is a direct array of devices
    if not isinstance(devices, list):
        raise ConfigurationError("config_iot_devices.json must be an array of devices")
    
    return {"iot_devices": devices}


def _load_inter_cloud(project_dir: Path) -> dict:
    """Load existing inter-cloud token if available."""
    inter_cloud_file = project_dir / "config_inter_cloud.json"
    
    if not inter_cloud_file.exists():
        return {}
    
    with open(inter_cloud_file) as f:
        inter_cloud = json.load(f)
    
    if "inter_cloud_token" in inter_cloud and inter_cloud["inter_cloud_token"]:
        return {"inter_cloud_token": inter_cloud["inter_cloud_token"]}
    
    return {}


if __name__ == "__main__":
    # CLI usage for testing
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python tfvars_generator.py <project_path> <output_path>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    generate_tfvars(sys.argv[1], sys.argv[2])
