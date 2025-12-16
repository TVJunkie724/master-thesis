"""
Function Package Builder for Terraform Deployment.

This module builds ZIP packages for all Lambda/Azure Functions
BEFORE Terraform runs, so Terraform can reference the pre-built packages.

AWS: Terraform uses ZIPs directly (no post-deployment upload needed)
Azure: ZIPs are uploaded via Kudu after Terraform creates infrastructure
"""

import io
import os
import shutil
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Build output directory (relative to terraform directory)
BUILD_DIR = ".build"


def build_all_packages(
    terraform_dir: Path,
    project_path: Path,
    providers_config: dict
) -> Dict[str, Path]:
    """
    Build all Lambda/Function packages before Terraform deployment.
    
    Args:
        terraform_dir: Path to src/terraform/
        project_path: Path to project directory
        providers_config: Layer provider configuration
    
    Returns:
        Dict mapping function names to ZIP paths
    """
    build_dir = terraform_dir / BUILD_DIR
    build_dir.mkdir(parents=True, exist_ok=True)
    
    packages = {}
    
    # Build AWS Lambda packages
    aws_packages = build_aws_lambda_packages(terraform_dir, project_path, providers_config)
    packages.update(aws_packages)
    
    # Build Azure Function packages
    azure_packages = build_azure_function_packages(terraform_dir, project_path, providers_config)
    packages.update(azure_packages)
    
    logger.info(f"✓ Built {len(packages)} function packages")
    return packages


def build_aws_lambda_packages(
    terraform_dir: Path,
    project_path: Path,
    providers_config: dict
) -> Dict[str, Path]:
    """
    Build AWS Lambda packages to .build/aws/*.zip.
    Only builds functions that are needed based on provider config.
    
    Returns:
        Dict mapping Lambda names to ZIP paths
    """
    build_dir = terraform_dir / BUILD_DIR / "aws"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Lambda functions directory
    lambda_dir = Path(__file__).parent.parent / "aws" / "lambda_functions"
    shared_dir = lambda_dir / "_shared"
    
    packages = {}
    functions_to_build = []
    
    # L0 Glue functions - only when cross-cloud boundaries exist
    # Required config keys (fail-fast - no silent fallbacks)
    required_keys = [
        "layer_1_provider", "layer_2_provider", 
        "layer_3_hot_provider", "layer_3_cold_provider", "layer_3_archive_provider",
        "layer_4_provider"
    ]
    for key in required_keys:
        if key not in providers_config:
            raise ValueError(f"Missing required provider config: {key}")
    
    l1 = providers_config["layer_1_provider"]
    l2 = providers_config["layer_2_provider"]
    l3_hot = providers_config["layer_3_hot_provider"]
    l3_cold = providers_config["layer_3_cold_provider"]
    l3_archive = providers_config["layer_3_archive_provider"]
    l4 = providers_config["layer_4_provider"]
    
    # Ingestion: L1 on another cloud, L2 on AWS
    if l1 != "aws" and l2 == "aws":
        functions_to_build.append("ingestion")
    
    # Hot Writer: L2 on another cloud, L3 hot on AWS
    if l2 != "aws" and l3_hot == "aws":
        functions_to_build.append("hot-writer")
    
    # Hot Reader: L3 hot on AWS, L4 on another cloud
    if l3_hot == "aws" and l4 != "aws":
        functions_to_build.append("hot-reader")
    
    # Cold Writer: L3 hot on another cloud, L3 cold on AWS
    if l3_hot != "aws" and l3_cold == "aws":
        functions_to_build.append("cold-writer")
    
    # Archive Writer: L3 cold on another cloud, L3 archive on AWS
    if l3_cold != "aws" and l3_archive == "aws":
        functions_to_build.append("archive-writer")
    
    # L1 IoT functions - when L1 is AWS
    if l1 == "aws":
        functions_to_build.extend(["dispatcher", "connector"])
    
    # L2 Compute functions - when L2 is AWS
    if l2 == "aws":
        functions_to_build.extend(["persister", "event-checker"])
    
    # L3 Storage functions - when L3 is AWS
    if l3_hot == "aws":
        functions_to_build.append("hot-to-cold-mover")
    if l3_cold == "aws":
        functions_to_build.append("cold-to-archive-mover")
    
    # L4 Twin functions - when L4 is AWS
    if l4 == "aws":
        functions_to_build.append("digital-twin-data-connector")
    
    # Build each function
    for func_name in functions_to_build:
        func_dir = lambda_dir / func_name
        if func_dir.exists():
            zip_path = build_dir / f"{func_name}.zip"
            _create_lambda_zip(func_dir, shared_dir, zip_path)
            packages[f"aws_{func_name}"] = zip_path
            logger.info(f"  ✓ Built: {func_name}.zip")
        else:
            logger.warning(f"  ⚠ Lambda dir not found: {func_dir}")
    
    if not functions_to_build:
        logger.info("  No AWS Lambda functions needed for this configuration")
    
    return packages


