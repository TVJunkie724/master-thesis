"""Azure Function package and aggregate user-bundle construction."""

import io
import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from src.function_registry import get_functions_for_provider_build
from src.function_metadata import (
    hash_bytes,
    hash_directory,
    reconcile_function_metadata,
    record_function_build,
)
from src.core.deterministic_zip import (
    atomic_write_bytes,
    atomic_zip_archive,
    write_zip_bytes,
    write_zip_file,
)
from src.providers.azure.azure_bundler import (
    _add_shared_files,
    _convert_functionapp_to_blueprint,
    _convert_require_env_to_lazy,
    bundle_l0_functions as _azure_bundle_l0,
    bundle_l1_functions as _azure_bundle_l1,
    bundle_l2_functions as _azure_bundle_l2,
    bundle_l3_functions as _azure_bundle_l3,
)
from src.providers.terraform.package_builders.common import (
    _clean_old_versioned_zips,
    _compute_content_hash,
    _should_include_file,
)

logger = logging.getLogger(__name__)
PROVIDERS_ROOT = Path(__file__).resolve().parents[2]

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
    azure_funcs_dir = PROVIDERS_ROOT / "azure" / "azure_functions"
    
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
    """Build L0 Glue functions ZIP. Returns path or None.
    
    Uses content-hash-based filename to force Azure redeployment when content changes.
    """
    zip_bytes, func_list = _azure_bundle_l0(str(project_path), providers_config)
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Use content hash in filename to force Azure redeployment
    content_hash = _compute_content_hash(zip_bytes)
    _clean_old_versioned_zips(build_dir, "l0_functions")
    output = build_dir / f"l0_functions_{content_hash}.zip"
    atomic_write_bytes(output, zip_bytes)
    return output



def build_azure_l1_bundle(project_path: Path, providers_config: dict = None) -> Optional[Path]:
    """Build L1 Dispatcher functions ZIP. Returns path or None.
    
    Uses content-hash-based filename to force Azure redeployment when content changes.
    
    Args:
        project_path: Path to project directory
        providers_config: Optional provider config for conditional function inclusion.
                         If L1 and L2 use same provider, connector is excluded.
    """
    zip_bytes = _azure_bundle_l1(str(project_path), providers_config)
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    content_hash = _compute_content_hash(zip_bytes)
    _clean_old_versioned_zips(build_dir, "l1_functions")
    output = build_dir / f"l1_functions_{content_hash}.zip"
    atomic_write_bytes(output, zip_bytes)
    return output


def build_azure_l2_bundle(project_path: Path) -> Optional[Path]:
    """Build L2 Processor functions ZIP. Returns path or None.
    
    Uses content-hash-based filename to force Azure redeployment when content changes.
    """
    zip_bytes = _azure_bundle_l2(str(project_path))
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    content_hash = _compute_content_hash(zip_bytes)
    _clean_old_versioned_zips(build_dir, "l2_functions")
    output = build_dir / f"l2_functions_{content_hash}.zip"
    atomic_write_bytes(output, zip_bytes)
    return output


def build_azure_l3_bundle(project_path: Path) -> Optional[Path]:
    """Build L3 Storage functions ZIP. Returns path or None.
    
    Uses content-hash-based filename to force Azure redeployment when content changes.
    """
    zip_bytes = _azure_bundle_l3(str(project_path))
    if not zip_bytes:
        return None
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    content_hash = _compute_content_hash(zip_bytes)
    _clean_old_versioned_zips(build_dir, "l3_functions")
    output = build_dir / f"l3_functions_{content_hash}.zip"
    atomic_write_bytes(output, zip_bytes)
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
        for subfolder in sorted(processors_dir.iterdir()):
            if subfolder.is_dir() and (subfolder / "function_app.py").exists():
                result.append(('processor', subfolder))
    
    # event_actions (if useEventChecking)
    if flags.get("useEventChecking", True):
        actions_dir = user_funcs_dir / "event_actions"
        if actions_dir.exists():
            for subfolder in sorted(actions_dir.iterdir()):
                if subfolder.is_dir() and (subfolder / "function_app.py").exists():
                    result.append(('event_action', subfolder))
    
    return result


def _add_azure_function_app_directly(
    zf: zipfile.ZipFile, 
    user_dir: Path, 
    module_name: str,
    digital_twin_name: Optional[str] = None,
    device_id: Optional[str] = None
) -> None:
    """
    Add user's function_app.py directly (converted to Blueprint).
    
    Used for event_actions that provide complete function_app.py files.
    Applies renaming if digital_twin_name and device_id are provided (for processors).
    """
    # 1. Add __init__.py
    write_zip_bytes(zf, f"{module_name}/__init__.py", "# Auto-generated\n")
    
    # 2. Add user's function_app.py (converted to Blueprint)
    func_app = user_dir / "function_app.py"
    if func_app.exists():
        content = func_app.read_text(encoding="utf-8")
        
        # Apply renaming for processors (if twin name and device ID provided)
        if digital_twin_name and device_id:
            content = _rewrite_azure_function_names(content, digital_twin_name, device_id)
            
        content = _convert_functionapp_to_blueprint(content)
        content = _convert_require_env_to_lazy(content)
        write_zip_bytes(zf, f"{module_name}/function_app.py", content)


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


