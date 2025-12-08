"""
File Manager - Project File Operations.

This module provides functions for creating projects from zip files,
managing configuration files, and updating function code.

All functions now REQUIRE the project_path parameter.
Legacy globals fallback has been removed.
"""

import os
import zipfile
import json
import shutil
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
def create_project_from_zip(project_name, zip_source, project_path: str = None):
    """
    Creates a new project from a validated zip file.
    
    Args:
        project_name (str): Name of the project to create.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
        
    Raises:
        ValueError: If project name is invalid, project already exists, or zip is invalid.
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
    validator.validate_project_zip(zip_source)
    
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    if os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' already exists.")
        
    os.makedirs(target_dir)
    
    # Extract only after validation passed
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
        
    logger.info(f"Created project '{project_name}' from zip.")


def update_project_from_zip(project_name, zip_source, project_path: str = None):
    """
    Updates an existing project from a zip file (Overwrites existing files).
    
    Args:
        project_name (str): Name of the project to update.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
        
    Raises:
        ValueError: If project name is invalid or zip is invalid.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)
        
    # Validate entire zip content first (Universal Validation)
    validator.validate_project_zip(zip_source)
        
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    if not os.path.exists(target_dir):
         os.makedirs(target_dir)

    # Extract and Overwrite
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
        
    logger.info(f"Updated project '{project_name}' from zip.")


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
