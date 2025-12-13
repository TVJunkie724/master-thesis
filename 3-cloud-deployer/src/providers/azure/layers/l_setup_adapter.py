"""
Azure Setup Layer Adapter - Orchestration Logic.

This module orchestrates the deployment of foundational Azure resources
in the correct order. It mirrors the AWS `l0_adapter.py` pattern.

Deployment Order:
    1. Resource Group (container for everything)
    2. Managed Identity (shared identity for Function Apps)
    3. Storage Account (required for Function App deployments)

Destruction Order (reverse):
    1. Storage Account
    2. Managed Identity
    3. Resource Group (deletes everything remaining)

Note:
    This layer runs BEFORE L0 and is ALWAYS executed for Azure deployments,
    regardless of multi-cloud boundaries.
"""

from typing import TYPE_CHECKING
import logging

from src.providers.azure.layers.layer_setup_azure import (
    create_resource_group,
    destroy_resource_group,
    check_resource_group,
    create_managed_identity,
    destroy_managed_identity,
    check_managed_identity,
    create_storage_account,
    destroy_storage_account,
    check_storage_account,
)

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


def deploy_setup(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy all foundational Azure resources for the digital twin.
    
    This function MUST be called before any other Azure layer deployment.
    It creates resources in the correct dependency order.
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance with initialized clients
    
    Deployment Order:
        1. Resource Group
        2. Managed Identity
        3. Storage Account
    """
    twin_name = context.config.digital_twin_name
    logger.info(f"========== Azure Setup Layer: {twin_name} ==========")
    
    # Location is always set when provider is initialized
    location = provider.location
    
    # 1. Create Resource Group (must be first)
    logger.info("Step 1/3: Creating Resource Group...")
    create_resource_group(provider, location=location)
    
    # 2. Create Managed Identity
    logger.info("Step 2/3: Creating Managed Identity...")
    identity_info = create_managed_identity(provider)
    
    # Store identity info for later use by other layers
    if not hasattr(context, 'azure_identity'):
        context.azure_identity = {}
    context.azure_identity = identity_info
    
    # 3. Create Storage Account
    logger.info("Step 3/3: Creating Storage Account...")
    create_storage_account(provider)
    
    logger.info(f"========== Azure Setup Layer Complete: {twin_name} ==========")


def destroy_setup(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy all foundational Azure resources.
    
    Resources are destroyed in reverse order. The Resource Group deletion
    at the end will clean up any remaining resources.
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance
    
    Destruction Order:
        1. Storage Account
        2. Managed Identity
        3. Resource Group (final cleanup)
    """
    twin_name = context.config.digital_twin_name
    logger.info(f"========== Destroying Azure Setup Layer: {twin_name} ==========")
    
    # 1. Destroy Storage Account
    logger.info("Step 1/3: Deleting Storage Account...")
    destroy_storage_account(provider)
    
    # 2. Destroy Managed Identity
    logger.info("Step 2/3: Deleting Managed Identity...")
    destroy_managed_identity(provider)
    
    # 3. Destroy Resource Group (final cleanup)
    # This will delete any resources that weren't explicitly destroyed
    logger.info("Step 3/3: Deleting Resource Group...")
    destroy_resource_group(provider)
    
    logger.info(f"========== Azure Setup Layer Destroyed: {twin_name} ==========")


def info_setup(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Get status information for all setup layer resources.
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance
    
    Returns:
        Dictionary with status of each resource:
        {
            "resource_group": bool,
            "managed_identity": bool,
            "storage_account": bool
        }
    """
    twin_name = context.config.digital_twin_name
    logger.info(f"========== Azure Setup Layer Info: {twin_name} ==========")
    
    status = {
        "resource_group": check_resource_group(provider),
        "managed_identity": check_managed_identity(provider),
        "storage_account": check_storage_account(provider),
    }
    
    # Summary
    all_exist = all(status.values())
    if all_exist:
        logger.info("✓ All Setup Layer resources exist")
    else:
        missing = [k for k, v in status.items() if not v]
        logger.info(f"✗ Missing resources: {', '.join(missing)}")
    
    return status
