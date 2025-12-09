"""
Layer 4 (TwinMaker) Adapter for AWS.

This module provides context-based wrappers around the Layer 4
deployment functions, passing provider explicitly.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 4 (Digital Twin) components for AWS.
    
    Creates:
        1. TwinMaker S3 Bucket
        2. TwinMaker IAM Role
        3. TwinMaker Workspace
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_4_twinmaker import (
        create_twinmaker_s3_bucket,
        create_twinmaker_iam_role,
        create_twinmaker_workspace,
        create_twinmaker_hierarchy,
    )
    
    logger.info(f"[L4] Deploying Layer 4 (TwinMaker) for {context.config.digital_twin_name}")
    context.set_active_layer(4)
    
    create_twinmaker_s3_bucket(provider)
    create_twinmaker_iam_role(provider)
    create_twinmaker_workspace(provider)

    if context.config.iot_devices:
        from .layer_4_twinmaker import create_twinmaker_component_type
        logger.info("[L4] Creating TwinMaker Component Types...")
        for device in context.config.iot_devices:
             create_twinmaker_component_type(device, provider)
    
    if context.config.twinmaker_hierarchy:
        logger.info("[L4] Creating TwinMaker Hierarchy...")
        create_twinmaker_hierarchy(provider, context.config.twinmaker_hierarchy, context.config)
    
    logger.info(f"[L4] Layer 4 deployment complete")


def destroy_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 4 (Digital Twin) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_4_twinmaker import (
        destroy_twinmaker_workspace,
        destroy_twinmaker_iam_role,
        destroy_twinmaker_s3_bucket,
        destroy_twinmaker_hierarchy,
        destroy_twinmaker_component_type,
    )
    
    logger.info(f"[L4] Destroying Layer 4 (TwinMaker) for {context.config.digital_twin_name}")
    context.set_active_layer(4)
    
    if context.config.twinmaker_hierarchy:
        destroy_twinmaker_hierarchy(provider, context.config.twinmaker_hierarchy)
    
    if context.config.iot_devices:
        logger.info("[L4] Destroying TwinMaker Component Types...")
        for device in context.config.iot_devices:
             destroy_twinmaker_component_type(device, provider)

    destroy_twinmaker_workspace(provider)
    destroy_twinmaker_iam_role(provider)
    destroy_twinmaker_s3_bucket(provider)
    
    logger.info(f"[L4] Layer 4 destruction complete")


def info_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Check status of Layer 4 (Digital Twin) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_4_twinmaker import info_l4 as _info_l4_impl
    
    logger.info(f"[L4] Checking status for {context.config.digital_twin_name}")
    _info_l4_impl(context, provider)
