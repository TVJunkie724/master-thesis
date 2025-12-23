"""
Core Validation Logic - Source-agnostic validation checks.

This module contains all validation logic that works with ANY file source
(ZIP file, directory, etc.) through the FileAccessor protocol.

Usage:
    from src.validation.core import run_all_checks
    from src.validation.accessors import ZipFileAccessor
    
    accessor = ZipFileAccessor(zipfile_obj)
    run_all_checks(accessor)  # Raises ValueError on failure
"""

import os
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Protocol
from dataclasses import dataclass, field

from logger import logger
import constants as CONSTANTS


# ==========================================
# Provider-to-Directory Mapping
# ==========================================

PROVIDER_FUNCTION_DIRS = {
    "aws": "lambda_functions",
    "azure": "azure_functions",
    "google": "cloud_functions",
    "gcp": "cloud_functions",  # alias
}


# ==========================================
# 1. File Accessor Protocol
# ==========================================

class FileAccessor(Protocol):
    """
    Protocol for accessing files from any source (ZIP, directory, etc.).
    
    Implementations must provide these methods to abstract file access.
    """
    
    def list_files(self) -> List[str]:
        """Return list of all file paths (relative to project root)."""
        ...
    
    def file_exists(self, path: str) -> bool:
        """Check if a file exists."""
        ...
    
    def read_text(self, path: str) -> str:
        """Read file contents as text. Raises FileNotFoundError if missing."""
        ...
    
    def get_project_root(self) -> str:
        """Return the project root prefix (empty for directories, nested path for ZIPs)."""
        ...


# ==========================================
# 2. Validation Context
# ==========================================

@dataclass
class ValidationContext:
    """
    Container for validation state shared across all checks.
    
    This is populated by build_context() and passed to all check functions.
    """
    project_root: str = ""
    all_files: List[str] = field(default_factory=list)
    
    # Parsed config files (populated during schema check)
    opt_config: Dict[str, Any] = field(default_factory=dict)
    prov_config: Dict[str, Any] = field(default_factory=dict)
    events_config: List[Dict[str, Any]] = field(default_factory=list)
    iot_config: List[Dict[str, Any]] = field(default_factory=list)
    credentials_config: Dict[str, Any] = field(default_factory=dict)
    
    # Tracked directories/files (populated during context build)
    seen_event_actions: Set[str] = field(default_factory=set)
    seen_state_machines: Set[str] = field(default_factory=set)
    seen_feedback_func: bool = False


# ==========================================
# 3. Context Builder
# ==========================================

def build_context(accessor: FileAccessor) -> ValidationContext:
    """
    Build validation context by scanning file source.
    
    This scans the file list and populates tracking sets.
    """
    ctx = ValidationContext()
    ctx.all_files = accessor.list_files()
    ctx.project_root = accessor.get_project_root()
    
    FUNCTION_DIR_NAMES = [
        CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME,  # lambda_functions (AWS)
        "azure_functions",                     # Azure
        "cloud_functions",                     # GCP
    ]
    
    for filepath in ctx.all_files:
        basename = os.path.basename(filepath)
        
        # Track event-feedback presence (ALL PROVIDERS)
        for func_dir in FUNCTION_DIR_NAMES:
            if f"{func_dir}/event-feedback/" in filepath:
                ctx.seen_feedback_func = True
                break
        
        # Track event actions (ALL PROVIDERS)
        for func_dir in FUNCTION_DIR_NAMES:
            if f"{func_dir}/{CONSTANTS.EVENT_ACTIONS_DIR_NAME}/" in filepath:
                parts = filepath.split(f"{CONSTANTS.EVENT_ACTIONS_DIR_NAME}/")
                if len(parts) > 1:
                    func_name = parts[1].split('/')[0]
                    if func_name:
                        ctx.seen_event_actions.add(func_name)
                break
        
        # Track state machines
        if basename in CONSTANTS.STATE_MACHINE_SIGNATURES:
            ctx.seen_state_machines.add(basename)
    
    return ctx


# ==========================================
# 4. Core Validation Checks
# ==========================================

