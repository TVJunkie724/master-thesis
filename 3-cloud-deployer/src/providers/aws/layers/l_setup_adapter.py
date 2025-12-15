"""
AWS Setup Layer Adapter - Orchestration Logic.

This module orchestrates the deployment of foundational AWS resources
in the correct order. It mirrors the Azure `l_setup_adapter.py` pattern.

Deployment Order:
    1. Resource Group (tag-based query for all twin resources)

Destruction Order (reverse):
    1. Resource Group

Note:
    Unlike Azure where the Resource Group is a container that holds resources,
    AWS Resource Groups are logical views based on tags. Deleting the Resource
    Group does NOT delete the resources - they must be deleted via their
    respective layer destroy functions.
"""

from typing import TYPE_CHECKING
import logging

from src.providers.aws.layers.layer_setup_aws import (
    create_resource_group,
    destroy_resource_group,
    check_resource_group,
)

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.providers.aws.provider import AWSProvider

logger = logging.getLogger(__name__)


def deploy_setup(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy all foundational AWS resources for the digital twin.
    
    This function should be called before any other AWS layer deployment.
    It creates the Resource Group that will contain references to all
    subsequently deployed resources (via tags).
    
    Args:
        context: Deployment context with configuration
        provider: AWS Provider instance with initialized clients
    
    Deployment Order:
        1. Resource Group
    """
    if provider is None:
        raise ValueError("provider is required")
    if context is None:
        raise ValueError("context is required")
    
    twin_name = context.config.digital_twin_name
    logger.info(f"========== AWS Setup Layer: {twin_name} ==========")
    
    # 1. Create Resource Group
    logger.info("Step 1/1: Creating Resource Group...")
    create_resource_group(provider)
    
    logger.info(f"========== AWS Setup Layer Complete: {twin_name} ==========")


def destroy_setup(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy all foundational AWS resources.
    
    Note:
        Deleting the Resource Group does NOT delete the resources within it.
        Resources are deleted by their respective layer destroy functions.
    
    Args:
        context: Deployment context with configuration
        provider: AWS Provider instance
    
    Destruction Order:
        1. Resource Group
    """
    if provider is None:
        raise ValueError("provider is required")
    if context is None:
        raise ValueError("context is required")
    
    twin_name = context.config.digital_twin_name
    logger.info(f"========== Destroying AWS Setup Layer: {twin_name} ==========")
    
    # 1. Destroy Resource Group
    logger.info("Step 1/1: Deleting Resource Group...")
    destroy_resource_group(provider)
    
    logger.info(f"========== AWS Setup Layer Destroyed: {twin_name} ==========")


def info_setup(context: 'DeploymentContext', provider: 'AWSProvider') -> dict:
    """
    Get status information for all setup layer resources.
    
    Args:
        context: Deployment context with configuration
        provider: AWS Provider instance
    
    Returns:
        Dictionary with status of each resource:
        {
            "resource_group": bool
        }
    """
    if provider is None:
        raise ValueError("provider is required")
    if context is None:
        raise ValueError("context is required")
    
    twin_name = context.config.digital_twin_name
    logger.info(f"========== AWS Setup Layer Info: {twin_name} ==========")
    
    status = {
        "resource_group": check_resource_group(provider),
    }
    
    # Summary
    all_exist = all(status.values())
    if all_exist:
        logger.info("✓ All Setup Layer resources exist")
    else:
        missing = [k for k, v in status.items() if not v]
        logger.info(f"✗ Missing resources: {', '.join(missing)}")
    
    return status
