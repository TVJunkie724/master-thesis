"""User-defined processor, event-action, and feedback package construction."""

import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict

from src.providers.terraform.package_builders.aws import _create_lambda_zip
from src.providers.terraform.package_builders.azure import _create_azure_function_zip
from src.providers.terraform.package_builders.common import _merge_requirements, _should_include_file
from src.providers.terraform.package_builders.gcp import _create_gcp_function_zip
from src.core.paths import validate_path_component
from src.core.deterministic_zip import atomic_zip_archive, write_zip_bytes, write_zip_file

logger = logging.getLogger(__name__)
PROVIDERS_ROOT = Path(__file__).resolve().parents[2]

def _compute_directory_hash(dir_path: Path) -> str:
    """
    Compute SHA256 hash of all files in a directory.
    
    Args:
        dir_path: Path to directory to hash
        
    Returns:
        SHA256 hash string prefixed with 'sha256:'
        
    Raises:
        ValueError: If directory doesn't exist
    """
    if not dir_path.exists():
        raise ValueError(f"Directory not found: {dir_path}")
    
    hasher = hashlib.sha256()
    
    for root, dirs, files in sorted(os.walk(str(dir_path))):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        
        for filename in sorted(files):
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, str(dir_path))
            
            # Hash the relative path
            hasher.update(rel_path.encode('utf-8'))
            
            # Hash the file content
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    hasher.update(chunk)
    
    return f"sha256:{hasher.hexdigest()}"


def _save_user_hash_metadata(
    project_path: Path,
    function_name: str,
    provider: str,
    code_hash: str
) -> None:
    """
    Save hash metadata for a built user function.
    
    Metadata is stored in upload/<project>/.build/metadata/
    
    Args:
        project_path: Path to project upload directory
        function_name: Name of the function
        provider: Provider name (aws/azure)
        code_hash: SHA256 hash of the function code
    """
    validate_path_component(function_name, "function name")
    validate_path_component(provider, "provider name")
    metadata_dir = project_path / ".build" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_path = metadata_dir / f"{function_name}.{provider}.json"
    
    metadata = {
        "function": function_name,
        "provider": provider,
        "zip_hash": code_hash,
        "last_built": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    }

    temporary_path = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    temporary_path.replace(metadata_path)
    
    logger.info(f"  Saved hash metadata: {function_name}.{provider}.json")


