"""
Azure Function Bundler - Per-App ZIP Packaging.

This module bundles multiple Azure Functions into single ZIP files
per Function App, for use with Terraform-based deployment.

Each bundle method:
1. Checks config_providers.json for conditional deployment
2. Collects all function folders for the app
3. Adds shared files (requirements.txt, host.json)
4. Returns a single ZIP bytes object

Usage:
    from function_bundler import bundle_l0_functions, bundle_l1_functions
    
    # For L0 glue (per-boundary conditional)
    zip_bytes, functions = bundle_l0_functions(project_path, providers_config)
    
    # For L1-L3 (layer-conditional)
    zip_bytes = bundle_l1_functions(project_path)
"""

import os
import io
import zipfile
import logging
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class BundleError(Exception):
    """Raised when function bundling fails."""
    pass


def _get_azure_functions_dir(project_path: str) -> Path:
    """Get the azure_functions directory path."""
    return Path(project_path) / "azure_functions"


def _add_shared_files(zf: zipfile.ZipFile, azure_functions_dir: Path) -> None:
    """Add shared files (requirements.txt, host.json, _shared/) to ZIP."""
    # Add requirements.txt if exists
    requirements_path = azure_functions_dir / "requirements.txt"
    if requirements_path.exists():
        zf.write(requirements_path, "requirements.txt")
    
    # Add host.json if exists
    host_path = azure_functions_dir / "host.json"
    if host_path.exists():
        zf.write(host_path, "host.json")
    
    # Add _shared directory if exists
    shared_dir = azure_functions_dir / "_shared"
    if shared_dir.exists() and shared_dir.is_dir():
        for root, _, files in os.walk(shared_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(azure_functions_dir)
                zf.write(file_path, str(arcname))


def _add_function_dir(zf: zipfile.ZipFile, func_dir: Path, azure_functions_dir: Path) -> None:
    """Add a function directory to the ZIP."""
    if not func_dir.exists():
        logger.warning(f"Function directory does not exist: {func_dir}")
        return
    
    for root, _, files in os.walk(func_dir):
        for file in files:
            # Skip __pycache__ and .pyc files
            if "__pycache__" in root or file.endswith(".pyc"):
                continue
            file_path = Path(root) / file
            arcname = file_path.relative_to(azure_functions_dir)
            zf.write(file_path, str(arcname))


def bundle_l0_functions(
    project_path: str,
    providers_config: dict
) -> Tuple[Optional[bytes], List[str]]:
    """
    Bundle L0 Glue functions based on cross-cloud boundaries.
    
    Only includes functions for boundaries that cross clouds:
    - ingestion: L1 → L2 (if L1 != L2 provider)
    - hot-writer: L2 → L3_hot (if L2 != L3_hot provider)
    - hot-reader: L3_hot → L4/L5 (if L3_hot != L4 or L3_hot != L5)
    
    Args:
        project_path: Absolute path to project directory
        providers_config: Provider configuration dict from config_providers.json
    
    Returns:
        Tuple of (zip_bytes, list_of_included_functions)
        Returns (None, []) if no glue functions needed
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    if not azure_functions_dir.exists():
        raise BundleError(f"azure_functions directory not found: {azure_functions_dir}")
    
    # Validate required provider configuration
    required_keys = [
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_hot_provider",
        "layer_4_provider",
        "layer_5_provider"
    ]
    
    for key in required_keys:
        if key not in providers_config:
            raise ValueError(f"Missing required provider config: {key}")
    
    l1 = providers_config["layer_1_provider"]
    l2 = providers_config["layer_2_provider"]
    l3_hot = providers_config["layer_3_hot_provider"]
    l4 = providers_config["layer_4_provider"]
    l5 = providers_config["layer_5_provider"]
    
    functions_to_include = []
    
    # L1 → L2 boundary: ingestion function on L2's cloud
    if l1 != l2 and l2 == "azure":
        functions_to_include.append("ingestion")
    
    # L2 → L3_hot boundary: hot-writer function on L3's cloud
    if l2 != l3_hot and l3_hot == "azure":
        functions_to_include.append("hot-writer")
    
    # L3_hot → L4 boundary: data connector (if needed)
    if l3_hot != l4 and l4 == "azure":
        functions_to_include.append("adt-pusher")
    
    # L3_hot → L5 boundary: hot-reader on L5's cloud
    if l3_hot != l5 and l5 == "azure":
        functions_to_include.append("hot-reader")
        functions_to_include.append("hot-reader-last-entry")
    
    # Also add hot-reader if L4 needs to read from different cloud
    if l3_hot != l4 and l4 == "azure" and "hot-reader" not in functions_to_include:
        functions_to_include.append("hot-reader")
        functions_to_include.append("hot-reader-last-entry")
    
    if not functions_to_include:
        logger.info("No L0 glue functions needed (single-cloud deployment)")
        return None, []
    
    logger.info(f"Bundling L0 glue functions: {functions_to_include}")
    
    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        for func_name in functions_to_include:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                _add_function_dir(zf, func_dir, azure_functions_dir)
            else:
                logger.warning(f"L0 function not found: {func_name}")
    
    return zip_buffer.getvalue(), functions_to_include


def bundle_l1_functions(project_path: str) -> bytes:
    """
    Bundle L1 functions (dispatcher).
    
    Args:
        project_path: Absolute path to project directory
    
    Returns:
        ZIP bytes for L1 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    functions = ["dispatcher"]
    
    logger.info(f"Bundling L1 functions: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        for func_name in functions:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                _add_function_dir(zf, func_dir, azure_functions_dir)
            else:
                logger.warning(f"L1 function not found: {func_name}")
    
    return zip_buffer.getvalue()


def bundle_l2_functions(project_path: str) -> bytes:
    """
    Bundle L2 functions (persister, event-checker).
    
    Args:
        project_path: Absolute path to project directory
    
    Returns:
        ZIP bytes for L2 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    # Core functions
    functions = ["persister"]
    
    # Optional: event-checker if exists
    event_checker_dir = azure_functions_dir / "event-checker"
    if event_checker_dir.exists():
        functions.append("event-checker")
    
    logger.info(f"Bundling L2 functions: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        for func_name in functions:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                _add_function_dir(zf, func_dir, azure_functions_dir)
            else:
                logger.warning(f"L2 function not found: {func_name}")
    
    return zip_buffer.getvalue()


def bundle_l3_functions(project_path: str) -> bytes:
    """
    Bundle L3 functions (hot-reader, movers).
    
    Args:
        project_path: Absolute path to project directory
    
    Returns:
        ZIP bytes for L3 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    # Core functions for L3
    functions = [
        "hot-reader",
        "hot-reader-last-entry",
        "hot-cold-mover",
        "cold-archive-mover"
    ]
    
    logger.info(f"Bundling L3 functions: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        for func_name in functions:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                _add_function_dir(zf, func_dir, azure_functions_dir)
            else:
                logger.warning(f"L3 function not found: {func_name}")
    
    return zip_buffer.getvalue()


def bundle_l4_functions(project_path: str) -> bytes:
    """
    Bundle L4 functions (ADT-related).
    
    Note: L4 may not need a separate Function App if ADT updates
    are done via Python SDK directly from L2/L3.
    
    Args:
        project_path: Absolute path to project directory
    
    Returns:
        ZIP bytes for L4 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    # L4 functions - optional ADT updater
    functions = ["adt-updater"]
    
    logger.info(f"Bundling L4 functions: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        for func_name in functions:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                _add_function_dir(zf, func_dir, azure_functions_dir)
            else:
                logger.warning(f"L4 function not found: {func_name}")
    
    return zip_buffer.getvalue()