def build_azure_function_packages(
    terraform_dir: Path,
    project_path: Path,
    providers_config: dict
) -> Dict[str, Path]:
    """
    Build all Azure Function packages to .build/azure/*.zip.
    
    Returns:
        Dict mapping Function App names to ZIP paths
    """
    # Check if any layer uses Azure
    azure_layers = ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider",
                    "layer_4_provider", "layer_5_provider"]
    has_azure = any(providers_config.get(layer) == "azure" for layer in azure_layers)
    
    if not has_azure:
        logger.info("  No Azure layers configured, skipping Function package build")
        return {}
    
    build_dir = terraform_dir / BUILD_DIR / "azure"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Azure functions directory
    azure_funcs_dir = Path(__file__).parent.parent / "azure" / "azure_functions"
    
    packages = {}
    
    # Azure Function Apps to build (each is a separate app with multiple functions)
    function_apps = [
        "dispatcher",
        "persister", 
        "connector",
        "hot-reader",
        "hot-writer",
        "hot-to-cold-mover",
        "cold-to-archive-mover",
        "digital-twin-data-connector",
        "adt-updater",
    ]
    
    for app_name in function_apps:
        app_dir = azure_funcs_dir / app_name
        if app_dir.exists():
            zip_path = build_dir / f"{app_name}.zip"
            _create_azure_function_zip(app_dir, zip_path)
            packages[f"azure_{app_name}"] = zip_path
            logger.info(f"  ✓ Built: {app_name}.zip")
    
    return packages


def _create_lambda_zip(func_dir: Path, shared_dir: Path, output_path: Path) -> None:
    """Create a Lambda deployment ZIP with function code and shared modules."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function files
        for file_path in func_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = file_path.relative_to(func_dir)
                zf.write(file_path, arcname)
        
        # Add shared modules
        if shared_dir.exists():
            for file_path in shared_dir.rglob('*'):
                if file_path.is_file() and '__pycache__' not in str(file_path):
                    arcname = file_path.relative_to(shared_dir)
                    zf.write(file_path, arcname)


def _create_azure_function_zip(app_dir: Path, output_path: Path) -> None:
    """Create an Azure Function App deployment ZIP."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in app_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = file_path.relative_to(app_dir)
                zf.write(file_path, arcname)


def get_lambda_zip_path(terraform_dir: Path, function_name: str) -> str:
    """Get the path to a pre-built Lambda ZIP for Terraform."""
    return str(terraform_dir / BUILD_DIR / "aws" / f"{function_name}.zip")


def get_azure_zip_path(terraform_dir: Path, app_name: str) -> str:
    """Get the path to a pre-built Azure Function ZIP."""
    return str(terraform_dir / BUILD_DIR / "azure" / f"{app_name}.zip")


# ==========================================
# User Package Building (event actions, processors, feedback)
# ==========================================

