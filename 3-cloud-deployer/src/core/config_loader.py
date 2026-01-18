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
CONFIG_PROVIDERS_FILE = "config_providers.json"
CONFIG_OPTIMIZATION_FILE = "config_optimization.json"
CONFIG_INTER_CLOUD_FILE = "config_inter_cloud.json"
CONFIG_USER_FILE = "config_user.json"

# Twin Hierarchy (provider-specific)
TWIN_HIERARCHY_DIR_NAME = "twin_hierarchy"
AWS_HIERARCHY_FILE = "aws_hierarchy.json"
AZURE_HIERARCHY_FILE = "azure_hierarchy.json"


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


def _load_hierarchy_for_provider(project_path: Path, provider: str) -> Dict[str, Any]:
    """
    Load hierarchy file for a specific provider from twin_hierarchy/ folder.
    
    The hierarchy file format differs by provider:
    - AWS: TwinMaker entity/component format (array of entities with children)
    - Azure: DTDL JSON format (object with models/twins/relationships sections)
    
    IMPORTANT - Azure NDJSON Conversion:
        Azure Digital Twins Import Jobs API requires NDJSON (Newline Delimited JSON) format.
        The L4 Azure deployer must convert this JSON to NDJSON before upload:
        
        JSON Structure:
            {"header": {...}, "models": [...], "twins": [...], "relationships": [...]}
        
        NDJSON Structure (each line is a separate JSON object):
            {"Section": "Header"}
            {"fileVersion": "1.0.0", ...}
            {"Section": "Models"}
            {"@id": "dtmi:...", "@type": "Interface", ...}
            {"Section": "Twins"}
            {"$dtId": "room-1", "$metadata": {"$model": "dtmi:..."}}
            {"Section": "Relationships"}
            {"$dtId": "room-1", "$targetId": "machine-1", ...}
        
        See: https://learn.microsoft.com/en-us/azure/digital-twins/concepts-apis-sdks#format-data
        See: upload/template/twin_hierarchy/azure_hierarchy_final.ndjson.example
    
    Args:
        project_path: Path to the project directory
        provider: Provider name ("aws" or "azure")
        
    Returns:
        Parsed hierarchy content, or empty dict/list if not found
        
    Raises:
        ConfigurationError: If file exists but has invalid JSON
        ValueError: If provider is not 'aws' or 'azure'
    """
    provider_lower = provider.lower()
    
    # TODO(GCP-L4L5): GCP has no managed Digital Twin service. When GCP L4 is implemented,
    # add a 'google' branch here similar to 'aws' and 'azure' to load GCP hierarchy format.
    # For now, return empty hierarchy - Terraform skips L4/L5 resources for GCP.
    if provider_lower == "google":
        return []  # No hierarchy for GCP - no Digital Twin service
    
    # Strict validation: only aws and azure have hierarchy support
    if provider_lower not in ("aws", "azure"):
        raise ValueError(
            f"Invalid provider '{provider}'. Hierarchy is only available for 'aws', 'azure', or 'google' (empty)."
        )
    
    hierarchy_dir = project_path / TWIN_HIERARCHY_DIR_NAME
    
    # Explicit provider handling - no fallbacks
    if provider_lower == "azure":
        hierarchy_file = hierarchy_dir / AZURE_HIERARCHY_FILE
        empty_structure = {}
    elif provider_lower == "aws":
        hierarchy_file = hierarchy_dir / AWS_HIERARCHY_FILE
        empty_structure = []
    else:
        # Should never reach here due to validation above, but defensive
        raise ValueError(f"Unhandled provider: {provider_lower}")
    
    if not hierarchy_file.exists():
        # Hierarchy is optional - return empty structure based on provider
        return empty_structure
    
    try:
        with open(hierarchy_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(
            f"Invalid JSON in hierarchy file: {e}",
            config_file=str(hierarchy_file)
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
    required_fields = ["digital_twin_name", "hot_storage_size_in_days", 
                       "cold_storage_size_in_days", "mode"]
    for field in required_fields:
        if field not in core_config:
            raise ConfigurationError(
                f"Missing required field '{field}' in {CONFIG_FILE}",
                config_file=str(project_path / CONFIG_FILE)
            )
    
    # Load remaining config files
    iot_devices = _load_json_file(project_path / CONFIG_IOT_DEVICES_FILE, required=True)
    events = _load_json_file(project_path / CONFIG_EVENTS_FILE, required=False)
    providers = _load_json_file(project_path / CONFIG_PROVIDERS_FILE, required=True)
    optimization = _load_json_file(project_path / CONFIG_OPTIMIZATION_FILE, required=False)
    inter_cloud = _load_json_file(project_path / CONFIG_INTER_CLOUD_FILE, required=False)
    user = _load_json_file(project_path / CONFIG_USER_FILE, required=False)
    
    # Load hierarchy based on L4 provider
    # layer_4_provider is REQUIRED for hierarchy loading (fail-fast)
    l4_provider = providers.get("layer_4_provider")
    if not l4_provider:
        raise ConfigurationError(
            "layer_4_provider not set in config_providers.json. This is required for hierarchy loading.",
            config_file=str(project_path / CONFIG_PROVIDERS_FILE)
        )
    hierarchy = _load_hierarchy_for_provider(project_path, l4_provider)
    
    # Construct ProjectConfig
    return ProjectConfig(
        digital_twin_name=core_config["digital_twin_name"],
        hot_storage_size_in_days=core_config["hot_storage_size_in_days"],
        cold_storage_size_in_days=core_config["cold_storage_size_in_days"],
        mode=core_config["mode"],
        iot_devices=iot_devices if isinstance(iot_devices, list) else iot_devices.get("devices", []),
        events=events if isinstance(events, list) else events.get("events", []),
        hierarchy=hierarchy,  # Preserve raw structure (dict for Azure, list for AWS)
        providers=providers,
        optimization=optimization,
        inter_cloud=inter_cloud,
        user=user,
    )


def load_optimization_flags(project_path: Path) -> dict:
    """
    Load feature flags from config_optimization.json.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dict with boolean feature flags. All default to False if missing.
        
    Note:
        Defaults are False for safety. Missing config triggers warning.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    defaults = {
        "useEventChecking": False,
        "triggerNotificationWorkflow": False,
        "returnFeedbackToDevice": False,
        "needs3DModel": False,
    }
    
    optimization_file = project_path / CONFIG_OPTIMIZATION_FILE
    
    if not optimization_file.exists():
        logger.warning(
            f"config_optimization.json not found in {project_path}. "
            f"All optimization features disabled (defaults to False)."
        )
        return defaults
    
    try:
        data = _load_json_file(optimization_file, required=False)
        flags = data.get("result", {}).get("inputParamsUsed", {})
        
        result = {}
        for key, default_val in defaults.items():
            if key in flags:
                result[key] = flags[key]
            else:
                logger.warning(f"  Missing optimization flag '{key}', defaulting to {default_val}")
                result[key] = default_val
        
        return result
    except Exception as e:
        logger.warning(
            f"Failed to load config_optimization.json: {e}. "
            f"Using defaults (all False)."
        )
        return defaults


def save_inter_cloud_connection(
    project_path: Path,
    conn_id: str,
    url: str,
    token: str
) -> None:
    """
    Save an inter-cloud connection to config_inter_cloud.json.
    
    Creates the file if it doesn't exist, or updates an existing connection.
    This is called during deployment when Function URLs are generated.
    
    Args:
        project_path: Path to the project directory
        conn_id: Connection identifier (e.g., "aws_l2_to_azure_l3hot")
        url: The Function URL for the remote writer/ingestion
        token: The inter-cloud authentication token
    
    Example:
        save_inter_cloud_connection(
            project_path=Path("/app/upload/my-project"),
            conn_id="aws_l3hot_to_azure_l3cold",
            url="https://func-cold-writer.azurewebsites.net/api/cold-writer",
            token="generated-secure-token"
        )
    """
    import logging
    logger = logging.getLogger(__name__)
    
    inter_cloud_path = project_path / CONFIG_INTER_CLOUD_FILE
    
    # Load existing or create new
    if inter_cloud_path.exists():
        with open(inter_cloud_path, 'r') as f:
            inter_cloud = json.load(f)
    else:
        inter_cloud = {"connections": {}}
    
    # Ensure connections key exists
    if "connections" not in inter_cloud:
        inter_cloud["connections"] = {}
    
    # Add/update connection
    inter_cloud["connections"][conn_id] = {
        "url": url,
        "token": token
    }
    
    # Save back
    with open(inter_cloud_path, 'w') as f:
        json.dump(inter_cloud, f, indent=4)
    
    logger.info(f"Saved inter-cloud connection '{conn_id}' to {CONFIG_INTER_CLOUD_FILE}")


def load_credentials(project_path: Path) -> Dict[str, dict]:
    """
    Load credentials for all configured providers.
    
    Credentials can be stored in either:
    - A single combined file: config_credentials.json
    - Separate files per provider: config_credentials_aws.json, etc.
    
    The combined file format:
        {
            "aws": {"aws_access_key_id": "...", ...},
            "azure": {"azure_subscription_id": "...", ...},
            "gcp": {"gcp_project_id": "...", ...}
        }
    
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
    
    # First check for combined config_credentials.json
    combined_path = project_path / "config_credentials.json"
    if combined_path.exists():
        combined_creds = _load_json_file(combined_path, required=False)
        if combined_creds:
            # Extract each provider's credentials
            if "aws" in combined_creds:
                credentials["aws"] = combined_creds["aws"]
            if "azure" in combined_creds:
                credentials["azure"] = combined_creds["azure"]
            if "gcp" in combined_creds:
                credentials["gcp"] = combined_creds["gcp"]
    
    # Also check for separate files (can override combined)
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
