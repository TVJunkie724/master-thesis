"""
Layer 1 (IoT) Adapter for AWS.

This module provides context-based wrappers around the existing Layer 1
deployment functions in src/aws/deployer_layers/layer_1_iot.py.

Note:
    The underlying layer code still uses globals internally.
    This adapter provides the context-based interface while legacy
    code is gradually migrated.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 1 (Data Acquisition) components for AWS.
    
    Creates:
        1. Dispatcher IAM Role
        2. Dispatcher Lambda Function
        3. IoT Topic Rule
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    # Import layer functions (they still use globals internally)
    from src.aws.deployer_layers.layer_1_iot import (
        create_dispatcher_iam_role,
        create_dispatcher_lambda_function,
        create_dispatcher_iot_rule,
    )
    
    logger.info(f"[L1] Deploying Layer 1 (IoT) for {context.config.digital_twin_name}")
    context.set_active_layer(1)
    
    create_dispatcher_iam_role()
    create_dispatcher_lambda_function()
    create_dispatcher_iot_rule()
    
    logger.info(f"[L1] Layer 1 deployment complete")


def destroy_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 1 (Data Acquisition) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.aws.deployer_layers.layer_1_iot import (
        destroy_dispatcher_iot_rule,
        destroy_dispatcher_lambda_function,
        destroy_dispatcher_iam_role,
    )
    
    logger.info(f"[L1] Destroying Layer 1 (IoT) for {context.config.digital_twin_name}")
    context.set_active_layer(1)
    
    destroy_dispatcher_iot_rule()
    destroy_dispatcher_lambda_function()
    destroy_dispatcher_iam_role()
    
    logger.info(f"[L1] Layer 1 destruction complete")

