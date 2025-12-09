"""
File Manager - Project File Operations.

This module provides functions for creating projects from zip files,
managing configuration files, and updating function code.

All functions require the project_path parameter.
"""

import os
import zipfile
import json
import shutil
import hashlib
from datetime import datetime
import constants as CONSTANTS
from logger import logger
import io
import src.validator as validator


def _get_project_base_path():
    """Get the base path for projects. Uses PYTHONPATH or app detection."""
    # Prefer /app in container, fallback to parent of src/
    app_path = "/app"
    if os.path.exists(app_path):
        return app_path
    # Fallback: go up from this file's directory
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==========================================
# 1. Project Creation & Update (Zip Handling)
# ==========================================
def create_project_from_zip(project_name, zip_source, project_path: str = None, description: str = None):
    """
    Creates a new project from a validated zip file.
    
    Args:
        project_name (str): Name of the project to create.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
        description (str): Optional project description. If None, generated from digital_twin_name.
        
    Returns:
        dict: Result with message and any warnings.
        
    Raises:
        ValueError: If project name is invalid, project already exists, zip is invalid,
                    or duplicate project detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    # Simple validation using os.path to prevent directory traversal
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    # If bytes, convert to BytesIO for multiple reads (validate + extract)
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    # Validate before extraction (Universal Validation)
    warnings = validator.validate_project_zip(zip_source)
    if warnings is None:
        warnings = []
    
    # Extract twin_name and creds from zip for duplicate check
    zip_source.seek(0)
    twin_name, creds = _extract_identity_from_zip(zip_source)
    
    # Check for duplicate project (same twin_name + same credentials)
    conflicting_project = validator.check_duplicate_project(
        twin_name, creds, exclude_project=project_name, project_path=project_path
    )
    if conflicting_project:
        raise ValueError(
            f"Duplicate project detected: '{conflicting_project}' has the same "
            f"digital_twin_name and credentials."
        )
    
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    if os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' already exists.")
        
    os.makedirs(target_dir)
    
    # Archive version before extracting
    _archive_zip_version(zip_source, target_dir)
    
    # Extract only after validation passed
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
    
    # Write project_info.json
    _write_project_info(target_dir, zip_source, description)
        
    logger.info(f"Created project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' created.", "warnings": warnings}


def update_project_from_zip(project_name, zip_source, project_path: str = None, description: str = None):
    """
    Updates an existing project from a zip file (Overwrites existing files).
    Archives the new version before extracting.
    
    Args:
        project_name (str): Name of the project to update.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
        description (str): Optional project description. If None, keeps existing or generates.
        
    Returns:
        dict: Result with message and any warnings.
        
    Raises:
        ValueError: If project name is invalid, zip is invalid, or duplicate detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)
        
    # Validate entire zip content first (Universal Validation)
    warnings = validator.validate_project_zip(zip_source)
    if warnings is None:
        warnings = []
    
    # Extract twin_name and creds from zip for duplicate check
    zip_source.seek(0)
    twin_name, creds = _extract_identity_from_zip(zip_source)
    
    # Check for duplicate project (exclude self)
    conflicting_project = validator.check_duplicate_project(
        twin_name, creds, exclude_project=project_name, project_path=project_path
    )
    if conflicting_project:
        raise ValueError(
            f"Duplicate project detected: '{conflicting_project}' has the same "
            f"digital_twin_name and credentials."
        )
        
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    if not os.path.exists(target_dir):
         os.makedirs(target_dir)
    
    # Archive version before extracting
    _archive_zip_version(zip_source, target_dir)

    # Extract and Overwrite
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
    
    # Update project_info.json if description provided
    if description:
        _write_project_info(target_dir, zip_source, description)
        
    logger.info(f"Updated project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' updated.", "warnings": warnings}


