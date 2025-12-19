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
    providers = _load_providers(project_dir)
    tfvars.update(providers)
    
    # Load config_iot_devices.json (device definitions)
    tfvars.update(_load_iot_devices(project_dir))
    
    # Load config_events.json (event actions)
    tfvars.update(_load_events(project_dir))
    
    # Load existing inter-cloud token if available
    tfvars.update(_load_inter_cloud(project_dir))
    
    # Load optimization feature flags (for conditional resources)
    tfvars.update(_load_optimization_flags(project_dir))
    
    # Build Azure function ZIPs if Azure is used as a provider
    tfvars.update(_build_azure_function_zips(project_dir, providers))
    
    # Write output file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(tfvars, f, indent=2)
    
    logger.info(f"✓ Generated tfvars: {output_path}")
    return tfvars


def _build_azure_function_zips(project_dir: Path, providers: dict) -> dict:
    """
    Build Azure function ZIP files for Terraform zip_deploy_file.
    
    Uses the existing function_bundler to create ZIP files, then returns
    the paths for Terraform to deploy via zip_deploy_file attribute.
    This ensures function code exists before EventGrid subscriptions.
    
    Args:
        project_dir: Path to the project directory
        providers: Provider configuration dict from config_providers.json
    
    Returns:
        Dict with azure_l0_zip_path, azure_l1_zip_path, etc.
    """
    from src.providers.azure.layers.function_bundler import (
        bundle_l0_functions,
        bundle_l1_functions,
        bundle_l2_functions,
        bundle_l3_functions,
    )
    
    zip_paths = {
        "azure_l0_zip_path": "",
        "azure_l1_zip_path": "",
        "azure_l2_zip_path": "",
        "azure_l3_zip_path": "",
    }
    
    # Create a temp directory for ZIP files in the project
    zip_dir = project_dir / ".terraform_zips"
    zip_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if any Azure provider is used
    uses_azure = any(
        providers.get(f"layer_{i}_provider") == "azure" 
        for i in [1, 2]
    ) or any(
        providers.get(f"layer_3_{tier}_provider") == "azure" 
        for tier in ["hot", "cold", "archive"]
    )
    
    if not uses_azure:
        logger.info("  No Azure providers configured, skipping ZIP builds")
        return zip_paths
    
    logger.info("  Building Azure function ZIPs for Terraform deployment...")
    
    try:
        # Build L0 glue functions
        l0_zip, l0_funcs = bundle_l0_functions(str(project_dir), providers)
        if l0_zip and l0_funcs:
            l0_path = zip_dir / "l0_functions.zip"
            with open(l0_path, "wb") as f:
                f.write(l0_zip)
            zip_paths["azure_l0_zip_path"] = str(l0_path)
            logger.info(f"    ✓ L0 ZIP: {len(l0_funcs)} functions")
        
        # Build L1 dispatcher
        if providers.get("layer_1_provider") == "azure":
            l1_zip = bundle_l1_functions(str(project_dir))
            if l1_zip:
                l1_path = zip_dir / "l1_functions.zip"
                with open(l1_path, "wb") as f:
                    f.write(l1_zip)
                zip_paths["azure_l1_zip_path"] = str(l1_path)
                logger.info("    ✓ L1 ZIP: dispatcher function")
        
        # Build L2 persister/processor
        if providers.get("layer_2_provider") == "azure":
            l2_zip = bundle_l2_functions(str(project_dir))
            if l2_zip:
                l2_path = zip_dir / "l2_functions.zip"
                with open(l2_path, "wb") as f:
                    f.write(l2_zip)
                zip_paths["azure_l2_zip_path"] = str(l2_path)
                logger.info("    ✓ L2 ZIP: persister/processor functions")
        
        # Build L3 reader/movers
        if providers.get("layer_3_hot_provider") == "azure":
            l3_zip = bundle_l3_functions(str(project_dir))
            if l3_zip:
                l3_path = zip_dir / "l3_functions.zip"
                with open(l3_path, "wb") as f:
                    f.write(l3_zip)
                zip_paths["azure_l3_zip_path"] = str(l3_path)
                logger.info("    ✓ L3 ZIP: reader/mover functions")
                
    except ImportError as e:
        logger.warning(f"  Function bundler not available: {e}")
    except Exception as e:
        logger.error(f"  Failed to build function ZIPs: {e}")
        raise
    
    return zip_paths


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
    
    # GCP credentials - support dual-mode: project_id (private) OR billing_account (org)
    if "gcp" in creds:
        gcp = creds["gcp"]
        
        # gcp_region is always required
        if "gcp_region" not in gcp:
            raise ConfigurationError("Missing required GCP credential: gcp_region")
        
        # Dual-mode validation: either gcp_project_id OR gcp_billing_account required
        has_project_id = "gcp_project_id" in gcp and gcp["gcp_project_id"].strip()
        has_billing_account = "gcp_billing_account" in gcp and gcp["gcp_billing_account"].strip()
        
        if not has_project_id and not has_billing_account:
            raise ConfigurationError(
                "GCP requires either 'gcp_project_id' (for private accounts with existing project) "
                "or 'gcp_billing_account' (for organization accounts with auto-project creation). "
                "Please provide at least one."
            )
        
        tfvars["gcp_region"] = gcp["gcp_region"]
        
        # Private account mode: use existing project
        if has_project_id:
            tfvars["gcp_project_id"] = gcp["gcp_project_id"].strip()
        
        # Organization account mode: auto-create project
        if has_billing_account:
            tfvars["gcp_billing_account"] = gcp["gcp_billing_account"].strip()
        
        # GCP credentials file - resolve relative paths, then read if exists
        creds_file_raw = gcp.get("gcp_credentials_file", "")
        
        # Resolve relative paths relative to project directory
        if creds_file_raw and not os.path.isabs(creds_file_raw):
            creds_file_path = project_dir / creds_file_raw
        else:
            creds_file_path = Path(creds_file_raw)
        
        if creds_file_path.exists():
            with open(creds_file_path) as f:
                tfvars["gcp_credentials_json"] = f.read()
        else:
            # Dummy credentials to prevent Terraform ADC lookup
            tfvars["gcp_credentials_json"] = '{"type":"service_account","project_id":"dummy","private_key_id":"","private_key":"","client_email":"dummy@dummy.iam.gserviceaccount.com","client_id":"","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}'
    
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