def _rewrite_azure_function_names(content: str, digital_twin_name: str, device_id: str) -> str:
    """
    Rewrite Azure function names and routes to match {twin}-{device_id}-processor pattern.
    
    Args:
        content: Original function_app.py content
        digital_twin_name: Name of the digital twin
        device_id: Device ID (from folder name)
        
    Returns:
        Modified content with updated function names and routes
    """
    expected_name = f"{digital_twin_name}-{device_id}-processor"
    
    # Pattern 1: @bp.route(route="...", ...)
    content = re.sub(
        r'@bp\.route\(route="[^"]*"',
        f'@bp.route(route="{expected_name}"',
        content
    )
    
    # Pattern 2: @bp.function_name("...")
    content = re.sub(
        r'@bp\.function_name\("[^"]*"\)',
        f'@bp.function_name("{expected_name}")',
        content
    )
    
    return content


# NOTE: GCP and AWS renaming functions removed - Terraform handles function names,
# not the Python code. GCP uses entry_point="main", AWS uses handler="lambda_function.lambda_handler".
# Only Azure needs code renaming due to decorator-based function naming.


def build_azure_user_bundle(project_path: Path, providers_config: dict, optimization_flags: dict = None) -> Optional[Path]:
    """
    Build combined Azure user functions ZIP.
    
    Supports both process.py + wrapper and direct function_app.py patterns.
    Returns path to ZIP or None if no user functions found.
    
    Uses content-hash-based filename to force Azure redeployment when content changes.
    """
    if providers_config.get("layer_2_provider") != "azure":
        return None
    
    user_funcs_dir = project_path / "azure_functions"
    if not user_funcs_dir.exists():
        reconcile_function_metadata(project_path, "azure", set())
        logger.info("  No azure_functions directory, skipping user bundle")
        return None
    
    # Load flags if not provided (for standalone use)
    if optimization_flags is None:
        from src.core.config_loader import load_optimization_flags
        optimization_flags = load_optimization_flags(project_path)
    
    discovered = _discover_azure_user_functions(user_funcs_dir, optimization_flags)
    
    if not discovered:
        reconcile_function_metadata(project_path, "azure", set())
        logger.info("  No user functions found")
        return None
    
    build_dir = project_path / ".terraform_zips"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    azure_funcs_base = PROVIDERS_ROOT / "azure" / "azure_functions"
    
    # Load digital_twin_name for processor renaming
    config_file = project_path / "config.json"
    digital_twin_name = ""
    if config_file.exists():
        config_data = json.loads(config_file.read_text())
        digital_twin_name = config_data.get("digital_twin_name", "")
    
    # Build ZIP in memory first to compute hash
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add shared files (host.json, requirements.txt base, _shared/)
        _add_shared_files(zf, azure_funcs_base)
        
        all_modules = []
        
        # Add all user functions (all use function_app.py pattern now)
        for func_type, user_dir in discovered:
            module_name = user_dir.name.replace("-", "_")
            
            # Extract device_id for processors to enable renaming
            device_id = None
            if func_type == 'processor':
                device_id = user_dir.name
                
            _add_azure_function_app_directly(
                zf, 
                user_dir, 
                module_name,
                digital_twin_name=digital_twin_name,
                device_id=device_id
            )
            all_modules.append(module_name)
        
        # Generate main function_app.py
        if all_modules:
            main_content = _generate_main_function_app(all_modules)
            write_zip_bytes(zf, "function_app.py", main_content)
    
    # Write with hash-based filename
    zip_bytes = zip_buffer.getvalue()
    content_hash = _compute_content_hash(zip_bytes)
    _clean_old_versioned_zips(build_dir, "user_functions")
    output_path = build_dir / f"user_functions_{content_hash}.zip"
    atomic_write_bytes(output_path, zip_bytes)

    artifact_hash = hash_bytes(zip_bytes)
    active_functions = set()
    for function_type, user_dir in discovered:
        if function_type == "processor":
            function_name = f"processor-{user_dir.name}"
        elif function_type == "event_feedback":
            function_name = "event-feedback"
        else:
            function_name = user_dir.name
        record_function_build(
            project_path,
            function_name,
            "azure",
            hash_directory(user_dir),
            artifact_hash,
        )
        active_functions.add(function_name)
    reconcile_function_metadata(project_path, "azure", active_functions)
    
    logger.info(f"  ✓ Built user bundle: {len(all_modules)} functions")
    return output_path






def _create_azure_function_zip(app_dir: Path, output_path: Path) -> None:
    """Create an Azure Function App deployment ZIP."""
    with atomic_zip_archive(output_path) as zf:
        for file_path in sorted(app_dir.rglob('*')):
            if file_path.is_file() and _should_include_file(file_path):
                arcname = file_path.relative_to(app_dir)
                write_zip_file(zf, file_path, arcname)



def get_azure_zip_path(project_path: Path, app_name: str) -> str:
    """Get the path to an Azure Function ZIP file."""
    return str(project_path / ".build" / "azure" / f"{app_name}.zip")