def check_required_files(accessor: FileAccessor, ctx: ValidationContext) -> None:
    """Check that all required configuration files are present."""
    for required_file in CONSTANTS.REQUIRED_CONFIG_FILES:
        expected_path = ctx.project_root + required_file
        if not accessor.file_exists(expected_path):
            raise ValueError(f"Missing required configuration file: {required_file}")


def check_config_schemas(accessor: FileAccessor, ctx: ValidationContext) -> None:
    """
    Validate config file contents against schemas.
    Also populates ctx with parsed config data for later checks.
    """
    from src.validator import validate_config_content
    
    for filepath in ctx.all_files:
        basename = os.path.basename(filepath)
        
        if basename in CONSTANTS.CONFIG_SCHEMAS:
            try:
                content = accessor.read_text(filepath)
                validate_config_content(basename, content)
                
                # Capture parsed configs for dependency checks
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
                raise ValueError(f"Validation failed for {basename}: {e}")


def check_state_machines(accessor: FileAccessor, ctx: ValidationContext) -> None:
    """Validate state machine file contents."""
    from src.validator import validate_state_machine_content
    
    for filepath in ctx.all_files:
        basename = os.path.basename(filepath)
        
        if basename in CONSTANTS.STATE_MACHINE_SIGNATURES:
            try:
                content = accessor.read_text(filepath)
                validate_state_machine_content(basename, content)
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"State Machine validation failed for {basename}: {e}")


def check_processor_syntax(accessor: FileAccessor, ctx: ValidationContext, l2_provider: str = None) -> None:
    """Validate Python syntax and signatures for user code files (filtered by provider)."""
    # Build patterns based on configured provider
    if l2_provider:
        func_dir = PROVIDER_FUNCTION_DIRS.get(l2_provider.lower(), "")
        if not func_dir:
            raise ValueError(f"Unknown layer_2_provider '{l2_provider}'. Expected: aws, azure, or google.")
        PROCESSOR_PATTERNS = [rf".*{func_dir}/processors/[^/]+/process\.py$"]
        EVENT_FEEDBACK_PATTERNS = [rf".*{func_dir}/event-feedback/process\.py$"]
    else:
        # No provider specified - check all providers
        PROCESSOR_PATTERNS = [
            rf".*{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/[^/]+/process\.py$",
            r".*azure_functions/processors/[^/]+/process\.py$",
            r".*cloud_functions/processors/[^/]+/process\.py$",
        ]
        EVENT_FEEDBACK_PATTERNS = [
            rf".*{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/event-feedback/process\.py$",
            r".*azure_functions/event-feedback/process\.py$",
            r".*cloud_functions/event-feedback/process\.py$",
        ]
    
    ALL_PATTERNS = PROCESSOR_PATTERNS + EVENT_FEEDBACK_PATTERNS
    
    for filepath in ctx.all_files:
        is_user_code = any(re.match(pattern, filepath) for pattern in ALL_PATTERNS)
        
        if is_user_code:
            try:
                content = accessor.read_text(filepath)
                ast.parse(content)  # Syntax check
                _validate_process_signature(content, filepath)  # Signature check
            except SyntaxError as e:
                raise ValueError(f"Syntax error in {filepath}: {e.msg} at line {e.lineno}")
            except Exception as e:
                raise ValueError(f"Validation failed for {filepath}: {e}")


def _validate_process_signature(content: str, filename: str) -> None:
    """Validate process() function has correct signature with type hints."""
    tree = ast.parse(content)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "process":
            if len(node.args.args) != 1:
                raise ValueError(f"{filename}: process() must have exactly 1 parameter")
            
            arg = node.args.args[0]
            if arg.annotation is None:
                raise ValueError(f"{filename}: process() parameter must have type hint 'dict'")
            
            if not (isinstance(arg.annotation, ast.Name) and arg.annotation.id == "dict"):
                raise ValueError(f"{filename}: process() parameter type must be 'dict'")
            
            if node.returns is None:
                raise ValueError(f"{filename}: process() must have return type hint '-> dict'")
            
            if not (isinstance(node.returns, ast.Name) and node.returns.id == "dict"):
                raise ValueError(f"{filename}: process() return type must be 'dict'")
            
            return  # Found valid process function
    
    raise ValueError(f"{filename}: Missing required process() function")


