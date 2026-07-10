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
from pathlib import Path
import constants as CONSTANTS
from logger import logger
import io
import src.validator as validator
from src.core.project_storage import ProjectStorage, is_sensitive_project_file


def _is_sensitive_project_file(relative_path: str) -> bool:
    """Return True when a project file may contain live cloud credentials."""
    return is_sensitive_project_file(relative_path)


def _get_project_base_path():
    """Get the base path for projects. Uses PYTHONPATH or app detection."""
    # Prefer /app in container, fallback to parent of src/
    app_path = "/app"
    if os.path.exists(app_path):
        return app_path
    # Fallback: go up from this file's directory
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_project_storage(project_path: str = None) -> ProjectStorage:
    """Return the project storage boundary for legacy file_manager callers."""
    if project_path is None:
        project_path = _get_project_base_path()
    return ProjectStorage(project_root=Path(project_path))


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

    zip_source.seek(0)
    _validate_project_name_matches_manifest(safe_name, _extract_deployment_manifest(zip_source))
    
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
    
    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(safe_name)
    if target_dir.exists():
        raise ValueError(f"Project '{project_name}' already exists.")
        
    target_dir.mkdir(parents=True)
    
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

    zip_source.seek(0)
    _validate_project_name_matches_manifest(safe_name, _extract_deployment_manifest(zip_source))
    
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
        
    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(safe_name)
    
    if not target_dir.exists():
         target_dir.mkdir(parents=True)
    
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
def list_projects(project_path: str = None, include_templates: bool = False):
    """
    Returns a list of available project names.
    
    Args:
        project_path: Base project path. If None, auto-detected.
        include_templates: Include legacy template folders that still live under upload.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    return _get_project_storage(project_path).list_projects(include_templates=include_templates)


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
    
    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(project_name)
    
    if not target_dir.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")
    
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

    storage.write_json(project_name, config_filename, json_content)
        
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
    
    storage = _get_project_storage(project_path)
    function_dir = f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/{function_name}"
    target_dir = storage.resolve_file(project_name, function_dir)
    
    if not target_dir.exists():
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
    target_file = storage.resolve_file(project_name, f"{function_dir}/{file_name}", for_write=True)
    target_file.write_text(code_content, encoding="utf-8")
        
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


def _extract_deployment_manifest(zip_source):
    """Extract deployment_manifest.json from a validated ZIP, if present."""
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, 'r') as zf:
        manifest_paths = [
            name for name in zf.namelist()
            if os.path.basename(name) == CONSTANTS.DEPLOYMENT_MANIFEST_FILE
        ]
        if not manifest_paths:
            return None
        if len(manifest_paths) > 1:
            raise ValueError("Multiple deployment_manifest.json files found in project ZIP.")
        with zf.open(manifest_paths[0]) as f:
            return json.load(f)


def _validate_project_name_matches_manifest(project_name: str, manifest: dict | None) -> None:
    """Ensure a manifest-backed upload lands under its declared resource name."""
    if not manifest:
        return

    twin = manifest.get("twin")
    if not isinstance(twin, dict):
        raise ValueError("deployment_manifest.json twin metadata must be a JSON object.")

    resource_name = twin.get("resource_name")
    if not isinstance(resource_name, str) or not resource_name:
        raise ValueError("deployment_manifest.json twin.resource_name is required.")

    if resource_name != project_name:
        raise ValueError(
            "deployment_manifest.json twin.resource_name does not match requested project_name."
        )


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
    
    target_dir = _get_project_storage(project_path).deployment_project_path(project_name)
    
    if not target_dir.exists():
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
    
    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(project_name)
    info_path = target_dir / CONSTANTS.PROJECT_INFO_FILE
    
    if not target_dir.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    info = {}
    if info_path.exists():
        with info_path.open('r') as f:
            info = json.load(f)
    
    info["description"] = description
    info["updated_at"] = datetime.now().isoformat()
    
    storage.write_json(project_name, CONSTANTS.PROJECT_INFO_FILE, info)
    
    logger.info(f"Updated info for project '{project_name}'.")


def export_project_to_zip(project_name: str, project_path: str = None) -> io.BytesIO:
    """
    Exports an entire project directory to a zip file in memory.
    
    Args:
        project_name: Name of the project to export.
        project_path: Base project path. If None, auto-detected.
        
    Returns:
        BytesIO: In-memory zip file buffer.
        
    Raises:
        ValueError: If project does not exist.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    target_dir = _get_project_storage(project_path).deployment_project_path(project_name)
    
    if not target_dir.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(target_dir):
            # Exclude versions, .build, and internal metadata
            dirs[:] = [d for d in dirs if d not in [CONSTANTS.PROJECT_VERSIONS_DIR_NAME, ".build", "__pycache__"]]
            
            for file in files:
                if file == CONSTANTS.PROJECT_INFO_FILE or file.endswith(".pyc"):
                    continue
                    
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, target_dir)
                zip_file.write(full_path, rel_path)
                
    zip_buffer.seek(0)
    return zip_buffer


