"""Deterministic function archives and deployment hash metadata."""

import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from src.api.function_discovery import _get_upload_dir, _invalidate_cache
from logger import logger
from src.core.deterministic_zip import write_zip_file
from src.function_metadata import (
    hash_directory,
    load_function_metadata,
    metadata_path,
)


def _iter_regular_files(directory: str, description: str):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"{description} directory not found or unsafe: {directory}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symbolic links are not allowed in {description} directories")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in {".pyc", ".zip"}
            and path.name != ".DS_Store"
            and not path.name.startswith(".git")
        ):
            yield root, path

def _compute_source_hash(dir_path: str) -> str:
    """
    Compute SHA256 hash of all files in a directory.
    
    Args:
        dir_path: Path to directory to hash
        
    Returns:
        SHA256 hash string prefixed with 'sha256:'
        
    Raises:
        ValueError: If directory doesn't exist
    """
    return hash_directory(dir_path)


def _build_function_zip(func_dir: str, shared_dir: Optional[str] = None) -> bytes:
    """
    Build a deployment ZIP for a function.
    
    Args:
        func_dir: Path to function code directory
        shared_dir: Optional path to shared modules to include
        
    Returns:
        ZIP file content as bytes
        
    Raises:
        ValueError: If function directory doesn't exist
    """
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, path in _iter_regular_files(func_dir, "Function"):
            write_zip_file(archive, path, path.relative_to(root))

        if shared_dir:
            for root, path in _iter_regular_files(shared_dir, "Shared module"):
                write_zip_file(
                    archive,
                    path,
                    Path("_shared") / path.relative_to(root),
                )
    
    return buffer.getvalue()


def _get_metadata_path(project_name: str, function_name: str, provider: str) -> str:
    """
    Get path to hash metadata file for a function.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name (aws/azure)
        
    Returns:
        Path to metadata JSON file
    """
    upload_dir = Path(_get_upload_dir(project_name))
    return os.fspath(metadata_path(upload_dir, function_name, provider))


def get_artifact_metadata(
    project_name: str,
    function_name: str,
    provider: str,
) -> dict[str, Any] | None:
    """
    Load hash metadata for a function if it exists.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
        
    Returns:
        Metadata dict or None if not found
    """
    target = Path(_get_metadata_path(project_name, function_name, provider))
    return load_function_metadata(target)


def clear_all_function_metadata(project_name: str) -> None:
    """
    Clear all hash metadata for a project.
    
    Called when project ZIP is fully replaced.
    
    Args:
        project_name: Name of the project
    """
    upload_dir = _get_upload_dir(project_name)
    metadata_dir = os.path.join(upload_dir, ".build", "metadata")
    
    if os.path.exists(metadata_dir):
        shutil.rmtree(metadata_dir)
        logger.info("Cleared all function metadata for project: %s", project_name)
    
    # Also invalidate cache
    _invalidate_cache(project_name)
