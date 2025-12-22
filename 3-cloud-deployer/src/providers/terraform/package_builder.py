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
from typing import Dict, List, Optional, Any

from src.function_registry import get_functions_for_provider_build
from src.providers.azure.azure_bundler import (
    bundle_l0_functions as _azure_bundle_l0,
    bundle_l1_functions as _azure_bundle_l1,
    bundle_l2_functions as _azure_bundle_l2,
    bundle_l3_functions as _azure_bundle_l3,
    _merge_function_files,
    _convert_functionapp_to_blueprint,
    _convert_require_env_to_lazy,
    _add_shared_files,
)

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
    # Convert to Path if strings are passed
    terraform_dir = Path(terraform_dir) if isinstance(terraform_dir, str) else terraform_dir
    project_path = Path(project_path) if isinstance(project_path, str) else project_path
    
    build_dir = terraform_dir / BUILD_DIR
    build_dir.mkdir(parents=True, exist_ok=True)
    
    packages = {}
    
    # Build AWS Lambda packages
    aws_packages = build_aws_lambda_packages(terraform_dir, project_path, providers_config)
    packages.update(aws_packages)
    
    # Build Azure Function packages
    azure_packages = build_azure_function_packages(terraform_dir, project_path, providers_config)
    packages.update(azure_packages)
    
    # Build GCP Cloud Function packages
    gcp_packages = build_gcp_cloud_function_packages(terraform_dir, project_path, providers_config)
    packages.update(gcp_packages)
    
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
    build_dir = project_path / ".build" / "aws"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Lambda functions directory
    lambda_dir = Path(__file__).parent.parent / "aws" / "lambda_functions"
    shared_dir = lambda_dir / "_shared"
    
    packages = {}
    
    # Get functions from registry (replaces hardcoded boundary logic)
    functions_to_build = get_functions_for_provider_build("aws", providers_config)
    
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
    
    build_dir = project_path / ".build" / "azure"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Azure functions directory
    azure_funcs_dir = Path(__file__).parent.parent / "azure" / "azure_functions"
    
    packages = {}
    
    # Get functions from registry
    functions_to_build = get_functions_for_provider_build("azure", providers_config)
    
    for func_name in functions_to_build:
        app_dir = azure_funcs_dir / func_name
        if app_dir.exists():
            zip_path = build_dir / f"{func_name}.zip"
            _create_azure_function_zip(app_dir, zip_path)
            packages[f"azure_{func_name}"] = zip_path
            logger.info(f"  ✓ Built: {func_name}.zip")
    
    return packages


def build_azure_l0_bundle(project_path: Path, providers_config: dict) -> Optional[Path]:
    """Build L0 Glue functions ZIP. Returns path or None."""
    zip_bytes, func_list = _azure_bundle_l0(str(project_path), providers_config)
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / "l0_functions.zip"
    output.write_bytes(zip_bytes)
    return output


def build_azure_l1_bundle(project_path: Path) -> Optional[Path]:
    """Build L1 Dispatcher functions ZIP. Returns path or None."""
    zip_bytes = _azure_bundle_l1(str(project_path))
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / "l1_functions.zip"
    output.write_bytes(zip_bytes)
    return output


def build_azure_l2_bundle(project_path: Path) -> Optional[Path]:
    """Build L2 Processor functions ZIP. Returns path or None."""
    zip_bytes = _azure_bundle_l2(str(project_path))
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / "l2_functions.zip"
    output.write_bytes(zip_bytes)
    return output


def build_azure_l3_bundle(project_path: Path) -> Optional[Path]:
    """Build L3 Storage functions ZIP. Returns path or None."""
    zip_bytes = _azure_bundle_l3(str(project_path))
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / "l3_functions.zip"
    output.write_bytes(zip_bytes)
    return output


