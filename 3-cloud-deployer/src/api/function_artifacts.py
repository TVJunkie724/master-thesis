"""Deterministic function archives and deployment hash metadata."""

import datetime
import hashlib
import json
import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from api.function_discovery import _get_upload_dir, _invalidate_cache
from logger import logger
from src.core.paths import validate_path_component


def _iter_regular_files(directory: str, description: str):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"{description} directory not found or unsafe: {directory}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symbolic links are not allowed in {description} directories")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            yield root, path

def _compute_directory_hash(dir_path: str) -> str:
    """
    Compute SHA256 hash of all files in a directory.
    
    Args:
        dir_path: Path to directory to hash
        
    Returns:
        SHA256 hash string prefixed with 'sha256:'
        
    Raises:
        ValueError: If directory doesn't exist
    """
    hasher = hashlib.sha256()

    for root, path in _iter_regular_files(dir_path, "Function"):
        hasher.update(path.relative_to(root).as_posix().encode("utf-8"))
        with path.open("rb") as function_file:
            while chunk := function_file.read(8192):
                hasher.update(chunk)
    
    return f"sha256:{hasher.hexdigest()}"


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
            archive.write(path, path.relative_to(root).as_posix())

        if shared_dir:
            for root, path in _iter_regular_files(shared_dir, "Shared module"):
                archive.write(path, path.relative_to(root).as_posix())
    
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
    validate_path_component(function_name, "function name")
    validate_path_component(provider, "provider name")
    upload_dir = _get_upload_dir(project_name)
    metadata_dir = os.path.join(upload_dir, ".build", "metadata")
    return os.path.join(metadata_dir, f"{function_name}.{provider}.json")


def _save_hash_metadata(
    project_name: str, 
    function_name: str, 
    provider: str, 
    code_hash: str
) -> None:
    """
    Save hash metadata for a deployed function.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
        code_hash: SHA256 hash of the function code
    """
    metadata_path = _get_metadata_path(project_name, function_name, provider)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    
    metadata = {
        "function": function_name,
        "provider": provider,
        "zip_hash": code_hash,
        "last_deployed": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Saved hash metadata: {metadata_path}")


def _get_hash_metadata(project_name: str, function_name: str, provider: str) -> Optional[Dict[str, Any]]:
    """
    Load hash metadata for a function if it exists.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
        
    Returns:
        Metadata dict or None if not found
    """
    metadata_path = _get_metadata_path(project_name, function_name, provider)
    
    if not os.path.exists(metadata_path):
        return None
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def _delete_hash_metadata(project_name: str, function_name: str, provider: str) -> None:
    """
    Delete hash metadata for a function.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
    """
    metadata_path = _get_metadata_path(project_name, function_name, provider)
    
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
        logger.info(f"Deleted hash metadata: {metadata_path}")


def clear_all_hash_metadata(project_name: str) -> None:
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
        logger.info(f"Cleared all hash metadata for project: {project_name}")
    
    # Also invalidate cache
    _invalidate_cache(project_name)