# ==========================================
# 2. Project Listing
# ==========================================
def list_projects(project_path: str = None):
    """
    Returns a list of available project names.
    
    Args:
        project_path: Base project path. If None, auto-detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    upload_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
    projects = []
    if os.path.exists(upload_dir):
        for item in os.listdir(upload_dir):
            if os.path.isdir(os.path.join(upload_dir, item)):
                projects.append(item)
    return projects


# ==========================================
# 3. Configuration Management
# ==========================================
def update_config_file(project_name, config_filename, config_content, project_path: str = None):
    """
    Updates a specific configuration file for a project.
    
    Args:
        project_name: Name of the project
        config_filename: Name of the config file
        config_content: JSON content to write
        project_path: Base project path. If None, auto-detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
        
    target_file = os.path.join(target_dir, config_filename)
    
    # Verify content is valid JSON
    if isinstance(config_content, str):
        try:
             json_content = json.loads(config_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content for {config_filename}: {e}")
    else:
        json_content = config_content

    # Validate Schema
    validator.validate_config_content(config_filename, json_content)

    with open(target_file, 'w') as f:
        json.dump(json_content, f, indent=2)
        
    logger.info(f"Updated {config_filename} for project '{project_name}'.")


# ==========================================
# 4. Function Management
# ==========================================
def get_provider_for_function(project_name, function_name, project_path: str = None):
    """Proxy for validator.get_provider_for_function"""
    if project_path is None:
        project_path = _get_project_base_path()
    return validator.get_provider_for_function(project_name, function_name, project_path)


def update_function_code_file(project_name, function_name, file_name, code_content, project_path: str = None):
    """
    Updates the code file for a specific function, with provider-specific validation.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        file_name: Name of the file to update
        code_content: Code content to write
        project_path: Base project path. If None, auto-detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_project_name = os.path.basename(project_name)
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_project_name, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, function_name)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Function directory '{function_name}' does not exist in project '{project_name}'.")

    # Validate Python Code
    if file_name.endswith(".py"):
        provider = validator.get_provider_for_function(project_name, function_name, project_path)
        if provider == "aws":
            validator.validate_python_code_aws(code_content)
        elif provider == "azure":
            validator.validate_python_code_azure(code_content)
        elif provider == "google":
            validator.validate_python_code_google(code_content)
            
    # Write File
    target_file = os.path.join(target_dir, file_name)
    with open(target_file, 'w') as f:
        f.write(code_content)
        
    logger.info(f"Updated function code '{file_name}' for function '{function_name}' in project '{project_name}'.")


# ==========================================
# 5. Versioning & Metadata Helpers
# ==========================================
def _archive_zip_version(zip_source, target_dir):
    """
    Archives the uploaded zip to {target_dir}/versions/{timestamp}.zip.
    
    Args:
        zip_source: BytesIO containing the zip file.
        target_dir: Project directory to archive into.
    """
    versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
    os.makedirs(versions_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    version_path = os.path.join(versions_dir, f"{timestamp}.zip")
    
    zip_source.seek(0)
    with open(version_path, 'wb') as f:
        f.write(zip_source.read())
    
    logger.info(f"Archived version to {version_path}")


def _write_project_info(target_dir, zip_source, description: str = None):
    """
    Writes project_info.json with description and timestamps.
    If description is None, generates from config.json's digital_twin_name.
    
    Args:
        target_dir: Project directory.
        zip_source: BytesIO containing the zip file.
        description: Optional description string.
    """
    if not description:
        # Read digital_twin_name from config.json in zip
        zip_source.seek(0)
        with zipfile.ZipFile(zip_source, 'r') as zf:
            for name in zf.namelist():
                if name.endswith(CONSTANTS.CONFIG_FILE):
                    with zf.open(name) as f:
                        config = json.load(f)
                        twin_name = config.get("digital_twin_name")
                        if not twin_name:
                            raise ValueError("Missing mandatory 'digital_twin_name' in config.json")
                        description = f"Project builds the digital twin with prefix name '{twin_name}'"
                        break
    
    info_path = os.path.join(target_dir, CONSTANTS.PROJECT_INFO_FILE)
    with open(info_path, 'w') as f:
        json.dump({
            "description": description, 
            "created_at": datetime.now().isoformat()
        }, f, indent=2)


def _extract_identity_from_zip(zip_source):
    """
    Extracts digital_twin_name and credentials from a zip file.
    
    Args:
        zip_source: BytesIO containing the zip file.
        
    Returns:
        tuple: (digital_twin_name, credentials_dict)
    """
    twin_name = None
    creds = {}
    
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, 'r') as zf:
        for name in zf.namelist():
            if name.endswith(CONSTANTS.CONFIG_FILE):
                with zf.open(name) as f:
                    config = json.load(f)
                    twin_name = config.get("digital_twin_name")
            elif name.endswith(CONSTANTS.CONFIG_CREDENTIALS_FILE):
                with zf.open(name) as f:
                    creds = json.load(f)
    
    return twin_name, creds


# ==========================================
# 6. Project CRUD Operations
# ==========================================
def delete_project(project_name, project_path: str = None):
    """
    Deletes an entire project directory.
    
    Args:
        project_name: Name of the project to delete.
        project_path: Base project path. If None, auto-detected.
        
    Raises:
        ValueError: If project does not exist.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    shutil.rmtree(target_dir)
    logger.info(f"Deleted project '{project_name}'.")


def update_project_info(project_name, description: str, project_path: str = None):
    """
    Updates the description in project_info.json.
    
    Args:
        project_name: Name of the project.
        description: New description.
        project_path: Base project path. If None, auto-detected.
        
    Raises:
        ValueError: If project does not exist.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    info_path = os.path.join(target_dir, CONSTANTS.PROJECT_INFO_FILE)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    info = {}
    if os.path.exists(info_path):
        with open(info_path, 'r') as f:
            info = json.load(f)
    
    info["description"] = description
    info["updated_at"] = datetime.now().isoformat()
    
    with open(info_path, 'w') as f:
        json.dump(info, f, indent=2)
    
    logger.info(f"Updated info for project '{project_name}'.")
