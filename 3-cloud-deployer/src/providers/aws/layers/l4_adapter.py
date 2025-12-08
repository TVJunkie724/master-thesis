"""
Layer 4 (TwinMaker) Adapter for AWS.

This module provides context-based wrappers around the existing Layer 4
deployment functions in src/aws/deployer_layers/layer_4_twinmaker.py.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 4 (Twin Management) components for AWS.
    
    Creates:
        1. TwinMaker S3 Bucket (for 3D models)
        2. TwinMaker IAM Role
        3. TwinMaker Workspace
    
    Note:
        Entity and component creation is handled by iot_deployer separately,
        as it depends on the IoT device configuration.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.aws.deployer_layers.layer_4_twinmaker import (
        create_twinmaker_s3_bucket,
        create_twinmaker_iam_role,
        create_twinmaker_workspace,
    )
    
    logger.info(f"[L4] Deploying Layer 4 (TwinMaker) for {context.config.digital_twin_name}")
    context.set_active_layer(4)
    
    create_twinmaker_s3_bucket()
    create_twinmaker_iam_role()
    create_twinmaker_workspace()
    
    logger.info(f"[L4] Layer 4 deployment complete")


def destroy_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 4 (Twin Management) components.
    
    Note:
        This destroys the workspace and its contents. Entity and component
        destruction should happen before this via iot_deployer.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.aws.deployer_layers.layer_4_twinmaker import (
        destroy_twinmaker_workspace,
        destroy_twinmaker_iam_role,
        destroy_twinmaker_s3_bucket,
    )
    
    logger.info(f"[L4] Destroying Layer 4 (TwinMaker) for {context.config.digital_twin_name}")
    context.set_active_layer(4)
    
    destroy_twinmaker_workspace()
    destroy_twinmaker_iam_role()
    destroy_twinmaker_s3_bucket()
    
    logger.info(f"[L4] Layer 4 destruction complete")
