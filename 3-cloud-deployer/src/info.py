"""
Info - Infrastructure Status Checks.

This module provides status check functions to verify deployed resources
across all layers and providers.

All functions require the context parameter.
"""

from logger import logger
from types import SimpleNamespace
from typing import Union, Optional, TYPE_CHECKING
import src.providers.deployer as deployer

if TYPE_CHECKING:
    from core.context import ProjectConfig, DeploymentContext
else:
    ProjectConfig = object # Forward ref placeholder if needed at runtime/circular

def _get_provider_instance(provider_name: str, context: Optional['DeploymentContext']):
    if context and context.providers and provider_name in context.providers:
        return context.providers[provider_name]
    return None


def check_l1(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 1 (IoT) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    if context:
        deployer.info_l1(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check_l2(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 2 (Compute) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    if context:
        deployer.info_l2(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check_l3_hot(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 3 Hot (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    if context:
        deployer.info_l3_hot(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check_l3_cold(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 3 Cold (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
        
    if context:
        deployer.info_l3_cold(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check_l3_archive(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 3 Archive (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    if context:
        deployer.info_l3_archive(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check_l3(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check all Layer 3 (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
        
    if context:
        deployer.info_l3(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check_l4(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 4 (TwinMaker) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    if context:
        deployer.info_l4(context, provider)
    else:
         raise ValueError("Context is required for info checks.")


def check_l5(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Check Layer 5 (Grafana) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
        
    if context:
        deployer.info_l5(context, provider)
    else:
        raise ValueError("Context is required for info checks.")


def check(provider: str = None, config: Union[dict, 'ProjectConfig'] = None, context: Optional['DeploymentContext'] = None):
    """Run all checks for the specified provider."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    if context is None:
         raise ValueError("Context is required for info checks.")
    
    try:
        check_l1(provider, config, context)
        check_l2(provider, config, context)
        check_l3(provider, config, context)
        check_l4(provider, config, context)
        check_l5(provider, config, context)
    except Exception as e:
        logger.error(f"Error during info/check: {str(e)}")
        raise