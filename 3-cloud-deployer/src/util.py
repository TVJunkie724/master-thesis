"""
Utility Functions - Common Operations.

This module provides utility functions for file operations, Lambda compilation,
and credential validation.

All functions that need project context now REQUIRE the project_path parameter.
"""

import os
import zipfile
import json
from typing import Optional
from fastapi.responses import JSONResponse
import constants as CONSTANTS


def pretty_json(data):
    """Return JSON with indentation and UTF-8 encoding."""
    return JSONResponse(
        content=json.loads(json.dumps(data, indent=2, ensure_ascii=False))
    )


def contains_provider(config_providers: dict, provider_name: str) -> bool:
    """Check if any value in the provider config matches provider_name."""
    return any(provider_name in str(v).lower() for v in config_providers.values())


def validate_credentials(provider_name: str, credentials: dict) -> dict:
    """Check if credentials exist and all required fields are present.
    
    Args:
        provider_name: The cloud provider name (aws, azure, gcp)
        credentials: Dictionary containing credential configurations
        
    Returns:
        The provider-specific credentials dictionary
        
    Raises:
        ValueError: If credentials are missing or incomplete
    """
    provider_creds = credentials.get(provider_name, {})
    if not provider_creds:
        raise ValueError(f"{provider_name.upper()} credentials are required but not found.")
    
    missing_fields = [
        field for field in CONSTANTS.REQUIRED_CREDENTIALS_FIELDS[provider_name] 
        if field not in provider_creds
    ]
    if missing_fields:
        raise ValueError(f"{provider_name.upper()} credentials are missing fields: {missing_fields}")
    return provider_creds


def get_path_in_project(subpath: str = "", project_path: str = None) -> str:
    """Returns the absolute path to a file or directory within a project's upload directory.
    
    Args:
        subpath: Optional subdirectory or file path within the project
        project_path: Project path (required)
        
    Returns:
        Absolute path to the requested location
    """
    if project_path is None:
        raise ValueError("project_path is required")
    
    if subpath:
        return os.path.join(project_path, subpath)
    return project_path


def resolve_folder_path(folder_path: str, project_path: str = None) -> str:
    """Resolve a folder path to an absolute path.
    
    Tries relative to project first, then as absolute path.
    
    Args:
        folder_path: Path to resolve
        project_path: Project path (REQUIRED for relative resolution)
        
    Returns:
        Absolute path to the folder
        
    Raises:
        FileNotFoundError: If folder doesn't exist
    """
    # Try relative to project if project_path provided
    if project_path is not None:
        rel_path = os.path.join(project_path, folder_path)
        if os.path.exists(rel_path):
            return rel_path

    # Try as absolute path
    abs_path = os.path.abspath(folder_path)
    if os.path.exists(abs_path):
        return abs_path

    raise FileNotFoundError(
        f"Folder '{folder_path}' does not exist as relative or absolute path."
    )


def zip_directory(folder_path: str, zip_name: str = 'zipped.zip', project_path: str = None) -> str:
    """Zip a directory's contents.
    
    Args:
        folder_path: Path to the directory to zip
        zip_name: Name of the output zip file
        project_path: Optional project path for resolution
        
    Returns:
        Path to the created zip file
    """
    folder_path = resolve_folder_path(folder_path, project_path)
    output_path = os.path.join(folder_path, zip_name)

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                if full_path == output_path:
                    continue
                arcname = os.path.relpath(full_path, start=folder_path)
                zf.write(full_path, arcname)

    return output_path


def compile_lambda_function(folder_path: str, project_path: str = None) -> bytes:
    """Compile a Lambda function directory into a deployable zip.
    
    Also includes the _shared directory (if present) from the parent
    lambda_functions folder. This enables Lambda functions to import
    from _shared.inter_cloud for centralized cross-cloud HTTP logic.
    
    Args:
        folder_path: Path to the Lambda function directory
        project_path: Optional project path for resolution
        
    Returns:
        Bytes of the zipped Lambda package
    """
    import io
    import tempfile
    import shutil
    
    resolved_path = resolve_folder_path(folder_path, project_path)
    
    # Check if _shared folder exists in parent (lambda_functions directory)
    parent_dir = os.path.dirname(resolved_path)
    shared_dir = os.path.join(parent_dir, "_shared")
    include_shared = os.path.isdir(shared_dir)
    
    if include_shared:
        # Create temp dir, copy function code + _shared folder
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy Lambda function files
            for item in os.listdir(resolved_path):
                src = os.path.join(resolved_path, item)
                dst = os.path.join(temp_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)
            
            # Copy _shared folder
            shared_dst = os.path.join(temp_dir, "_shared")
            shutil.copytree(shared_dir, shared_dst)
            
            # Zip the combined package
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, start=temp_dir)
                        zf.write(full_path, arcname)
            
            return zip_buffer.getvalue()
    else:
        # Original behavior: just zip the folder
        zip_path = zip_directory(folder_path, project_path=project_path)

        with open(zip_path, "rb") as f:
            zip_code = f.read()

        return zip_code


def compile_merged_lambda_function(
    base_path: str, 
    custom_file_path: str,
    project_path: str = None
) -> bytes:
    """Merges a base system wrapper folder with a custom user file, then zips it.
    
    Args:
        base_path: Path to the system wrapper code (e.g. processor_wrapper)
        custom_file_path: Relative path (from project upload) to the user's custom code
        project_path: Project path (required)
        
    Returns:
        bytes: The zipped deployment package.
    """
    import shutil
    import tempfile
    
    if project_path is None:
         raise ValueError("project_path is required")
    
    # 1. Resolve Paths
    abs_base_path = resolve_folder_path(base_path, project_path)
    abs_custom_path = os.path.join(project_path, custom_file_path)
    
    if not os.path.exists(abs_base_path):
        raise FileNotFoundError(f"Base path not found: {abs_base_path}")
    if not os.path.exists(abs_custom_path):
        raise FileNotFoundError(f"Custom file not found: {abs_custom_path}")

    # 2. Create Temp Build Directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # 3. Copy Base System Code
        for item in os.listdir(abs_base_path):
            s = os.path.join(abs_base_path, item)
            d = os.path.join(temp_dir, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
            elif os.path.isdir(s):
                shutil.copytree(s, d)
        
        # 4. Copy Custom User Code
        dest_custom_path = os.path.join(temp_dir, "process.py")
        shutil.copy2(abs_custom_path, dest_custom_path)
        
        # 5. Zip the Result
        zip_path = zip_directory(temp_dir, zip_name="merged_function.zip", project_path=temp_dir)
        
        with open(zip_path, "rb") as f:
            zip_code = f.read()
            
    return zip_code