def check_event_actions(ctx: ValidationContext) -> None:
    """Check that event action functions exist when useEventChecking is enabled."""
    optimization = ctx.opt_config.get("result", {}).get("inputParamsUsed", {})
    
    if optimization.get("useEventChecking", False):
        for event in ctx.events_config:
            action = event.get("action", {})
            if action.get("type") == "lambda":
                func_name = action.get("functionName")
                if func_name and func_name not in ctx.seen_event_actions:
                    raise ValueError(f"Missing code for event action: {func_name}")


def check_feedback_function(ctx: ValidationContext) -> None:
    """Check that event-feedback function exists when returnFeedbackToDevice is enabled."""
    optimization = ctx.opt_config.get("result", {}).get("inputParamsUsed", {})
    
    if optimization.get("returnFeedbackToDevice", False):
        if not ctx.seen_feedback_func:
            raise ValueError("Missing event-feedback function (required by returnFeedbackToDevice).")


def check_state_machine_presence(ctx: ValidationContext) -> None:
    """Check that state machine file exists when triggerNotificationWorkflow is enabled."""
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
            "google": CONSTANTS.GOOGLE_STATE_MACHINE_FILE,
            "gcp": CONSTANTS.GOOGLE_STATE_MACHINE_FILE,  # alias
        }
        
        if provider not in target_file_map:
            raise ValueError(f"Invalid provider '{provider}' for state machine.")
        
        target_file = target_file_map[provider]
        if target_file not in ctx.seen_state_machines:
            raise ValueError(
                f"Missing state machine definition '{target_file}' for provider '{provider}' "
                "(required by triggerNotificationWorkflow)."
            )


def check_payloads_vs_devices(accessor: FileAccessor, ctx: ValidationContext) -> None:
    """Validate that iotDeviceId in payloads.json matches config_iot_devices.json."""
    payloads_path = ctx.project_root + CONSTANTS.PAYLOADS_FILE
    
    if not accessor.file_exists(payloads_path):
        return  # Skip if file missing
    
    try:
        payloads_content = json.loads(accessor.read_text(payloads_path))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in payloads.json: {e.msg} at line {e.lineno}")
    except Exception as e:
        raise ValueError(f"Failed to read payloads.json: {e}")

    if not ctx.iot_config:
        return  # Skip device matching if no IoT devices configured
    
    valid_device_ids = {device.get("id") for device in ctx.iot_config if device.get("id")}
    
    for payload in payloads_content:
        device_id = payload.get("iotDeviceId")
        if device_id and device_id not in valid_device_ids:
            raise ValueError(
                f"Payload references unknown device '{device_id}'. "
                f"Valid devices: {sorted(valid_device_ids)}"
            )


def check_credentials_per_provider(ctx: ValidationContext) -> None:
    """Validate that credentials exist for all configured providers."""
    if not ctx.prov_config or not ctx.credentials_config:
        return  # Skip if missing
    
    configured_providers = set()
    for key, value in ctx.prov_config.items():
        if key.startswith("layer_") and value:
            configured_providers.add(value.lower())
    
    for provider in configured_providers:
        if provider not in ctx.credentials_config:
            raise ValueError(
                f"Missing credentials for provider '{provider}'. "
                f"Add '{provider}' section to config_credentials.json."
            )


def check_hierarchy_provider_match(accessor: FileAccessor, ctx: ValidationContext) -> None:
    """Validate that hierarchy file exists for layer_4_provider."""
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
    
    if not accessor.file_exists(full_path):
        raise ValueError(
            f"Missing hierarchy file '{expected_file}' for layer_4_provider='{layer_4_provider}'."
        )


def check_scene_assets(accessor: FileAccessor, ctx: ValidationContext) -> None:
    """Validate scene assets when needs3DModel is enabled."""
    input_params = ctx.opt_config.get("result", {}).get("inputParamsUsed", {})
    needs_3d_model = input_params.get("needs3DModel", False)
    
    if not needs_3d_model:
        return
    
    layer_4_provider = ctx.prov_config.get("layer_4_provider", "")
    if layer_4_provider:
        layer_4_provider = layer_4_provider.lower()
    
    if not layer_4_provider or layer_4_provider not in CONSTANTS.SCENE_REQUIRED_FILES:
        return
    
    required_files = CONSTANTS.SCENE_REQUIRED_FILES[layer_4_provider]
    missing_files = []
    
    for required_file in required_files:
        full_path = ctx.project_root + required_file
        if not accessor.file_exists(full_path):
            missing_files.append(required_file)
    
    if missing_files:
        raise ValueError(
            f"Missing scene asset(s) for layer_4_provider='{layer_4_provider}' when needs3DModel=true: "
            f"{missing_files}. Required files: {required_files}"
        )


