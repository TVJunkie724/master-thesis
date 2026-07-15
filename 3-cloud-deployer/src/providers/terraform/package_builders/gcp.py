"""GCP Cloud Function package construction for Terraform deployments."""

import logging
import shutil
from pathlib import Path
from typing import Dict, Optional

from src.core.config_loader import load_optimization_flags as _load_optimization_flags
from src.core.deterministic_zip import atomic_zip_archive, write_zip_bytes, write_zip_file
from src.function_registry import get_functions_for_provider_build
from src.providers.terraform.package_builders.common import _merge_requirements, _should_include_file

logger = logging.getLogger(__name__)
PROVIDERS_ROOT = Path(__file__).resolve().parents[2]

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
    has_gcp = any(
        providers_config.get(layer) in {"gcp", "google"}
        for layer in gcp_layers
    )
    
    if not has_gcp:
        logger.info("  No GCP layers configured, skipping Cloud Function package build")
        return {}
    
    # Build to project_path/.build/gcp/ (matches Terraform's expected paths)
    build_dir = project_path / ".build" / "gcp"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    packages = {}
    
    # Get GCP Cloud Functions source directory (from deployer src)
    gcp_funcs_dir = PROVIDERS_ROOT / "gcp" / "cloud_functions"
    shared_dir = gcp_funcs_dir / "_shared"
    
    # Load optimization flags from config_optimization.json
    optimization_flags = _load_optimization_flags(project_path)
    
    # Get functions from registry (replaces hardcoded boundary logic)
    functions_to_build = get_functions_for_provider_build("gcp", providers_config, optimization_flags)
    
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
            # Note: processor_wrapper no longer merges user code - per-device processors
            # are built separately via build_user_packages() which creates individual ZIPs
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
    project_path: Optional[Path] = None,
    digital_twin_name: Optional[str] = None,
    device_id: Optional[str] = None
) -> None:
    """
    Create a GCP Cloud Function deployment ZIP with shared modules.
    
    Args:
        func_dir: Path to function source directory
        shared_dir: Path to _shared modules directory
        output_path: Path to output ZIP file
        project_path: Optional project path for processor user code merge
        digital_twin_name: Optional digital twin name for processor renaming
        device_id: Optional device ID for processor renaming
    """
    with atomic_zip_archive(output_path) as zf:
        # Add function code (skip requirements.txt - will merge with defaults later)
        for file_path in sorted(func_dir.rglob('*')):
            if file_path.is_file() and _should_include_file(file_path):
                # Skip requirements.txt - we'll merge it with defaults
                if file_path.name == 'requirements.txt':
                    continue
                    
                arcname = file_path.relative_to(func_dir)
                
                # Apply renaming logic to main.py for processors
                if file_path.name == 'main.py' and digital_twin_name and device_id:
                    content = file_path.read_text(encoding='utf-8')
                    content = _rewrite_gcp_function_names(content, digital_twin_name, device_id)
                    write_zip_bytes(zf, arcname, content)
                else:
                    write_zip_file(zf, file_path, arcname)
        
        # Add shared modules under _shared/
        if shared_dir and shared_dir.exists():
            for file_path in sorted(shared_dir.rglob('*')):
                if file_path.is_file() and _should_include_file(file_path):
                    arcname = Path("_shared") / file_path.relative_to(shared_dir)
                    write_zip_file(zf, file_path, arcname)
        
        # Merge defaults with function's requirements.txt (always include defaults)
        defaults = {"functions-framework", "requests", "google-cloud-firestore", 
                   "google-cloud-storage", "google-cloud-pubsub", "google-auth"}
        func_req = func_dir / "requirements.txt"
        if func_req.exists():
            for line in func_req.read_text().strip().splitlines():
                if line.strip() and not line.startswith('#'):
                    defaults.add(line.strip())
        write_zip_bytes(zf, "requirements.txt", '\n'.join(sorted(defaults)) + '\n')



def _rewrite_gcp_function_names(content: str, twin_name: str, device_id: str) -> str:
    """
    Rewrite function names in GCP Cloud Function code.
    
    This handles any necessary renaming of entry points or identifiers
    to match the GCP naming constraints and project structure.
    
    Args:
        content: The python source code content
        twin_name: The digital twin name
        device_id: The device ID
        
    Returns:
        Modified source code
    """
    # Currently no rewriting needed for Decoupled Invoke pattern
    # The entry point is defined in main.py as 'process' or similar
    # and configured via Cloud Function entry_point setting.
    return content


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
    with atomic_zip_archive(output_path) as zf:
        # 1. Add base processor code (main.py, etc.)
        if base_dir.exists():
            for file_path in sorted(base_dir.rglob('*')):
                if file_path.is_file() and _should_include_file(file_path):
                    arcname = file_path.relative_to(base_dir)
                    write_zip_file(zf, file_path, arcname)
        
        # 2. Add shared modules under _shared/
        if shared_dir and shared_dir.exists():
            for file_path in sorted(shared_dir.rglob('*')):
                if file_path.is_file() and _should_include_file(file_path):
                    arcname = Path("_shared") / file_path.relative_to(shared_dir)
                    write_zip_file(zf, file_path, arcname)
        
        # 3. Add/Overwrite with user processor code (process.py)
        # Skip requirements.txt - will merge later
        if user_dir.exists():
            for file_path in sorted(user_dir.rglob('*.py')):
                if _should_include_file(file_path):
                    arcname = file_path.relative_to(user_dir)
                    write_zip_file(zf, file_path, arcname)
            logger.info(f"    → Merged user processor code from: {user_dir}")
        
        # 4. Merge requirements.txt (wrapper + user, no fallback)
        wrapper_req = base_dir / "requirements.txt"
        user_req = user_dir / "requirements.txt"
        merged = _merge_requirements(wrapper_req, user_req)
        if merged:
            write_zip_bytes(zf, "requirements.txt", merged)
        



def get_gcp_zip_path(project_path: Path, function_name: str) -> str:
    """Get the path to a GCP Cloud Function ZIP file (for Terraform variable references)."""
    return str(project_path / ".build" / "gcp" / f"{function_name}.zip")
