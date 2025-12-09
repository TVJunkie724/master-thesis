
"""
Global State Management

This module manages the runtime state of the application, replacing the legacy `globals.py`.
It handles:
1. Active Project tracking
2. Project Base Path resolution
"""
import os
from logger import logger

# Default values
DEFAULT_PROJECT = "template"
CURRENT_PROJECT = DEFAULT_PROJECT

def get_active_project() -> str:
    """Get the name of the currently active project."""
    return CURRENT_PROJECT

def set_active_project(project_name: str) -> None:
    """
    Set the active project.
    Validates that the project directory exists.
    """
    global CURRENT_PROJECT
    
    # Validation logic to check if project exists
    upload_path = get_project_upload_path()
    project_dir = os.path.join(upload_path, project_name)
    
    if not os.path.exists(project_dir):
        # Allow template to be set even if checks fail (bootstrapping)
        if project_name != "template":
            raise ValueError(f"Project '{project_name}' does not exist at {project_dir}")
            
    CURRENT_PROJECT = project_name
    logger.info(f"Active project set to: {CURRENT_PROJECT}")

def get_project_base_path() -> str:
    """
    Get the base path for the application.
    Prioritizes /app (Docker), then resolves relative to this file.
    """
    # Docker/Container path
    if os.path.exists("/app"):
        return "/app"
        
    # Local path: .../src/core/state.py -> .../src/core -> .../src -> .../
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

def get_project_upload_path() -> str:
    """Get the path to the 'upload' directory."""
    return os.path.join(get_project_base_path(), "upload")

def reset_state():
    """Reset state to defaults (useful for tests)."""
    global CURRENT_PROJECT
    CURRENT_PROJECT = DEFAULT_PROJECT