def check_provider_function_directory(accessor: FileAccessor, ctx: ValidationContext, l2_provider: str) -> None:
    """Ensure the configured provider's function directory exists."""
    if not l2_provider:
        return  # No L2 configured
    
    func_dir = PROVIDER_FUNCTION_DIRS.get(l2_provider.lower())
    if not func_dir:
        raise ValueError(f"Unknown layer_2_provider '{l2_provider}'. Expected: aws, azure, or google.")
    
    # Check if any file exists in the provider's function directory
    has_files = any(f.startswith(func_dir + "/") for f in ctx.all_files)
    if not has_files:
        raise ValueError(
            f"Missing function directory '{func_dir}/' for layer_2_provider='{l2_provider}'."
        )


def check_processor_folders_match_devices(accessor: FileAccessor, ctx: ValidationContext, l2_provider: str) -> None:
    """
    Validate that a processor folder exists for each device in config_iot_devices.json.
    
    Processor folder name must match device ID exactly.
    Example: Device "temp-sensor-1" requires folder "processors/temp-sensor-1/"
    
    The user function file inside must be:
    - Azure: function_app.py
    - AWS: lambda_function.py
    - GCP: main.py
    """
    if not ctx.iot_config:
        return  # No devices configured
    
    func_dir = PROVIDER_FUNCTION_DIRS.get(l2_provider.lower(), "")
    if not func_dir:
        return
    
    # Get all device IDs from config
    device_ids = {device.get("id") for device in ctx.iot_config if device.get("id")}
    
    # Determine expected file pattern per provider
    file_patterns = {
        "azure": "function_app.py",
        "aws": "lambda_function.py",
        "google": "main.py",
        "gcp": "main.py",
    }
    expected_file = file_patterns.get(l2_provider.lower(), "function_app.py")
    
    for device_id in device_ids:
        expected_path = f"{func_dir}/processors/{device_id}/{expected_file}"
        full_path = ctx.project_root + expected_path
        
        if not accessor.file_exists(full_path):
            raise ValueError(
                f"Missing processor for device '{device_id}'. "
                f"Expected: {expected_path}"
            )


# ==========================================
# 5. Main Orchestrator
# ==========================================

def run_all_checks(accessor: FileAccessor) -> None:
    """
    Run all validation checks.
    
    This is the single entrypoint for all validation.
    
    Args:
        accessor: FileAccessor implementation (ZIP or Directory)
        
    Raises:
        ValueError: On any validation failure with descriptive message
    """
    # Phase 1: Build initial context (scans ALL files)
    ctx = build_context(accessor)
    
    # Phase 2: Schema validation (populates ctx.prov_config)
    check_required_files(accessor, ctx)
    check_config_schemas(accessor, ctx)
    
    # Phase 3: Get provider for provider-specific checks (fail-fast)
    l2_provider = ctx.prov_config.get("layer_2_provider")
    if not l2_provider:
        raise ValueError("Missing required 'layer_2_provider' in config_providers.json")
    l2_provider = l2_provider.lower()
    
    # Phase 4: Provider-specific validations
    check_provider_function_directory(accessor, ctx, l2_provider)
    check_state_machines(accessor, ctx)  # Already uses ctx.prov_config
    check_processor_syntax(accessor, ctx, l2_provider)
    check_event_actions(ctx)
    check_feedback_function(ctx)
    check_processor_folders_match_devices(accessor, ctx, l2_provider)
    check_state_machine_presence(ctx)  # Already provider-aware
    
    # Phase 5: Cross-cutting validations
    check_payloads_vs_devices(accessor, ctx)
    check_credentials_per_provider(ctx)
    check_hierarchy_provider_match(accessor, ctx)
    check_scene_assets(accessor, ctx)
    
    logger.info("✓ All validation checks passed")
