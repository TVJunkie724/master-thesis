"""
Directory Validator - Project directory validation.

This module is a thin adapter that delegates to src.validation.core.
Used for pre-deployment validation of unpacked project directories.
"""

from pathlib import Path
from typing import Union

from src.validation.core import run_all_checks
from src.validation.accessors import DirectoryAccessor


def validate_project_directory(project_path: Union[str, Path]) -> None:
    """
    Validates an unpacked project directory structure.
    
    Runs the same comprehensive validation checks as ZIP validation,
    but operates on a file system directory. Useful for:
    - Pre-deployment validation (catch config drift after upload)
    - CI/CD pipeline validation
    - Manual project folder validation
    
    Args:
        project_path: Path to project directory
        
    Raises:
        ValueError: For any validation failure with descriptive message
    """
    project_path = Path(project_path)
    
    if not project_path.exists():
        raise ValueError(f"Project directory not found: {project_path}")
    
    if not project_path.is_dir():
        raise ValueError(f"Path is not a directory: {project_path}")
    
    accessor = DirectoryAccessor(project_path)
    run_all_checks(accessor)
