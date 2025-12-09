"""
Configuration loading utilities.

This module provides functions to load and parse project configuration
from JSON files.

File Loading Order:
    1. config.json - Core settings (twin name, storage days, mode)
    2. config_iot_devices.json - IoT device definitions
    3. config_events.json - Event/anomaly rules
    4. config_hierarchy.json - Entity hierarchy for TwinMaker
    5. config_providers.json - Layer-to-provider mapping
    6. config_optimization.json - Feature flags
    7. config_inter_cloud.json - Cross-cloud connections (optional)

Usage:
    from core.config_loader import load_project_config
    
    config = load_project_config(
        project_path=Path("/app/upload/my-project")
    )
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .context import ProjectConfig
from .exceptions import ConfigurationError

# Constants matching src/constants.py
CONFIG_FILE = "config.json"
CONFIG_IOT_DEVICES_FILE = "config_iot_devices.json"
CONFIG_EVENTS_FILE = "config_events.json"
CONFIG_HIERARCHY_FILE = "config_hierarchy.json"
CONFIG_PROVIDERS_FILE = "config_providers.json"
CONFIG_OPTIMIZATION_FILE = "config_optimization.json"
CONFIG_INTER_CLOUD_FILE = "config_inter_cloud.json"


def _load_json_file(file_path: Path, required: bool = True) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents as a dictionary.
    
    Args:
        file_path: Path to the JSON file
        required: If True, raise error when file is missing. If False, return empty dict.
    
    Returns:
        Parsed JSON content as dictionary
    
    Raises:
        ConfigurationError: If file is missing (when required) or has invalid JSON
    """
    if not file_path.exists():
        if required:
            raise ConfigurationError(
                f"Required configuration file not found: {file_path.name}",
                config_file=str(file_path)
            )
        return {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(
            f"Invalid JSON in configuration file: {e}",
            config_file=str(file_path)
        )


def load_project_config(project_path: Path) -> ProjectConfig:
    """
    Load all configuration files for a project.
    
    This function reads all configuration JSON files from the project
    directory and constructs a ProjectConfig object.
    
    Args:
        project_path: Path to the project directory containing config files
    
    Returns:
        ProjectConfig with all loaded settings
    
    Raises:
        ConfigurationError: If required config files are missing or invalid
    
    Example:
        config = load_project_config(Path("/app/upload/my-project"))
        print(config.digital_twin_name)  # "my-twin"
    """
    # Load core config (required)
    core_config = _load_json_file(project_path / CONFIG_FILE, required=True)
    
    # Validate required fields in core config
    required_fields = ["digital_twin_name", "layer_3_hot_to_cold_interval_days", 
                       "layer_3_cold_to_archive_interval_days", "mode"]
    for field in required_fields:
        if field not in core_config:
            raise ConfigurationError(
                f"Missing required field '{field}' in {CONFIG_FILE}",
                config_file=str(project_path / CONFIG_FILE)
            )
    
    # Load remaining config files
    iot_devices = _load_json_file(project_path / CONFIG_IOT_DEVICES_FILE, required=True)
    events = _load_json_file(project_path / CONFIG_EVENTS_FILE, required=False)
    hierarchy = _load_json_file(project_path / CONFIG_HIERARCHY_FILE, required=False)
    providers = _load_json_file(project_path / CONFIG_PROVIDERS_FILE, required=True)
    optimization = _load_json_file(project_path / CONFIG_OPTIMIZATION_FILE, required=False)
    inter_cloud = _load_json_file(project_path / CONFIG_INTER_CLOUD_FILE, required=False)
    
    # Construct ProjectConfig
    return ProjectConfig(
        digital_twin_name=core_config["digital_twin_name"],
        hot_storage_size_in_days=core_config["layer_3_hot_to_cold_interval_days"],
        cold_storage_size_in_days=core_config["layer_3_cold_to_archive_interval_days"],
        mode=core_config["mode"],
        iot_devices=iot_devices if isinstance(iot_devices, list) else iot_devices.get("devices", []),
        events=events if isinstance(events, list) else events.get("events", []),
        hierarchy=hierarchy if isinstance(hierarchy, list) else hierarchy.get("hierarchy", []),
        providers=providers,
        optimization=optimization,
        inter_cloud=inter_cloud,
    )


def load_credentials(project_path: Path) -> Dict[str, dict]:
    """
    Load credentials for all configured providers.
    
    Credentials are stored in separate files per provider:
    - config_credentials_aws.json
    - config_credentials_azure.json
    - config_credentials_google.json
    
    Args:
        project_path: Path to the project directory
    
    Returns:
        Dictionary mapping provider names to their credentials
        e.g., {"aws": {"aws_access_key_id": "...", ...}}
    
    Note:
        Credentials files are optional - only loaded if they exist.
        This allows using environment variables or IAM roles instead.
    """
    credentials = {}
    
    # AWS credentials
    aws_creds = _load_json_file(
        project_path / "config_credentials_aws.json", 
        required=False
    )
    if aws_creds:
        credentials["aws"] = aws_creds
    
    # Azure credentials
    azure_creds = _load_json_file(
        project_path / "config_credentials_azure.json",
        required=False
    )
    if azure_creds:
        credentials["azure"] = azure_creds
    
    # GCP credentials
    gcp_creds = _load_json_file(
        project_path / "config_credentials_google.json",
        required=False
    )
    if gcp_creds:
        credentials["gcp"] = gcp_creds
    
    return credentials


def get_required_providers(config: ProjectConfig) -> set[str]:
    """
    Determine which providers are needed based on configuration.
    
    Examines the config_providers settings to find all unique
    provider names that need to be initialized.
    
    Args:
        config: Loaded ProjectConfig
    
    Returns:
        Set of provider names (e.g., {"aws", "azure"})
    
    Example:
        >>> config.providers
        {"layer_1_provider": "aws", "layer_2_provider": "azure", ...}
        >>> get_required_providers(config)
        {"aws", "azure"}
    """
    return set(config.providers.values())