def build_user_packages(
    project_path: Path,
    providers_config: dict
) -> Dict[str, Path]:
    """
    Build user function packages from the project upload directory.
    
    This builds packages for:
    - Event actions (from config_events.json)
    - Processors (from config_iot_devices.json)
    - Event-feedback function
    
    Packages are built to upload/<project>/.build/{aws|azure}/
    Hash metadata is saved to upload/<project>/.build/metadata/
    
    Args:
        project_path: Path to project upload directory (upload/<project>/)
        providers_config: Layer provider configuration
        
    Returns:
        Dict mapping function names to ZIP paths
        
    Raises:
        ValueError: If required configs are missing
    """
    if not project_path.exists():
        raise ValueError(f"Project path not found: {project_path}")
    
    # Validate required config keys
    if "layer_2_provider" not in providers_config:
        raise ValueError("Missing required provider config: layer_2_provider")
    
    l2_provider = providers_config["layer_2_provider"].lower()
    
    if l2_provider not in ("aws", "azure", "google"):
        raise ValueError(f"Invalid layer_2_provider: {l2_provider}")
    
    # Normalize google -> gcp for consistent paths with other package builders
    # This ensures ZIPs go to .build/gcp/ where tfvars_generator expects them
    build_provider = "gcp" if l2_provider == "google" else l2_provider
    
    # Build output directory in project
    build_dir = project_path / ".build" / build_provider
    build_dir.mkdir(parents=True, exist_ok=True)
    
    packages = {}
    
    # Load config files
    events_path = project_path / "config_events.json"
    devices_path = project_path / "config_iot_devices.json"
    
    if not events_path.exists():
        raise ValueError("Missing required config: config_events.json")
    if not devices_path.exists():
        raise ValueError("Missing required config: config_iot_devices.json")
    
    with open(events_path, 'r') as f:
        events_config = json.load(f)
    with open(devices_path, 'r') as f:
        devices_config = json.load(f)
    
    # Determine source directories based on provider
    if l2_provider == "aws":
        user_funcs_dir = project_path / "lambda_functions"
        event_actions_dir = user_funcs_dir / "event_actions"
        processors_dir = user_funcs_dir / "processors"
        feedback_dir = user_funcs_dir / "event-feedback"
        shared_dir = PROVIDERS_ROOT / "aws" / "lambda_functions" / "_shared"
    elif l2_provider == "azure":
        user_funcs_dir = project_path / "azure_functions"
        event_actions_dir = user_funcs_dir / "event_actions"
        processors_dir = user_funcs_dir / "processors"
        feedback_dir = user_funcs_dir / "event-feedback"
        shared_dir = None  # Azure doesn't use shared dir
    else:  # google
        user_funcs_dir = project_path / "cloud_functions"
        event_actions_dir = user_funcs_dir / "event_actions"
        processors_dir = user_funcs_dir / "processors"
        feedback_dir = user_funcs_dir / "event-feedback"
        shared_dir = PROVIDERS_ROOT / "gcp" / "cloud_functions" / "_shared"
    
    logger.info(f"Building user packages for provider: {l2_provider}")
    
    # 1. Build Event Action packages
    # Note: Workflow actions (step_function, logic_app, workflow) trigger managed services
    # and don't have user function code to build - only lambda/function actions do
    WORKFLOW_ACTION_TYPES = {"step_function", "logic_app", "workflow"}
    
    for event in events_config:
        if "action" not in event:
            raise ValueError("Event config entry missing required 'action' field")
        
        action = event["action"]
        action_type = action.get("type", "")
        
        # Skip workflow actions - they trigger managed services, no user code to build
        if action_type in WORKFLOW_ACTION_TYPES:
            logger.info(f"  → Skipping {action_type} action (no user code to build)")
            continue
        
        # For lambda/function actions, require functionName
        if "functionName" not in action:
            raise ValueError("Event action missing required 'functionName' field")
        
        func_name = action["functionName"]
        func_dir = event_actions_dir / func_name
        
        if not func_dir.exists():
            raise ValueError(f"Missing code for event action: {func_name}. Expected: {func_dir}")
        
        # Compute hash
        code_hash = _compute_directory_hash(func_dir)
        
        # Build ZIP
        zip_path = build_dir / f"{func_name}.zip"
        if l2_provider == "aws":
            _create_lambda_zip(func_dir, shared_dir, zip_path)
        elif l2_provider == "google":
            _create_gcp_function_zip(func_dir, shared_dir, zip_path)
        else:  # azure
            _create_azure_function_zip(func_dir, zip_path)
        
        packages[func_name] = zip_path
        
        # Save hash metadata
        _save_user_hash_metadata(project_path, func_name, l2_provider, code_hash)
        
        logger.info(f"  ✓ Built event action: {func_name}.zip")
    
    # 2. Build Processor packages
    # Load digital_twin_name for processor renaming
    config_file = project_path / "config.json"
    digital_twin_name = ""
    if config_file.exists():
        config_data = json.loads(config_file.read_text())
        digital_twin_name = config_data.get("digital_twin_name", "")
    
    processors_seen = set()
    for device in devices_config:
        if "id" not in device:
            raise ValueError("Device config entry missing required 'id' field")
        
        device_id = device["id"]
        
        # Use device_id for folder lookup and ZIP naming (matches tfvars_generator)
        if device_id in processors_seen:
            continue
        processors_seen.add(device_id)
        
        proc_dir = processors_dir / device_id
        
        if not proc_dir.exists():
            raise ValueError(f"Missing processor code for device '{device_id}'. Expected: {proc_dir}")
        
        # Compute hash
        code_hash = _compute_directory_hash(proc_dir)
        
        # Build ZIP with processor wrapper for Azure
        zip_path = build_dir / f"processor-{device_id}.zip"
        
        if l2_provider == "aws":
            # User provides standalone lambda_function.py
            _create_lambda_zip(
                proc_dir, 
                shared_dir, 
                zip_path,
                digital_twin_name=digital_twin_name,
                device_id=device_id
            )
            packages[f"processor-{device_id}"] = zip_path
            _save_user_hash_metadata(project_path, f"processor-{device_id}", l2_provider, code_hash)
            logger.info(f"  ✓ Built processor: processor-{device_id}.zip")
        elif l2_provider == "azure":
            # Azure user functions are bundled together separately via build_azure_user_bundle()
            logger.info("  → Skipping individual processor ZIP for Azure (bundled together)")
        else:  # google
            # User provides standalone main.py
            _create_gcp_function_zip(
                proc_dir, 
                shared_dir, 
                zip_path,
                digital_twin_name=digital_twin_name,
                device_id=device_id
            )
            packages[f"processor-{device_id}"] = zip_path
            _save_user_hash_metadata(project_path, f"processor-{device_id}", l2_provider, code_hash)
            logger.info(f"  ✓ Built processor: processor-{device_id}.zip")
    
    # 3. Build Event-Feedback package (WITH WRAPPER MERGING)
    if feedback_dir.exists():
        code_hash = _compute_directory_hash(feedback_dir)
        zip_path = build_dir / "event-feedback.zip"
        
        # User provides standalone serverless function
        if l2_provider == "aws":
            _create_lambda_zip(feedback_dir, shared_dir, zip_path)
            packages["event-feedback"] = zip_path
            _save_user_hash_metadata(project_path, "event-feedback", l2_provider, code_hash)
            logger.info("  ✓ Built event-feedback.zip")
        elif l2_provider == "azure":
            # Azure bundles all user functions together via build_azure_user_bundle()
            logger.info("  → Skipping individual event-feedback ZIP for Azure (bundled together)")
        else:  # google
            _create_gcp_function_zip(feedback_dir, shared_dir, zip_path)
            packages["event-feedback"] = zip_path
            _save_user_hash_metadata(project_path, "event-feedback", l2_provider, code_hash)
            logger.info("  ✓ Built event-feedback.zip")
    
    logger.info(f"✓ Built {len(packages)} user packages")
    return packages


