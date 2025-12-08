"""
Layer 1 (IoT) Adapter for AWS.

This module provides context-based wrappers around the existing Layer 1
deployment functions in src/aws/deployer_layers/layer_1_iot.py.

Migration Strategy:
    This adapter bridges the new context-based pattern with the legacy
    globals-based code. It:
    1. Receives the DeploymentContext
    2. Sets up globals with the context's configuration
    3. Calls the existing deployment functions
    4. Reports progress via the context

Future Work:
    Once all adapters are stable, the underlying layer code can be
    refactored to use context directly, eliminating the globals dependency.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 1 (Data Acquisition) components for AWS.
    
    This adapter sets up the necessary globals state and calls the
    existing deployment functions from layer_1_iot.py.
    
    Creates:
        1. Dispatcher IAM Role
        2. Dispatcher Lambda Function
        3. IoT Topic Rule
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    
    Note:
        This function modifies global state as a bridge to legacy code.
        This is intentional during the migration period.
    """
    # Import globals to set up state for legacy code
    import globals
    import src.aws.globals_aws as globals_aws
    
    # Ensure globals are initialized with context's project
    # The existing code expects globals.config to be set
    if globals.config.get("digital_twin_name") != context.config.digital_twin_name:
        logger.warning(
            f"Global config twin name mismatch. "
            f"Expected: {context.config.digital_twin_name}, "
            f"Got: {globals.config.get('digital_twin_name')}"
        )
    
    # Import and call existing functions
    from src.aws.deployer_layers.layer_1_iot import (
        create_dispatcher_iam_role,
        create_dispatcher_lambda_function,
        create_dispatcher_iot_rule,
    )
    
    logger.info(f"[L1] Deploying Layer 1 (IoT) for {context.config.digital_twin_name}")
    
    # Set active layer for tracking
    context.set_active_layer(1)
    
    # Deploy in order
    create_dispatcher_iam_role()
    create_dispatcher_lambda_function()
    create_dispatcher_iot_rule()
    
    logger.info(f"[L1] Layer 1 deployment complete")


def destroy_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 1 (Data Acquisition) components for AWS.
    
    Removes resources in reverse order:
        1. IoT Topic Rule
        2. Dispatcher Lambda Function
        3. Dispatcher IAM Role
    
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
    
    # Destroy in reverse order
    destroy_dispatcher_iot_rule()
    destroy_dispatcher_lambda_function()
    destroy_dispatcher_iam_role()
    
    logger.info(f"[L1] Layer 1 destruction complete")
