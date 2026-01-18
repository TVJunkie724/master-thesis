"""
Context Factory - Creates Deployment contexts.

This module provides factory functions to create DeploymentContext objects,
handling configuration loading. Provider initialization is handled separately
by TerraformDeployerStrategy._initialize_providers() at deployment time.

It serves as the entry point for both CLI and API to establish a session.
"""

from pathlib import Path
from core.config_loader import load_project_config
from core.context import DeploymentContext
import constants as CONSTANTS

def get_project_path() -> Path:
    """Get the project root path."""
    # Assuming this file is in src/core/, project root is up two levels
    return Path(__file__).parent.parent.parent

def get_upload_path(project_name: str) -> Path:
    """Get the upload path for a project."""
    return get_project_path() / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / project_name

def create_context(project_name: str, provider_name: str = None) -> DeploymentContext:
    """
    Create a lightweight DeploymentContext for a project.
    
    Note: This creates a context WITHOUT initialized providers.
    Provider initialization is handled by TerraformDeployerStrategy._initialize_providers()
    at deployment time, which knows exactly which providers are needed based on
    the actual layer configuration.
    
    Args:
        project_name: Name of the project
        provider_name: Optional (unused, kept for API compatibility)
        
    Returns:
        DeploymentContext with config loaded but providers not yet initialized
    """
    project_path = get_upload_path(project_name)
    
    # Load configuration
    config = load_project_config(project_path)
    
    # Create lightweight context (providers initialized later by deployer strategy)
    context = DeploymentContext(
        project_name=project_name,
        project_path=project_path,
        config=config,
    )
    
    return context

