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
import os
from pathlib import Path
from typing import Any

from src.core.config_loader import load_optimization_flags

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
    
    # Generate DIGITAL_TWIN_INFO JSON (unified structure for all providers)
    tfvars["digital_twin_info_json"] = _build_digital_twin_info_json(tfvars)
    
    # Load config_user.json for platform user
    tfvars.update(_load_platform_user_config(project_dir))
    
    # Load optimization feature flags (for conditional resources)
    optimization_flags = load_optimization_flags(project_dir)
        
    # Handle scene_assets_path for 3D models
    scene_assets_path = ""
    if optimization_flags["needs3DModel"]:
        scene_assets_dir = project_dir / "scene_assets"
        if scene_assets_dir.exists():
            scene_assets_path = str(scene_assets_dir)
            logger.info(f"  3D scene assets enabled: {scene_assets_path}")
        else:
            logger.warning(f"  needs3DModel=true but scene_assets/ not found")
    
    tfvars.update({
        "use_event_checking": optimization_flags["useEventChecking"],
        "trigger_notification_workflow": optimization_flags["triggerNotificationWorkflow"],
        "return_feedback_to_device": optimization_flags["returnFeedbackToDevice"],
        "needs_3d_model": optimization_flags["needs3DModel"],
        "scene_assets_path": scene_assets_path,
    })
    
    # Workflow definition file paths (conditional based on L2 provider)
    # Only set paths when the corresponding provider is used for L2
    l2_provider = providers["layer_2_provider"].lower()  # Fail explicitly if missing
    
    # Azure Logic App definition (only if L2 is Azure)
    if l2_provider == "azure":
        logic_app_path = project_dir / "state_machines" / "azure_logic_app.json"
        if logic_app_path.exists():
            tfvars["logic_app_definition_file"] = str(logic_app_path)
            logger.info(f"  Logic App definition: {logic_app_path}")
        else:
            tfvars["logic_app_definition_file"] = ""
    else:
        tfvars["logic_app_definition_file"] = ""
    
    # AWS Step Functions definition (only if L2 is AWS)
    if l2_provider == "aws":
        step_function_path = project_dir / "state_machines" / "aws_step_function.json"
        if step_function_path.exists():
            tfvars["step_function_definition_file"] = str(step_function_path)
            logger.info(f"  Step Function definition: {step_function_path}")
        else:
            tfvars["step_function_definition_file"] = ""
    else:
        tfvars["step_function_definition_file"] = ""
    
    # GCP Workflows definition (only if L2 is GCP)
    if l2_provider == "google":
        gcp_workflow_path = project_dir / "state_machines" / "google_cloud_workflow.yaml"
        if gcp_workflow_path.exists():
            tfvars["gcp_workflow_definition_file"] = str(gcp_workflow_path)
            logger.info(f"  GCP Workflow definition: {gcp_workflow_path}")
        else:
            tfvars["gcp_workflow_definition_file"] = ""
    else:
        tfvars["gcp_workflow_definition_file"] = ""
    
    # Build Azure function ZIPs if Azure is used as a provider
    tfvars.update(_build_azure_function_zips(project_dir, providers, optimization_flags))
    
    # Build GCP user function variables if GCP is used as a provider
    tfvars.update(_build_gcp_user_function_vars(project_dir, providers))
    
    # Build AWS user function variables if AWS is used as a provider
    tfvars.update(_get_aws_user_function_vars(project_dir, providers))
    
    # Write output file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(tfvars, f, indent=2)
    
    logger.info(f"✓ Generated tfvars: {output_path}")
    return tfvars


