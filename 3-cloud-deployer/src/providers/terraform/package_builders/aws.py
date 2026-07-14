"""AWS Lambda package construction for Terraform deployments."""

import logging
from pathlib import Path
from typing import Dict, Optional

from src.core.config_loader import load_optimization_flags as _load_optimization_flags
from src.core.deterministic_zip import atomic_zip_archive, write_zip_file
from src.function_registry import get_functions_for_provider_build
from src.providers.terraform.package_builders.common import _should_include_file

logger = logging.getLogger(__name__)
PROVIDERS_ROOT = Path(__file__).resolve().parents[2]

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
    lambda_dir = PROVIDERS_ROOT / "aws" / "lambda_functions"
    shared_dir = lambda_dir / "_shared"
    
    packages = {}
    
    # Load optimization flags from config_optimization.json
    optimization_flags = _load_optimization_flags(project_path)
    
    # Get functions from registry (replaces hardcoded boundary logic)
    functions_to_build = get_functions_for_provider_build("aws", providers_config, optimization_flags)
    
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



def _create_lambda_zip(
    func_dir: Path, 
    shared_dir: Path, 
    output_path: Path,
    digital_twin_name: Optional[str] = None,
    device_id: Optional[str] = None
) -> None:
    """
    Create a Lambda deployment ZIP with function code and shared modules.
    
    Args:
        func_dir: Path to function source directory
        shared_dir: Path to _shared modules directory
        output_path: Path to output ZIP file
        digital_twin_name: Optional digital twin name for processor renaming
        device_id: Optional device ID for processor renaming
    """
    with atomic_zip_archive(output_path) as zf:
        # Add function files
        for file_path in sorted(func_dir.rglob('*')):
            if file_path.is_file() and _should_include_file(file_path):
                arcname = file_path.relative_to(func_dir)
                write_zip_file(zf, file_path, arcname)
        
        # Add shared modules
        if shared_dir.exists():
            for file_path in sorted(shared_dir.rglob('*')):
                if file_path.is_file() and _should_include_file(file_path):
                    arcname = f"_shared/{file_path.relative_to(shared_dir)}"
                    write_zip_file(zf, file_path, arcname)



def get_lambda_zip_path(project_path: Path, function_name: str) -> str:
    """Get the path to a Lambda ZIP file (for Terraform variable references)."""
    return str(project_path / ".build" / "aws" / f"{function_name}.zip")