def _load_events(project_dir: Path) -> dict:
    """Load event definitions from config_events.json."""
    events_file = project_dir / "config_events.json"
    
    if not events_file.exists():
        # Events are optional
        return {"events": []}
    
    with open(events_file) as f:
        events = json.load(f)
    
    # File is a direct array of events
    if not isinstance(events, list):
        raise ConfigurationError("config_events.json must be an array of events")
    
    return {"events": events}


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


def _load_optimization_flags(project_dir: Path) -> dict:
    """
    Load feature flags from config_optimization.json for conditional Terraform resources.
    
    Maps inputParamsUsed to Terraform variable names:
    - useEventChecking -> use_event_checking
    - triggerNotificationWorkflow -> trigger_notification_workflow
    - returnFeedbackToDevice -> return_feedback_to_device
    """
    optimization_file = project_dir / "config_optimization.json"
    
    # Default values (safe defaults for testing)
    defaults = {
        "use_event_checking": True,
        "trigger_notification_workflow": False,  # Disabled for initial testing
        "return_feedback_to_device": False,
    }
    
    if not optimization_file.exists():
        logger.info("  No config_optimization.json, using default feature flags")
        return defaults
    
    try:
        with open(optimization_file) as f:
            data = json.load(f)
        
        input_params = data.get("result", {}).get("inputParamsUsed", {})
        
        return {
            "use_event_checking": input_params.get("useEventChecking", True),
            "trigger_notification_workflow": input_params.get("triggerNotificationWorkflow", False),
            "return_feedback_to_device": input_params.get("returnFeedbackToDevice", False),
        }
    except Exception as e:
        logger.warning(f"  Failed to load config_optimization.json: {e}, using defaults")
        return defaults


if __name__ == "__main__":
    # CLI usage for testing
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python tfvars_generator.py <project_path> <output_path>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    generate_tfvars(sys.argv[1], sys.argv[2])
