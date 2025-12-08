"""
Layer 5 (Grafana) Adapter for AWS.

This module provides context-based wrappers around the existing Layer 5
deployment functions in src/aws/deployer_layers/layer_5_grafana.py.
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
        2. Grafana Workspace (Amazon Managed Grafana)
    
    Note:
        Dashboard configuration is a manual step after workspace creation.
        The TwinMaker data source plugin must be configured in Grafana.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.aws.deployer_layers.layer_5_grafana import (
        create_grafana_iam_role,
        create_grafana_workspace,
    )
    
    logger.info(f"[L5] Deploying Layer 5 (Grafana) for {context.config.digital_twin_name}")
    context.set_active_layer(5)
    
    create_grafana_iam_role()
    create_grafana_workspace()
    
    logger.info(f"[L5] Layer 5 deployment complete")


def destroy_l5(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 5 (Visualization) components.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.aws.deployer_layers.layer_5_grafana import (
        destroy_grafana_workspace,
        destroy_grafana_iam_role,
    )
    
    logger.info(f"[L5] Destroying Layer 5 (Grafana) for {context.config.digital_twin_name}")
    context.set_active_layer(5)
    
    destroy_grafana_workspace()
    destroy_grafana_iam_role()
    
    logger.info(f"[L5] Layer 5 destruction complete")
