"""
Layer 5 (Grafana) Adapter for AWS.

This module provides context-based wrappers around the Layer 5
deployment functions, passing provider explicitly.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l5(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 5 (Visualization) components for AWS.
    
    Creates:
        1. Grafana IAM Role
        2. Amazon Managed Grafana Workspace
        3. CORS configuration for TwinMaker S3 bucket
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_5_grafana import (
        create_grafana_iam_role,
        create_grafana_workspace,
        add_cors_to_twinmaker_s3_bucket,
    )
    
    logger.info(f"[L5] Deploying Layer 5 (Grafana) for {context.config.digital_twin_name}")
    context.set_active_layer(5)
    
    create_grafana_iam_role(provider)
    create_grafana_workspace(provider)
    add_cors_to_twinmaker_s3_bucket(provider)
    
    logger.info(f"[L5] Layer 5 deployment complete")


def destroy_l5(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 5 (Visualization) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_5_grafana import (
        remove_cors_from_twinmaker_s3_bucket,
        destroy_grafana_workspace,
        destroy_grafana_iam_role,
    )
    
    logger.info(f"[L5] Destroying Layer 5 (Grafana) for {context.config.digital_twin_name}")
    context.set_active_layer(5)
    
    remove_cors_from_twinmaker_s3_bucket(provider)
    destroy_grafana_workspace(provider)
    destroy_grafana_iam_role(provider)
    
    logger.info(f"[L5] Layer 5 destruction complete")