def _resolve_project_target_dir(
    project_name: str,
    project_path: str = None,
    project_context_path: str = None,
) -> str:
    """Resolve a project directory from either a base path or an explicit context path."""
    if project_context_path is not None:
        return os.fspath(project_context_path)

    if project_path is None:
        project_path = _get_project_base_path()

    safe_name = os.path.basename(project_name)
    return os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)


def get_project_file_tree(
    project_name: str,
    project_path: str = None,
    project_context_path: str = None,
) -> list:
    """
    Returns a recursive file tree structure for the project.
    """
    target_dir = _resolve_project_target_dir(project_name, project_path, project_context_path)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
        
    def build_tree(current_path, rel_base):
        items = []
        try:
            entries = sorted(os.listdir(current_path))
        except OSError:
            return []
            
        for entry in entries:
            # Skip hidden/internal folders
            if entry.startswith(".") or entry in [CONSTANTS.PROJECT_VERSIONS_DIR_NAME, "__pycache__"]:
                continue
            if entry == CONSTANTS.PROJECT_INFO_FILE:
                continue
                
            full_path = os.path.join(current_path, entry)
            rel_path = os.path.join(rel_base, entry).replace("\\", "/") # force posix path for API
            if os.path.isfile(full_path) and _is_sensitive_project_file(rel_path):
                continue
            
            item = {
                "name": entry,
                "path": rel_path
            }
            
            if os.path.isdir(full_path):
                item["type"] = "directory"
                item["children"] = build_tree(full_path, rel_path)
            else:
                item["type"] = "file"
                item["size"] = os.path.getsize(full_path)
                
            items.append(item)
        return items

    return build_tree(target_dir, "")


def get_project_file_content(
    project_name: str,
    relative_path: str,
    project_path: str = None,
    project_context_path: str = None,
) -> dict:
    """
    Returns the content of a specific file.
    """
    target_dir = _resolve_project_target_dir(project_name, project_path, project_context_path)
    
    # Security check: prevent directory traversal
    target_file = os.path.abspath(os.path.join(target_dir, relative_path))
    if os.path.commonpath([os.path.abspath(target_dir), target_file]) != os.path.abspath(target_dir):
        raise ValueError("Invalid file path: Traversal attempt detected.")

    if _is_sensitive_project_file(relative_path):
        raise PermissionError(f"Access denied for protected sensitive project file '{relative_path}'.")
        
    if not os.path.exists(target_file):
        raise ValueError(f"File '{relative_path}' not found.")
        
    if os.path.isdir(target_file):
        raise ValueError(f"'{relative_path}' is a directory, not a file.")
        
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        result = {
            "path": relative_path,
            "raw": content
        }
        
        # Try parsing JSON if applicable. Example files keep their source suffix
        # (for example config_credentials.json.example) but still carry JSON.
        if relative_path.endswith(".json") or relative_path.endswith(".json.example"):
            try:
                result["content"] = json.loads(content)
            except json.JSONDecodeError:
                pass
                
        return result
    except UnicodeDecodeError:
        raise ValueError("Cannot read binary file as text.")