# Obsolete function removed - user functions now use HTTP call pattern



# Obsolete function removed - AWS processors now use standalone lambda_function.py





def _create_event_feedback_with_wrapper(
    feedback_dir: Path, 
    output_path: Path, 
    provider: str
) -> None:
    """
    Create event-feedback ZIP with the provider's event_feedback_wrapper.
    
    Merges user process.py with static wrapper code from /src.
    
    Args:
        feedback_dir: Path to user's event-feedback code (containing process.py)
        output_path: Path to output ZIP file
        provider: 'aws', 'azure', or 'google'
    """
    # Map provider to wrapper directory path
    provider_map = {
        'aws': PROVIDERS_ROOT / 'aws' / 'lambda_functions' / 'event_feedback_wrapper',
        'azure': PROVIDERS_ROOT / 'azure' / 'azure_functions' / 'event_feedback_wrapper',
        'google': PROVIDERS_ROOT / 'gcp' / 'cloud_functions' / 'event_feedback_wrapper',
    }
    
    wrapper_dir = provider_map.get(provider)
    if not wrapper_dir or not wrapper_dir.exists():
        logger.warning(f"No event_feedback_wrapper found for {provider}, bundling raw files")
        # Fallback to raw bundling
        if provider == 'aws':
            shared_dir = PROVIDERS_ROOT / 'aws' / 'lambda_functions' / '_shared'
            _create_lambda_zip(feedback_dir, shared_dir, output_path)
        elif provider == 'google':
            shared_dir = PROVIDERS_ROOT / 'gcp' / 'cloud_functions' / '_shared'
            _create_gcp_function_zip(feedback_dir, shared_dir, output_path)
        else:
            _create_azure_function_zip(feedback_dir, output_path)
        return
    
    with atomic_zip_archive(output_path) as zf:
        # 1. Add wrapper files (lambda_function.py/function_app.py/main.py, etc.)
        for file_path in sorted(wrapper_dir.rglob('*')):
            if file_path.is_file() and _should_include_file(file_path):
                arcname = file_path.relative_to(wrapper_dir)
                write_zip_file(zf, file_path, arcname)
        
        # 2. Add user's process.py at root level (required for 'from process import process')
        # Skip requirements.txt - will merge later
        # 2. Add user's process.py at root level (required for 'from process import process')
        # Skip requirements.txt - will merge later
        for file_path in sorted(feedback_dir.rglob('*')):
            if file_path.is_file() and _should_include_file(file_path):
                if file_path.name == 'requirements.txt':
                    continue  # Skip - will merge
                arcname = file_path.relative_to(feedback_dir)
                write_zip_file(zf, file_path, arcname)
        
        # 3. Add shared modules for AWS/GCP
        if provider == 'aws':
            shared_dir = PROVIDERS_ROOT / 'aws' / 'lambda_functions' / '_shared'
            if shared_dir.exists():
                for file_path in sorted(shared_dir.rglob('*')):
                    if file_path.is_file() and _should_include_file(file_path):
                        arcname = f"_shared/{file_path.relative_to(shared_dir)}"
                        write_zip_file(zf, file_path, arcname)
        elif provider == 'google':
            shared_dir = PROVIDERS_ROOT / 'gcp' / 'cloud_functions' / '_shared'
            if shared_dir.exists():
                for file_path in sorted(shared_dir.rglob('*')):
                    if file_path.is_file() and _should_include_file(file_path):
                        arcname = f"_shared/{file_path.relative_to(shared_dir)}"
                        write_zip_file(zf, file_path, arcname)
        
        # 4. Merge requirements.txt
        wrapper_req = wrapper_dir / "requirements.txt"
        user_req = feedback_dir / "requirements.txt"
        merged = _merge_requirements(wrapper_req, user_req)
        if merged:
            write_zip_bytes(zf, "requirements.txt", merged)
    
    logger.info(f"  ✓ Built event-feedback.zip with wrapper for {provider}")


def get_user_package_path(project_path: Path, function_name: str, provider: str) -> Path:
    """
    Get the path to a pre-built user package.
    
    Args:
        project_path: Path to project upload directory
        function_name: Name of the function
        provider: Provider name (aws/azure)
        
    Returns:
        Path to the ZIP file
    """
    return project_path / ".build" / provider / f"{function_name}.zip"
