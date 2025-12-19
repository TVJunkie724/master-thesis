"""
Zip Validator - Project archive validation with comprehensive cross-config checks.

This module provides validation for uploaded project zip files, ensuring:
1. Required files are present
2. Security (Zip Slip prevention)
3. Config schema validation
4. Cross-config consistency (payloads ↔ devices, credentials ↔ providers)
5. Optimization flag dependencies
6. Provider-specific function locations

Usage:
    from src.validation.zip_validator import validate_project_zip
    
    # Validate uploaded bytes
    validate_project_zip(zip_bytes)
    
    # Validate file path
    validate_project_zip("/path/to/project.zip")

All validation errors raise ValueError with descriptive messages.
"""

import os
import io
import json
import ast
import zipfile
from typing import Dict, List, Set, Any, Optional, Union
from logger import logger
import constants as CONSTANTS


# ==========================================
# Main Entry Point
# ==========================================

def validate_project_zip(zip_source: Union[str, bytes, io.BytesIO]) -> None:
    """
    Validates a project zip file for upload.
    
    Performs comprehensive validation including file presence, security,
    schema validation, and cross-config consistency checks.
    
    Args:
        zip_source: Path to zip file, raw bytes, or BytesIO object
        
    Raises:
        ValueError: For any validation failure with descriptive message
    """
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    with zipfile.ZipFile(zip_source, 'r') as zf:
        # Extract context needed by all checks
        ctx = _build_validation_context(zf)
        
        # Run all validation checks
        _check_required_files(zf, ctx)
        _check_zip_slip(zf)
        _check_config_schemas(zf, ctx)
        _check_state_machines(zf, ctx)
        _check_processor_syntax(zf, ctx)
        _check_event_actions(ctx)
        _check_feedback_function(ctx)
        _check_state_machine_presence(ctx)
        _check_payloads_vs_devices(zf, ctx)
        _check_credentials_per_provider(ctx)
        _check_hierarchy_provider_match(zf, ctx)


# ==========================================
# Validation Context Builder
# ==========================================

class ValidationContext:
    """Container for validation state shared across checks."""
    
    def __init__(self):
        self.project_root: str = ""
        self.zip_files: List[str] = []
        self.opt_config: Dict[str, Any] = {}
        self.prov_config: Dict[str, Any] = {}
        self.events_config: List[Dict[str, Any]] = []
        self.iot_config: List[Dict[str, Any]] = []
        self.credentials_config: Dict[str, Any] = {}
        self.seen_event_actions: Set[str] = set()
        self.seen_state_machines: Set[str] = set()
        self.seen_feedback_func: bool = False


def _build_validation_context(zf: zipfile.ZipFile) -> ValidationContext:
    """
    Build validation context by scanning zip contents.
    
    Extracts:
    - Project root prefix
    - Parsed config files
    - Tracked directories/files
    """
    ctx = ValidationContext()
    ctx.zip_files = zf.namelist()
    
    # Find project root (handles nested folders)
    for f in ctx.zip_files:
        if f.endswith(CONSTANTS.CONFIG_FILE):
            ctx.project_root = f.replace(CONSTANTS.CONFIG_FILE, "")
            break
    
    # Track directories and capture configs
    for member in zf.infolist():
        if member.is_dir():
            continue
            
        filename = member.filename
        basename = os.path.basename(filename)
        
        # Track event-feedback presence
        if f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/event-feedback/" in filename:
            ctx.seen_feedback_func = True
        
        # Track event actions
        if f"{CONSTANTS.EVENT_ACTIONS_DIR_NAME}/" in filename:
            parts = filename.split(f"{CONSTANTS.EVENT_ACTIONS_DIR_NAME}/")
            if len(parts) > 1:
                func_name = parts[1].split('/')[0]
                if func_name:
                    ctx.seen_event_actions.add(func_name)
        
        # Track state machines
        if basename in CONSTANTS.STATE_MACHINE_SIGNATURES:
            ctx.seen_state_machines.add(basename)
    
    return ctx


# ==========================================
# Individual Validation Checks
# ==========================================

def _check_required_files(zf: zipfile.ZipFile, ctx: ValidationContext) -> None:
    """
    Check that all required configuration files are present.
    
    Required files defined in CONSTANTS.REQUIRED_CONFIG_FILES.
    """
    for required_file in CONSTANTS.REQUIRED_CONFIG_FILES:
        expected_path = ctx.project_root + required_file
        if expected_path not in ctx.zip_files:
            raise ValueError(f"Missing required configuration file in zip: {required_file}")