def _build_azure_function_zips(project_dir: Path, providers: dict, optimization_flags: dict) -> dict:
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
    from src.providers.terraform.package_builder import (
        build_azure_l0_bundle,
        build_azure_l1_bundle,
        build_azure_l2_bundle,
        build_azure_l3_bundle,
        build_azure_user_bundle,
    )
    
    zip_paths = {
        "azure_l0_zip_path": "",
        "azure_l1_zip_path": "",
        "azure_l2_zip_path": "",
        "azure_l3_zip_path": "",
        "azure_user_zip_path": "",
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
        l0_path = build_azure_l0_bundle(project_dir, providers)
        if l0_path:
            zip_paths["azure_l0_zip_path"] = str(l0_path)
            logger.info("    ✓ L0 ZIP built")
        
        # Build L1 dispatcher
        if providers.get("layer_1_provider") == "azure":
            l1_path = build_azure_l1_bundle(project_dir)
            if l1_path:
                zip_paths["azure_l1_zip_path"] = str(l1_path)
                logger.info("    ✓ L1 ZIP built")
        
        # Build L2 persister/processor
        if providers.get("layer_2_provider") == "azure":
            l2_path = build_azure_l2_bundle(project_dir)
            if l2_path:
                zip_paths["azure_l2_zip_path"] = str(l2_path)
                logger.info("    ✓ L2 ZIP built")
        
        # Build L3 reader/movers
        if providers.get("layer_3_hot_provider") == "azure":
            l3_path = build_azure_l3_bundle(project_dir)
            if l3_path:
                zip_paths["azure_l3_zip_path"] = str(l3_path)
                logger.info("    ✓ L3 ZIP built")
        
        # Build user functions (processors, event_actions, event-feedback)
        if providers.get("layer_2_provider") == "azure":
            user_path = build_azure_user_bundle(project_dir, providers, optimization_flags)
            if user_path:
                zip_paths["azure_user_zip_path"] = str(user_path)
                logger.info("    ✓ User ZIP built")
                
    except ImportError as e:
        logger.warning(f"  Function bundler not available: {e}")
    except Exception as e:
        logger.error(f"  Failed to build function ZIPs: {e}")
        raise
    
    return zip_paths


def _build_gcp_user_function_vars(project_dir: Path, providers: dict) -> dict:
    """
    Build GCP user function variables for Terraform.
    
    Reads config_iot_devices.json and config_events.json to generate lists
    of processors and event_actions with their ZIP paths.
    
    Args:
        project_dir: Path to project directory
        providers: Provider configuration dict from config_providers.json
    
    Returns:
        Dict with gcp_processors, gcp_event_actions, gcp_event_feedback_enabled, etc.
    """
    gcp_vars = {
        "gcp_processors": [],
        "gcp_event_actions": [],
        "gcp_event_feedback_enabled": False,
        "gcp_event_feedback_zip_path": ""
    }
    
    # Only build if L2 is GCP
    if providers.get("layer_2_provider") != "google":
        return gcp_vars
    
    build_dir = project_dir / ".build" / "gcp"
    
    # Load IoT devices config to get processors
    devices_path = project_dir / "config_iot_devices.json"
    if devices_path.exists():
        with open(devices_path, 'r') as f:
            devices = json.load(f)
        
        processors_seen = set()
        for device in devices:
            # Use device ID as processor folder name (matches wrapper expectations)
            device_id = device.get("id")
            if device_id and device_id not in processors_seen:
                processors_seen.add(device_id)
                zip_path = build_dir / f"processor-{device_id}.zip"
                if zip_path.exists():
                    gcp_vars["gcp_processors"].append({
                        "name": device_id,
                        "zip_path": str(zip_path)
                    })
    
    # Load events config to get event actions
    events_path = project_dir / "config_events.json"
    if events_path.exists():
        with open(events_path, 'r') as f:
            events = json.load(f)
        
        for event in events:
            if "action" in event and "functionName" in event["action"]:
                func_name = event["action"]["functionName"]
                zip_path = build_dir / f"{func_name}.zip"
                if zip_path.exists():
                    gcp_vars["gcp_event_actions"].append({
                        "name": func_name,
                        "zip_path": str(zip_path)
                    })
    
    # Check for event feedback
    feedback_zip = build_dir / "event-feedback.zip"
    if feedback_zip.exists():
        gcp_vars["gcp_event_feedback_enabled"] = True
        gcp_vars["gcp_event_feedback_zip_path"] = str(feedback_zip)
    
    return gcp_vars


def _get_aws_user_function_vars(project_dir: Path, providers: dict) -> dict:
    """
    Build AWS user function variable values from project config.
    
    Returns:
        Dict with aws_processors, aws_event_actions, aws_event_feedback_enabled, etc.
    """
    aws_vars = {
        "aws_processors": [],
        "aws_event_actions": [],
        "aws_event_feedback_enabled": False,
        "aws_event_feedback_zip_path": ""
    }
    
    # Only build if L2 is AWS
    if providers.get("layer_2_provider") != "aws":
        return aws_vars
    
    build_dir = project_dir / ".build" / "aws"
    
    # Load IoT devices config to get processors
    devices_path = project_dir / "config_iot_devices.json"
    if devices_path.exists():
        with open(devices_path, 'r') as f:
            devices = json.load(f)
        
        processors_seen = set()
        for device in devices:
            # Use device ID as processor folder name (matches wrapper expectations)
            device_id = device.get("id")
            if device_id and device_id not in processors_seen:
                processors_seen.add(device_id)
                zip_path = build_dir / f"processor-{device_id}.zip"
                if zip_path.exists():
                    aws_vars["aws_processors"].append({
                        "name": device_id,
                        "zip_path": str(zip_path)
                    })
    
    # Load events config to get event actions
    events_path = project_dir / "config_events.json"
    if events_path.exists():
        with open(events_path, 'r') as f:
            events = json.load(f)
        
        for event in events:
            if "action" in event and "functionName" in event["action"]:
                func_name = event["action"]["functionName"]
                zip_path = build_dir / f"{func_name}.zip"
                if zip_path.exists():
                    aws_vars["aws_event_actions"].append({
                        "name": func_name,
                        "zip_path": str(zip_path)
                    })
    
    # Check for event feedback
    feedback_zip = build_dir / "event-feedback.zip"
    if feedback_zip.exists():
        aws_vars["aws_event_feedback_enabled"] = True
        aws_vars["aws_event_feedback_zip_path"] = str(feedback_zip)
    
    return aws_vars


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
        # SSO region - may be different from main region (e.g., us-east-1 while resources are in eu-central-1)
        tfvars["aws_sso_region"] = aws.get("aws_sso_region", "")
    
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


def _build_digital_twin_info_json(tfvars: dict) -> str:
    """
    Build the unified DIGITAL_TWIN_INFO JSON for all cloud providers.
    
    This JSON is used by Lambda/Azure Functions/Cloud Functions at runtime
    to access configuration data for routing, processing, and storage operations.
    
    Args:
        tfvars: Dictionary of terraform variables (must contain providers, devices, events)
    
    Returns:
        JSON string containing complete digital twin configuration
    """
    digital_twin_info = {
        "config": {
            "digital_twin_name": tfvars.get("digital_twin_name", ""),
            "hot_storage_size_in_days": tfvars.get("layer_3_hot_to_cold_interval_days", 7),
            "cold_storage_size_in_days": tfvars.get("layer_3_cold_to_archive_interval_days", 30),
            "mode": tfvars.get("environment", "production"),
        },
        "config_iot_devices": tfvars.get("iot_devices", []),
        "config_events": tfvars.get("events", []),
        "config_providers": {
            "layer_1_provider": tfvars.get("layer_1_provider", ""),
            "layer_2_provider": tfvars.get("layer_2_provider", ""),
            "layer_3_hot_provider": tfvars.get("layer_3_hot_provider", ""),
            "layer_3_cold_provider": tfvars.get("layer_3_cold_provider", ""),
            "layer_3_archive_provider": tfvars.get("layer_3_archive_provider", ""),
            "layer_4_provider": tfvars.get("layer_4_provider", ""),
            "layer_5_provider": tfvars.get("layer_5_provider", ""),
        },
    }
    return json.dumps(digital_twin_info)


def _load_platform_user_config(project_dir: Path) -> dict:
    """Load platform user configuration from config_user.json."""
    user_file = project_dir / "config_user.json"
    
    if not user_file.exists():
        return {}
    
    with open(user_file) as f:
        user = json.load(f)
    
    result = {}
    
    # Map config fields to Terraform variables
    if user.get("admin_email"):
        result["platform_user_email"] = user["admin_email"]
        logger.info(f"  Platform user email: {user['admin_email']}")
    
    if user.get("admin_first_name"):
        result["platform_user_first_name"] = user["admin_first_name"]
    
    if user.get("admin_last_name"):
        result["platform_user_last_name"] = user["admin_last_name"]
    
    return result


if __name__ == "__main__":
    # CLI usage for testing
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python tfvars_generator.py <project_path> <output_path>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    generate_tfvars(sys.argv[1], sys.argv[2])