import hashlib
import json
import datetime


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
    metadata_dir = project_path / ".build" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_path = metadata_dir / f"{function_name}.{provider}.json"
    
    metadata = {
        "function": function_name,
        "provider": provider,
        "zip_hash": code_hash,
        "last_built": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
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
    
    # Build output directory in project
    build_dir = project_path / ".build" / l2_provider
    build_dir.mkdir(parents=True, exist_ok=True)
    
    packages = {}
    
    # Load config files
    events_path = project_path / "config_events.json"
    devices_path = project_path / "config_iot_devices.json"
    
    if not events_path.exists():
        raise ValueError(f"Missing required config: config_events.json")
    if not devices_path.exists():
        raise ValueError(f"Missing required config: config_iot_devices.json")
    
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
        shared_dir = Path(__file__).parent.parent / "aws" / "lambda_functions" / "_shared"
    elif l2_provider == "azure":
        user_funcs_dir = project_path / "azure_functions"
        event_actions_dir = user_funcs_dir / "event_actions"
        processors_dir = user_funcs_dir / "processors"
        feedback_dir = user_funcs_dir / "event-feedback"
        shared_dir = None  # Azure doesn't use shared dir
    else:
        user_funcs_dir = project_path / "cloud_functions"
        event_actions_dir = user_funcs_dir / "event_actions"
        processors_dir = user_funcs_dir / "processors"
        feedback_dir = user_funcs_dir / "event-feedback"
        shared_dir = None
    
    logger.info(f"Building user packages for provider: {l2_provider}")
    
    # 1. Build Event Action packages
    for event in events_config:
        if "action" not in event:
            raise ValueError("Event config entry missing required 'action' field")
        
        action = event["action"]
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
        else:
            _create_azure_function_zip(func_dir, zip_path)
        
        packages[func_name] = zip_path
        
        # Save hash metadata
        _save_user_hash_metadata(project_path, func_name, l2_provider, code_hash)
        
        logger.info(f"  ✓ Built event action: {func_name}.zip")
    
    # 2. Build Processor packages
    processors_seen = set()
    for device in devices_config:
        if "id" not in device:
            raise ValueError("Device config entry missing required 'id' field")
        
        processor_name = device.get("processor", "default_processor")
        
        if processor_name in processors_seen:
            continue
        processors_seen.add(processor_name)
        
        proc_dir = processors_dir / processor_name
        
        if not proc_dir.exists():
            raise ValueError(f"Missing processor code: {processor_name}. Expected: {proc_dir}")
        
        # Compute hash
        code_hash = _compute_directory_hash(proc_dir)
        
        # Build ZIP with processor wrapper for Azure
        zip_path = build_dir / f"processor-{processor_name}.zip"
        
        if l2_provider == "aws":
            _create_lambda_zip(proc_dir, shared_dir, zip_path)
        elif l2_provider == "azure":
            # For Azure, we wrap the processor with the processor_wrapper
            _create_processor_with_wrapper(proc_dir, zip_path)
        else:
            _create_azure_function_zip(proc_dir, zip_path)
        
        packages[f"processor-{processor_name}"] = zip_path
        
        # Save hash metadata
        _save_user_hash_metadata(project_path, f"processor-{processor_name}", l2_provider, code_hash)
        
        logger.info(f"  ✓ Built processor: processor-{processor_name}.zip")
    
    # 3. Build Event-Feedback package
    if feedback_dir.exists():
        code_hash = _compute_directory_hash(feedback_dir)
        
        zip_path = build_dir / "event-feedback.zip"
        if l2_provider == "aws":
            _create_lambda_zip(feedback_dir, shared_dir, zip_path)
        else:
            _create_azure_function_zip(feedback_dir, zip_path)
        
        packages["event-feedback"] = zip_path
        
        # Save hash metadata
        _save_user_hash_metadata(project_path, "event-feedback", l2_provider, code_hash)
        
        logger.info(f"  ✓ Built event-feedback.zip")
    
    logger.info(f"✓ Built {len(packages)} user packages")
    return packages


def _create_processor_with_wrapper(proc_dir: Path, output_path: Path) -> None:
    """
    Create a processor ZIP with the Azure processor wrapper.
    
    For Azure, processors need to be wrapped with function_app.py
    from the processor_wrapper directory.
    
    Args:
        proc_dir: Path to processor code directory
        output_path: Path to output ZIP file
    """
    # Get processor wrapper directory
    wrapper_dir = Path(__file__).parent.parent / "azure" / "azure_functions" / "processor_wrapper"
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add wrapper files (function_app.py, host.json, requirements.txt)
        if wrapper_dir.exists():
            for file_path in wrapper_dir.rglob('*'):
                if file_path.is_file() and '__pycache__' not in str(file_path):
                    arcname = file_path.relative_to(wrapper_dir)
                    zf.write(file_path, arcname)
        
        # Add processor code under 'processor/' subdirectory
        for file_path in proc_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = Path("processor") / file_path.relative_to(proc_dir)
                zf.write(file_path, arcname)


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