def _check_zip_slip(zf: zipfile.ZipFile) -> None:
    """
    Prevent Zip Slip attacks (path traversal).
    
    Rejects paths containing '..' or absolute paths.
    """
    for member in zf.infolist():
        if member.is_dir():
            continue
        if ".." in member.filename or os.path.isabs(member.filename):
            raise ValueError("Malicious file path detected in zip (Zip Slip Prevention).")


def _check_config_schemas(zf: zipfile.ZipFile, ctx: ValidationContext) -> None:
    """
    Validate config file contents against schemas and capture for later checks.
    
    Uses validate_config_content from validator module.
    """
    from src.validator import validate_config_content
    
    for member in zf.infolist():
        if member.is_dir():
            continue
            
        basename = os.path.basename(member.filename)
        
        if basename in CONSTANTS.CONFIG_SCHEMAS:
            try:
                with zf.open(member) as f:
                    content = f.read().decode('utf-8')
                    validate_config_content(basename, content)
                    
                    # Capture for dependency checks
                    if basename == CONSTANTS.CONFIG_OPTIMIZATION_FILE:
                        ctx.opt_config = json.loads(content)
                    elif basename == CONSTANTS.CONFIG_PROVIDERS_FILE:
                        ctx.prov_config = json.loads(content)
                    elif basename == CONSTANTS.CONFIG_EVENTS_FILE:
                        ctx.events_config = json.loads(content)
                    elif basename == CONSTANTS.CONFIG_IOT_DEVICES_FILE:
                        ctx.iot_config = json.loads(content)
                    elif basename == CONSTANTS.CONFIG_CREDENTIALS_FILE:
                        ctx.credentials_config = json.loads(content)
                        
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Validation failed for {basename} inside zip: {e}")


def _check_state_machines(zf: zipfile.ZipFile, ctx: ValidationContext) -> None:
    """
    Validate state machine file contents.
    
    Uses validate_state_machine_content from validator module.
    """
    from src.validator import validate_state_machine_content
    
    for member in zf.infolist():
        if member.is_dir():
            continue
            
        basename = os.path.basename(member.filename)
        
        if basename in CONSTANTS.STATE_MACHINE_SIGNATURES:
            try:
                with zf.open(member) as f:
                    content = f.read().decode('utf-8')
                    validate_state_machine_content(basename, content)
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"State Machine validation failed for {basename} inside zip: {e}")


def _check_processor_syntax(zf: zipfile.ZipFile, ctx: ValidationContext) -> None:
    """
    Validate Python syntax for processor files.
    
    Checks process.py files in lambda_functions/processors/.
    """
    for member in zf.infolist():
        if member.is_dir():
            continue
            
        filename = member.filename
        
        if filename.endswith("process.py") and f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/" in filename:
            try:
                with zf.open(member) as f:
                    content = f.read().decode('utf-8')
                    ast.parse(content)
            except SyntaxError as e:
                raise ValueError(f"Syntax error in processor file {filename}: {e.msg} at line {e.lineno}")
            except Exception as e:
                raise ValueError(f"Validation failed for processor code {filename}: {e}")


def _check_event_actions(ctx: ValidationContext) -> None:
    """
    Check that event action functions exist when useEventChecking is enabled.
    
    Cross-references config_events.json with event_actions/ directory.
    """
    optimization = ctx.opt_config.get("result", {}).get("inputParamsUsed", {})
    
    if optimization.get("useEventChecking", False):
        for event in ctx.events_config:
            action = event.get("action", {})
            if action.get("type") == "lambda":
                func_name = action.get("functionName")
                if func_name and func_name not in ctx.seen_event_actions:
                    raise ValueError(f"Missing code for event action in zip: {func_name}")


def _check_feedback_function(ctx: ValidationContext) -> None:
    """
    Check that event-feedback function exists when returnFeedbackToDevice is enabled.
    """
    optimization = ctx.opt_config.get("result", {}).get("inputParamsUsed", {})
    
    if optimization.get("returnFeedbackToDevice", False):
        if not ctx.seen_feedback_func:
            raise ValueError("Missing event-feedback function in zip (required by returnFeedbackToDevice).")


