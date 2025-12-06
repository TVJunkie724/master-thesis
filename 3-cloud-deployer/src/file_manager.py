import os
import zipfile
import json
import shutil
import globals
import constants as CONSTANTS
from logger import logger

import io

def validate_project_zip(zip_source):
    """
    Validates that a zip file contains all required configuration files.
    zip_source can be a path (str) or a file-like object/bytes.
    """
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    with zipfile.ZipFile(zip_source, 'r') as zf:
        file_list = zf.namelist()
        missing_files = []
        for required_file in CONSTANTS.REQUIRED_CONFIG_FILES:
            if required_file not in file_list:
                missing_files.append(required_file)
        
        if missing_files:
            raise ValueError(f"Invalid project zip. Missing required files: {', '.join(missing_files)}")

def create_project_from_zip(project_name, zip_source):
    """
    Creates a new project from a zip file.
    zip_source can be a path (str) or a file-like object/bytes.
    """
    # Simple validation using os.path to prevent directory traversal
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    # If bytes, convert to BytesIO for multiple reads (validate + extract)
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    validate_project_zip(zip_source)
    
    target_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    if os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' already exists.")
        
    os.makedirs(target_dir)
    
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
        
    logger.info(f"Created project '{project_name}' from zip.")

def list_projects():
    """
    Returns a list of available project names.
    """
    upload_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
    projects = []
    if os.path.exists(upload_dir):
        for item in os.listdir(upload_dir):
            if os.path.isdir(os.path.join(upload_dir, item)):
                projects.append(item)
    return projects

def update_config_file(project_name, config_filename, config_content):
    """
    Updates a specific configuration file for a project.
    Hot-reloads if the project is currently active.
    """
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
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

    with open(target_file, 'w') as f:
        json.dump(json_content, f, indent=2)
        
    logger.info(f"Updated {config_filename} for project '{project_name}'.")
    
    # Hot Reload
    if project_name == globals.CURRENT_PROJECT:
        logger.info(f"Hot-reloading configuration for active project '{project_name}'...")
        if config_filename == CONSTANTS.CONFIG_FILE:
            globals.initialize_config()
        elif config_filename == CONSTANTS.CONFIG_IOT_DEVICES_FILE:
            globals.initialize_config_iot_devices()
        elif config_filename == CONSTANTS.CONFIG_EVENTS_FILE:
            globals.initialize_config_events()
        elif config_filename == CONSTANTS.CONFIG_HIERARCHY_FILE:
            globals.initialize_config_hierarchy()
        elif config_filename == CONSTANTS.CONFIG_CREDENTIALS_FILE:
            globals.initialize_config_credentials()
        elif config_filename == CONSTANTS.CONFIG_PROVIDERS_FILE:
            globals.initialize_config_providers()
