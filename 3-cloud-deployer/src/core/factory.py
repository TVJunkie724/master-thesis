"""
Context Factory - Creates Deployment contexts.

This module provides factory functions to create DeploymentContext objects,
handling configuration loading. Provider initialization is handled separately
by TerraformDeployerStrategy._initialize_providers() at deployment time.

It serves as the entry point for both CLI and API to establish a session.
"""

from pathlib import Path

from core.config_loader import load_deployment_manifest, load_project_config
from core.context import DeploymentContext
from core.paths import get_project_root, resolve_deployment_paths, resolve_project_context_path

def get_project_path() -> Path:
    """Get the project root path."""
    return get_project_root()

def get_upload_path(project_name: str) -> Path:
    """Get the upload path for a project."""
    return resolve_deployment_paths(project_name).project_path

def create_context(
    project_name: str,
    provider_name: str = None,
    *,
    operation_id: str | None = None,
) -> DeploymentContext:
    """
    Create a lightweight DeploymentContext for a project.
    
    Note: This creates a context WITHOUT initialized providers.
    Provider initialization is handled by TerraformDeployerStrategy._initialize_providers()
    at deployment time, which knows exactly which providers are needed based on
    the actual layer configuration.
    
    Args:
        project_name: Name of the project
        provider_name: Optional (unused, kept for API compatibility)
        operation_id: Optional request/deployment correlation id
        
    Returns:
        DeploymentContext with config loaded but providers not yet initialized
    """
    project_path = resolve_project_context_path(project_name)
    
    # Load configuration
    config = load_project_config(project_path)
    deployment_manifest = load_deployment_manifest(project_path)
    
    # Create lightweight context (providers initialized later by deployer strategy)
    context = DeploymentContext(
        project_name=project_name,
        project_path=project_path,
        operation_id=operation_id,
        requested_provider=provider_name,
        config=config,
        deployment_manifest=deployment_manifest,
    )
    context.validate_manifest_identity()
    
    return context