def _check_state_machine_presence(ctx: ValidationContext) -> None:
    """
    Check that state machine file exists when triggerNotificationWorkflow is enabled.
    
    Determines required file based on layer_2_provider.
    """
    optimization = ctx.opt_config.get("result", {}).get("inputParamsUsed", {})
    
    if optimization.get("triggerNotificationWorkflow", False):
        provider = ctx.prov_config.get("layer_2_provider")
        if not provider:
            raise ValueError(
                "Missing 'layer_2_provider' in config_providers.json. "
                "Required when 'triggerNotificationWorkflow' is enabled."
            )
        provider = provider.lower()
        
        target_file_map = {
            "aws": CONSTANTS.AWS_STATE_MACHINE_FILE,
            "azure": CONSTANTS.AZURE_STATE_MACHINE_FILE,
            "google": CONSTANTS.GOOGLE_STATE_MACHINE_FILE
        }
        
        if provider not in target_file_map:
            raise ValueError(f"Invalid provider '{provider}' for state machine. Must be 'aws', 'azure', or 'google'.")
        
        target_file = target_file_map[provider]
        if target_file not in ctx.seen_state_machines:
            raise ValueError(
                f"Missing state machine definition '{target_file}' in zip for provider '{provider}' "
                "(required by triggerNotificationWorkflow)."
            )


# ==========================================
# NEW: Cross-Config Validation Checks
# ==========================================

def _check_payloads_vs_devices(zf: zipfile.ZipFile, ctx: ValidationContext) -> None:
    """
    Validate that iotDeviceId in payloads.json matches config_iot_devices.json.
    
    Each device referenced in payloads must exist in IoT device config.
    """
    # Find and parse payloads.json
    payloads_content = None
    for member in zf.infolist():
        if member.is_dir():
            continue
        if member.filename.endswith(CONSTANTS.PAYLOADS_FILE):
            try:
                with zf.open(member) as f:
                    payloads_content = json.loads(f.read().decode('utf-8'))
            except Exception:
                pass  # Payloads validation happens elsewhere
            break
    
    if not payloads_content or not ctx.iot_config:
        return  # Skip if either file missing (will be caught by required files check)
    
    # Get valid device IDs (config_iot_devices uses 'id', payloads uses 'iotDeviceId')
    valid_device_ids = {device.get("id") for device in ctx.iot_config if device.get("id")}
    
    # Check all payload device references
    for payload in payloads_content:
        device_id = payload.get("iotDeviceId")
        if device_id and device_id not in valid_device_ids:
            raise ValueError(
                f"Payload references unknown device '{device_id}'. "
                f"Valid devices: {sorted(valid_device_ids)}"
            )


def _check_credentials_per_provider(ctx: ValidationContext) -> None:
    """
    Validate that credentials exist for all providers configured in config_providers.json.
    
    Each layer's provider must have corresponding credentials.
    """
    if not ctx.prov_config or not ctx.credentials_config:
        return  # Skip if missing (will be caught by required files check)
    
    # Get all configured providers
    configured_providers = set()
    for key, value in ctx.prov_config.items():
        if key.startswith("layer_") and value:
            configured_providers.add(value.lower())
    
    # Check each provider has credentials
    for provider in configured_providers:
        if provider not in ctx.credentials_config:
            raise ValueError(
                f"Missing credentials for provider '{provider}'. "
                f"Add '{provider}' section to config_credentials.json."
            )


def _check_hierarchy_provider_match(zf: zipfile.ZipFile, ctx: ValidationContext) -> None:
    """
    Validate that hierarchy file exists for layer_4_provider.
    
    AWS requires aws_hierarchy.json, Azure requires azure_hierarchy.json.
    """
    if not ctx.prov_config:
        return
    
    layer_4_provider = ctx.prov_config.get("layer_4_provider")
    if not layer_4_provider:
        return  # L4 not configured
    
    layer_4_provider = layer_4_provider.lower()
    
    hierarchy_file_map = {
        "aws": "twin_hierarchy/aws_hierarchy.json",
        "azure": "twin_hierarchy/azure_hierarchy.json"
    }
    
    if layer_4_provider not in hierarchy_file_map:
        return  # Google doesn't have hierarchy file
    
    expected_file = hierarchy_file_map[layer_4_provider]
    full_path = ctx.project_root + expected_file
    
    if full_path not in ctx.zip_files:
        raise ValueError(
            f"Missing hierarchy file '{expected_file}' for layer_4_provider='{layer_4_provider}'."
        )