def _discover_azure_user_functions(user_funcs_dir: Path, optimization_flags: dict = None) -> List[tuple]:
    """
    Discover user functions using function_app.py pattern.
    
    Returns list of (func_type, folder_path) tuples.
    
    Conditional inclusion based on optimization flags:
    - event-feedback: included if returnFeedbackToDevice=true
    - event_actions: included if useEventChecking=true
    - processors: always included
    """
    result = []
    flags = optimization_flags or {}
    
    # event-feedback (if returnFeedbackToDevice)
    if flags.get("returnFeedbackToDevice", True):
        feedback_dir = user_funcs_dir / "event-feedback"
        if feedback_dir.exists() and (feedback_dir / "function_app.py").exists():
            result.append(('event_feedback', feedback_dir))
    
    # processors (always included)
    processors_dir = user_funcs_dir / "processors"
    if processors_dir.exists():
        for subfolder in processors_dir.iterdir():
            if subfolder.is_dir() and (subfolder / "function_app.py").exists():
                result.append(('processor', subfolder))
    
    # event_actions (if useEventChecking)
    if flags.get("useEventChecking", True):
        actions_dir = user_funcs_dir / "event_actions"
        if actions_dir.exists():
            for subfolder in actions_dir.iterdir():
                if subfolder.is_dir() and (subfolder / "function_app.py").exists():
                    result.append(('event_action', subfolder))
    
    return result


def _add_azure_function_app_directly(
    zf: zipfile.ZipFile, 
    user_dir: Path, 
    module_name: str
) -> None:
    """
    Add user's function_app.py directly (converted to Blueprint).
    
    Used for event_actions that provide complete function_app.py files.
    """
    # 1. Add __init__.py
    zf.writestr(f"{module_name}/__init__.py", "# Auto-generated\n")
    
    # 2. Add user's function_app.py (converted to Blueprint)
    func_app = user_dir / "function_app.py"
    if func_app.exists():
        content = func_app.read_text(encoding="utf-8")
        content = _convert_functionapp_to_blueprint(content)
        content = _convert_require_env_to_lazy(content)
        zf.writestr(f"{module_name}/function_app.py", content)


def _generate_main_function_app(modules: list) -> str:
    """Generate main function_app.py that registers all Blueprints."""
    imports = []
    registers = []
    
    for module in modules:
        bp_alias = f"{module}_bp"
        imports.append(f"from {module}.function_app import bp as {bp_alias}")
        registers.append(f"app.register_functions({bp_alias})")
    
    return f'''"""
Auto-generated main function_app.py for Azure Functions Bundle.
Functions included: {', '.join(modules)}
"""
import azure.functions as func

{chr(10).join(imports)}

app = func.FunctionApp()
{chr(10).join(registers)}
'''


def build_azure_user_bundle(project_path: Path, providers_config: dict, optimization_flags: dict = None) -> Optional[Path]:
    """
    Build combined Azure user functions ZIP.
    
    Supports both process.py + wrapper and direct function_app.py patterns.
    Returns path to ZIP or None if no user functions found.
    """
    if providers_config.get("layer_2_provider") != "azure":
        return None
    
    user_funcs_dir = project_path / "azure_functions"
    if not user_funcs_dir.exists():
        logger.info("  No azure_functions directory, skipping user bundle")
        return None
    
    # Load flags if not provided (for standalone use)
    if optimization_flags is None:
        from src.core.config_loader import load_optimization_flags
        optimization_flags = load_optimization_flags(project_path)
    
    discovered = _discover_azure_user_functions(user_funcs_dir, optimization_flags)
    
    if not discovered:
        logger.info("  No user functions found")
        return None
    
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_dir / "user_functions.zip"
    
    azure_funcs_base = Path(__file__).parent.parent / "azure" / "azure_functions"
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add shared files (host.json, requirements.txt base, _shared/)
        _add_shared_files(zf, azure_funcs_base)
        
        all_modules = []
        
        # Add all user functions (all use function_app.py pattern now)
        for func_type, user_dir in discovered:
            module_name = user_dir.name.replace("-", "_")
            _add_azure_function_app_directly(zf, user_dir, module_name)
            all_modules.append(module_name)
        
        # Generate main function_app.py
        if all_modules:
            main_content = _generate_main_function_app(all_modules)
            zf.writestr("function_app.py", main_content)
    
    logger.info(f"  ✓ Built user bundle: {len(all_modules)} functions")
    return output_path



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
                    arcname = f"_shared/{file_path.relative_to(shared_dir)}"
                    zf.write(file_path, arcname)


