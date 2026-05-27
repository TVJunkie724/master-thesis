
"""Legacy path helpers for Deployer compatibility shims."""

import os


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
