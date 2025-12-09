"""
Context Factory - Creates Deployment contexts.

This module provides factory functions to create DeploymentContext objects,
handling configuration loading, credential loading, and provider initialization.
It serves as the entry point for both CLI and API to establish a session.

Moves dependency injection logic out of main.py to be reusable.
"""

from pathlib import Path
from logger import logger
from core.config_loader import load_project_config, load_credentials, get_required_providers
from core.context import DeploymentContext
from core.registry import ProviderRegistry
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
    Create a DeploymentContext for a project.
    
    Args:
        project_name: Name of the project
        provider_name: Optional provider to initialize (e.g., "aws")
        
    Returns:
        Initialized DeploymentContext
    """
    project_path = get_upload_path(project_name)
    
    # Load configuration
    config = load_project_config(project_path)
    credentials = load_credentials(project_path)
    
    # Create context
    context = DeploymentContext(
        project_name=project_name,
        project_path=project_path,
        config=config,
    )
    
    # Initialize required providers
    required = get_required_providers(config) if provider_name is None else {provider_name}
    
    for prov_name in required:
        try:
            # Skip if provider name is NONE or empty
            if not prov_name or prov_name.upper() == "NONE":
                continue
                
            provider = ProviderRegistry.get(prov_name)
            creds = credentials.get(prov_name, {})
            
            # AWS can use env vars, so we initialize even if creds dict is empty
            if creds or prov_name == "aws": 
                provider.initialize_clients(creds, config.digital_twin_name)
                context.providers[prov_name] = provider
                
        except Exception as e:
            logger.warning(f"Could not initialize {prov_name} provider: {e}")
    
    return context