def _create_azure_function_zip(app_dir: Path, output_path: Path) -> None:
    """Create an Azure Function App deployment ZIP."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in app_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = file_path.relative_to(app_dir)
                zf.write(file_path, arcname)


def get_lambda_zip_path(project_path: Path, function_name: str) -> str:
    """Get the path to a Lambda ZIP file (for Terraform variable references)."""
    return str(project_path / ".build" / "aws" / f"{function_name}.zip")


def get_azure_zip_path(project_path: Path, app_name: str) -> str:
    """Get the path to an Azure Function ZIP file."""
    return str(project_path / ".build" / "azure" / f"{app_name}.zip")


def build_gcp_cloud_function_packages(
    terraform_dir: Path,
    project_path: Path,
    providers_config: dict
) -> Dict[str, Path]:
    """
    Build GCP Cloud Function packages to .build/gcp/*.zip.
    Only builds functions that are needed based on provider config.
    
    Returns:
        Dict mapping function names to ZIP paths
    """
    # Check if any layer uses GCP
    gcp_layers = ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider",
                  "layer_3_cold_provider", "layer_3_archive_provider"]
    has_gcp = any(providers_config.get(layer) == "google" for layer in gcp_layers)
    
    if not has_gcp:
        logger.info("  No GCP layers configured, skipping Cloud Function package build")
        return {}
    
    # Build to project_path/.build/gcp/ (matches Terraform's expected paths)
    build_dir = project_path / ".build" / "gcp"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    packages = {}
    
    # Get GCP Cloud Functions source directory (from deployer src)
    gcp_funcs_dir = Path(__file__).parent.parent / "gcp" / "cloud_functions"
    shared_dir = gcp_funcs_dir / "_shared"
    
    # Get functions from registry (replaces hardcoded boundary logic)
    functions_to_build = get_functions_for_provider_build("gcp", providers_config)
    
    # Copy source files to project_path/cloud_functions/ for Terraform filemd5() access
    cloud_functions_dir = project_path / "cloud_functions"
    cloud_functions_dir.mkdir(parents=True, exist_ok=True)
    
    # Build each function
    for func_name in functions_to_build:
        func_dir = gcp_funcs_dir / func_name
        if func_dir.exists():
            # Copy source to project path for Terraform filemd5()
            dest_dir = cloud_functions_dir / func_name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(func_dir, dest_dir)
            
            zip_path = build_dir / f"{func_name}.zip"
            # Processor gets user code merged
            if func_name == "processor_wrapper":
                _create_gcp_function_zip(func_dir, shared_dir, zip_path, project_path)
            else:
                _create_gcp_function_zip(func_dir, shared_dir, zip_path)
            packages[f"gcp_{func_name}"] = zip_path
            logger.info(f"  ✓ Built GCP: {func_name}.zip")
        else:
            logger.warning(f"  ⚠ GCP function dir not found: {func_dir}")
    
    # Note: User functions (processors, event_actions, event_feedback) are built separately
    # via build_user_packages() which creates individual ZIPs per function (like AWS)
    # This matches the GCP Cloud Functions architecture where each function is deployed separately
    
    if not functions_to_build:
        logger.info("  No GCP Cloud Functions needed for this configuration")
    
    return packages


def _create_gcp_function_zip(
    func_dir: Path, 
    shared_dir: Path, 
    output_path: Path,
    project_path: Optional[Path] = None
) -> None:
    """
    Create a GCP Cloud Function deployment ZIP with shared modules.
    
    Args:
        func_dir: Path to function source directory
        shared_dir: Path to _shared modules directory
        output_path: Path to output ZIP file
        project_path: Optional project path for processor user code merge
    """
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function code
        for file_path in func_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = file_path.relative_to(func_dir)
                zf.write(file_path, arcname)
        
        # Add shared modules under _shared/
        if shared_dir and shared_dir.exists():
            for file_path in shared_dir.rglob('*'):
                if file_path.is_file() and '__pycache__' not in str(file_path):
                    arcname = Path("_shared") / file_path.relative_to(shared_dir)
                    zf.write(file_path, arcname)
        
        # Add requirements.txt if not present
        if not (func_dir / "requirements.txt").exists():
            requirements = "functions-framework\ngoogle-cloud-firestore\ngoogle-cloud-storage\ngoogle-cloud-pubsub\n"
            zf.writestr("requirements.txt", requirements)


def _create_gcp_processor_zip(
    base_dir: Path,
    user_dir: Path,
    shared_dir: Path,
    output_path: Path
) -> None:
    """
    Create a GCP Processor ZIP by wrapping user code with default-processor base.
    
    Args:
        base_dir: Path to default-processor base directory (src/providers/gcp/cloud_functions/default-processor)
        user_dir: Path to specific user processor directory (containing process.py)
        shared_dir: Path to _shared modules directory
        output_path: Path to output ZIP file
    """
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Add base processor code (main.py, etc.)
        if base_dir.exists():
            for file_path in base_dir.rglob('*'):
                if file_path.is_file() and '__pycache__' not in str(file_path):
                    arcname = file_path.relative_to(base_dir)
                    zf.write(file_path, arcname)
        
        # 2. Add shared modules under _shared/
        if shared_dir and shared_dir.exists():
            for file_path in shared_dir.rglob('*'):
                if file_path.is_file() and '__pycache__' not in str(file_path):
                    arcname = Path("_shared") / file_path.relative_to(shared_dir)
                    zf.write(file_path, arcname)
        
        # 3. Add/Overwrite with user processor code (process.py)
        # Skip requirements.txt - will merge later
        if user_dir.exists():
            for file_path in user_dir.rglob('*.py'):
                if '__pycache__' not in str(file_path):
                    arcname = file_path.relative_to(user_dir)
                    zf.write(file_path, arcname)
            logger.info(f"    → Merged user processor code from: {user_dir}")
        
        # 4. Merge requirements.txt (wrapper + user, no fallback)
        wrapper_req = base_dir / "requirements.txt"
        user_req = user_dir / "requirements.txt"
        merged = _merge_requirements(wrapper_req, user_req)
        if merged:
            zf.writestr("requirements.txt", merged)
        



def get_gcp_zip_path(project_path: Path, function_name: str) -> str:
    """Get the path to a GCP Cloud Function ZIP file (for Terraform variable references)."""
    return str(project_path / ".build" / "gcp" / f"{function_name}.zip")


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
    else:  # google
        user_funcs_dir = project_path / "cloud_functions"
        event_actions_dir = user_funcs_dir / "event_actions"
        processors_dir = user_funcs_dir / "processors"
        feedback_dir = user_funcs_dir / "event-feedback"
        shared_dir = Path(__file__).parent.parent / "gcp" / "cloud_functions" / "_shared"
    
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
        elif l2_provider == "google":
            _create_gcp_function_zip(func_dir, shared_dir, zip_path)
        else:  # azure
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
            # User provides standalone lambda_function.py
            _create_lambda_zip(proc_dir, shared_dir, zip_path)
            packages[f"processor-{processor_name}"] = zip_path
            _save_user_hash_metadata(project_path, f"processor-{processor_name}", l2_provider, code_hash)
            logger.info(f"  ✓ Built processor: processor-{processor_name}.zip")
        elif l2_provider == "azure":
            # Azure user functions are bundled together separately via build_azure_user_bundle()
            logger.info(f"  → Skipping individual processor ZIP for Azure (bundled together)")
        else:  # google
            # User provides standalone main.py - just copy it
            _create_gcp_function_zip(proc_dir, shared_dir, zip_path)
            packages[f"processor-{processor_name}"] = zip_path
            _save_user_hash_metadata(project_path, f"processor-{processor_name}", l2_provider, code_hash)
            logger.info(f"  ✓ Built processor: processor-{processor_name}.zip")
    
    # 3. Build Event-Feedback package (WITH WRAPPER MERGING)
    if feedback_dir.exists():
        code_hash = _compute_directory_hash(feedback_dir)
        zip_path = build_dir / "event-feedback.zip"
        
        # User provides standalone serverless function
        if l2_provider == "aws":
            _create_lambda_zip(feedback_dir, shared_dir, zip_path)
            packages["event-feedback"] = zip_path
            _save_user_hash_metadata(project_path, "event-feedback", l2_provider, code_hash)
            logger.info(f"  ✓ Built event-feedback.zip")
        elif l2_provider == "azure":
            # Azure bundles all user functions together via build_azure_user_bundle()
            logger.info(f"  → Skipping individual event-feedback ZIP for Azure (bundled together)")
        else:  # google
            _create_gcp_function_zip(feedback_dir, shared_dir, zip_path)
            packages["event-feedback"] = zip_path
            _save_user_hash_metadata(project_path, "event-feedback", l2_provider, code_hash)
            logger.info(f"  ✓ Built event-feedback.zip")
    
    logger.info(f"✓ Built {len(packages)} user packages")
    return packages


# Obsolete function removed - user functions now use HTTP call pattern



# Obsolete function removed - AWS processors now use standalone lambda_function.py




def _merge_requirements(wrapper_req: Path, user_req: Path) -> str:
    """Merge wrapper and user requirements.txt files."""
    lines = set()
    
    if wrapper_req.exists():
        for line in wrapper_req.read_text().strip().splitlines():
            if line.strip() and not line.startswith('#'):
                lines.add(line.strip())
    
    if user_req.exists():
        for line in user_req.read_text().strip().splitlines():
            if line.strip() and not line.startswith('#'):
                lines.add(line.strip())
    
    return '\n'.join(sorted(lines)) if lines else ''


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
        'aws': Path(__file__).parent.parent / 'aws' / 'lambda_functions' / 'event_feedback_wrapper',
        'azure': Path(__file__).parent.parent / 'azure' / 'azure_functions' / 'event_feedback_wrapper',
        'google': Path(__file__).parent.parent / 'gcp' / 'cloud_functions' / 'event_feedback_wrapper',
    }
    
    wrapper_dir = provider_map.get(provider)
    if not wrapper_dir or not wrapper_dir.exists():
        logger.warning(f"No event_feedback_wrapper found for {provider}, bundling raw files")
        # Fallback to raw bundling
        if provider == 'aws':
            shared_dir = Path(__file__).parent.parent / 'aws' / 'lambda_functions' / '_shared'
            _create_lambda_zip(feedback_dir, shared_dir, output_path)
        elif provider == 'google':
            shared_dir = Path(__file__).parent.parent / 'gcp' / 'cloud_functions' / '_shared'
            _create_gcp_function_zip(feedback_dir, shared_dir, output_path)
        else:
            _create_azure_function_zip(feedback_dir, output_path)
        return
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Add wrapper files (lambda_function.py/function_app.py/main.py, etc.)
        for file_path in wrapper_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = file_path.relative_to(wrapper_dir)
                zf.write(file_path, arcname)
        
        # 2. Add user's process.py at root level (required for 'from process import process')
        # Skip requirements.txt - will merge later
        for file_path in feedback_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                if file_path.name == 'requirements.txt':
                    continue  # Skip - will merge
                arcname = file_path.relative_to(feedback_dir)
                zf.write(file_path, arcname)
        
        # 3. Add shared modules for AWS/GCP
        if provider == 'aws':
            shared_dir = Path(__file__).parent.parent / 'aws' / 'lambda_functions' / '_shared'
            if shared_dir.exists():
                for file_path in shared_dir.rglob('*'):
                    if file_path.is_file() and '__pycache__' not in str(file_path):
                        arcname = f"_shared/{file_path.relative_to(shared_dir)}"
                        zf.write(file_path, arcname)
        elif provider == 'google':
            shared_dir = Path(__file__).parent.parent / 'gcp' / 'cloud_functions' / '_shared'
            if shared_dir.exists():
                for file_path in shared_dir.rglob('*'):
                    if file_path.is_file() and '__pycache__' not in str(file_path):
                        arcname = f"_shared/{file_path.relative_to(shared_dir)}"
                        zf.write(file_path, arcname)
        
        # 4. Merge requirements.txt
        wrapper_req = wrapper_dir / "requirements.txt"
        user_req = feedback_dir / "requirements.txt"
        merged = _merge_requirements(wrapper_req, user_req)
        if merged:
            zf.writestr("requirements.txt", merged)
    
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


def build_combined_user_package(
    project_path: Path,
    providers_config: dict
) -> Optional[Path]:
    """
    Build a SINGLE ZIP containing ALL user functions for Azure.
    
    This creates a combined ZIP with all event actions, processors, and
    feedback functions for deployment to a single Azure Function App.
    
    Args:
        project_path: Path to project upload directory (upload/<project>/)
        providers_config: Layer provider configuration
        
    Returns:
        Path to combined ZIP file, or None if no user functions
        
    Raises:
        ValueError: If required configs are missing
    """
    if not project_path.exists():
        raise ValueError(f"Project path not found: {project_path}")
    
    l2_provider = providers_config.get("layer_2_provider", "").lower()
    
    if l2_provider != "azure":
        logger.info("  L2 is not Azure, skipping combined user package")
        return None
    
    # Build output directory
    build_dir = project_path / ".build" / "azure"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Load config files
    events_path = project_path / "config_events.json"
    devices_path = project_path / "config_iot_devices.json"
    optimization_path = project_path / "config_optimization.json"
    
    if not devices_path.exists():
        logger.info("  No config_iot_devices.json, skipping user package")
        return None
    
    with open(devices_path, 'r') as f:
        devices_config = json.load(f)
    
    # Load optimization config to check which features are enabled
    optimization_config = {}
    if optimization_path.exists():
        with open(optimization_path, 'r') as f:
            opt_data = json.load(f)
            optimization_config = opt_data.get("result", {}).get("inputParamsUsed", {})
    
    # Feature flags from config_optimization.json
    use_event_checking = optimization_config.get("useEventChecking", True)
    return_feedback = optimization_config.get("returnFeedbackToDevice", False)
    
    # Load events config if event checking is enabled
    events_config = []
    if use_event_checking and events_path.exists():
        with open(events_path, 'r') as f:
            events_config = json.load(f)
    
    # Source directories
    user_funcs_dir = project_path / "azure_functions"
    event_actions_dir = user_funcs_dir / "event_actions"
    processors_dir = user_funcs_dir / "processors"
    feedback_dir = user_funcs_dir / "event-feedback"
    
    # Azure shared files
    azure_funcs_base = Path(__file__).parent.parent / "azure" / "azure_functions"
    
    combined_zip_path = build_dir / "user_functions_combined.zip"
    combined_hash = hashlib.sha256()
    functions_added = []
    
    logger.info("  Building combined Azure user functions package...")
    
    with zipfile.ZipFile(combined_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add host.json
        host_json = azure_funcs_base / "host.json"
        if host_json.exists():
            zf.write(host_json, "host.json")
        else:
            # Create default host.json
            zf.writestr("host.json", json.dumps({
                "version": "2.0",
                "extensionBundle": {
                    "id": "Microsoft.Azure.Functions.ExtensionBundle",
                    "version": "[4.*, 5.0.0)"
                }
            }, indent=2))
        
        # Add requirements.txt
        req_path = azure_funcs_base / "requirements.txt"
        if req_path.exists():
            zf.write(req_path, "requirements.txt")
        else:
            zf.writestr("requirements.txt", "azure-functions\n")
        
        # 1. Add Event Actions
        for event in events_config:
            action = event.get("action", {})
            func_name = action.get("functionName")
            if not func_name:
                continue
            
            func_dir = event_actions_dir / func_name
            if func_dir.exists():
                _add_function_to_combined_zip(zf, func_dir, func_name, combined_hash)
                functions_added.append(f"event-action:{func_name}")
        
        # 2. Add Processors (with wrapper)
        processors_seen = set()
        processor_wrapper_dir = azure_funcs_base / "processor_wrapper"
        
        for device in devices_config:
            processor_name = device.get("processor", "default_processor")
            if processor_name in processors_seen:
                continue
            processors_seen.add(processor_name)
            
            proc_dir = processors_dir / processor_name
            if proc_dir.exists():
                _add_processor_to_combined_zip(zf, proc_dir, processor_name, 
                                               processor_wrapper_dir, combined_hash)
                functions_added.append(f"processor:{processor_name}")
        
        # 3. Add Event Feedback (only if returnFeedbackToDevice is enabled)
        if return_feedback and feedback_dir.exists():
            _add_function_to_combined_zip(zf, feedback_dir, "event-feedback", combined_hash)
            functions_added.append("event-feedback")
    
    if not functions_added:
        logger.info("  No user functions found, removing empty ZIP")
        combined_zip_path.unlink(missing_ok=True)
        return None
    
    # Save combined hash
    combined_hash_str = f"sha256:{combined_hash.hexdigest()}"
    _save_user_hash_metadata(project_path, "user_functions_combined", "azure", combined_hash_str)
    
    logger.info(f"  ✓ Built combined user package with {len(functions_added)} functions")
    return combined_zip_path


def _add_function_to_combined_zip(
    zf: zipfile.ZipFile, 
    func_dir: Path, 
    func_name: str,
    hasher: Any
) -> None:
    """Add a function directory to the combined ZIP under its own folder."""
    for file_path in func_dir.rglob('*'):
        if file_path.is_file() and '__pycache__' not in str(file_path):
            arcname = f"{func_name}/{file_path.relative_to(func_dir)}"
            zf.write(file_path, arcname)
            # Update hash
            hasher.update(arcname.encode('utf-8'))
            with open(file_path, 'rb') as f:
                hasher.update(f.read())


def _add_processor_to_combined_zip(
    zf: zipfile.ZipFile,
    proc_dir: Path,
    proc_name: str,
    wrapper_dir: Path,
    hasher: Any
) -> None:
    """Add a processor with wrapper to the combined ZIP."""
    func_name = f"processor-{proc_name}"
    
    # Add wrapper files to processor folder
    if wrapper_dir.exists():
        for file_path in wrapper_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = f"{func_name}/{file_path.relative_to(wrapper_dir)}"
                zf.write(file_path, arcname)
                hasher.update(arcname.encode('utf-8'))
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
    
    # Add processor user code at same level as function_app.py
    # The wrapper does "from process import process" so process.py must be at root
    for file_path in proc_dir.rglob('*'):
        if file_path.is_file() and '__pycache__' not in str(file_path):
            # Put at root level (same as function_app.py) for import to work
            arcname = f"{func_name}/{file_path.relative_to(proc_dir)}"
            zf.write(file_path, arcname)
            hasher.update(arcname.encode('utf-8'))
            with open(file_path, 'rb') as f:
                hasher.update(f.read())


def check_user_functions_changed(project_path: Path) -> bool:
    """
    Check if any user function code has changed since last build.
    
    Compares current combined hash with saved metadata.
    
    Args:
        project_path: Path to project upload directory
        
    Returns:
        True if any function changed or no previous build exists
    """
    metadata_path = project_path / ".build" / "metadata" / "user_functions_combined.azure.json"
    
    if not metadata_path.exists():
        logger.info("  No previous user functions build found")
        return True
    
    # We'd need to rebuild to get current hash, so just check timestamp
    # For full accuracy, could compare individual function hashes
    # For now, always return True to rebuild (safe but slower)
    return True


def get_combined_user_package_path(project_path: Path) -> Path:
    """Get path to the combined user functions ZIP."""
    return project_path / ".build" / "azure" / "user_functions_combined.zip"

