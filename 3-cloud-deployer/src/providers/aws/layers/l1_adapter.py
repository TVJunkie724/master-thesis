"""
Layer 1 (IoT) Adapter for AWS.

This module provides context-based wrappers around the Layer 1
deployment functions, passing provider and config explicitly.
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
    from .layer_1_iot import (
        create_dispatcher_iam_role,
        create_dispatcher_lambda_function,
        create_dispatcher_iot_rule,
        post_init_values_to_iot_core,
    )
    
    logger.info(f"[L1] Deploying Layer 1 (IoT) for {context.config.digital_twin_name}")
    context.set_active_layer(1)
    
    # Pass provider explicitly to each function
    create_dispatcher_iam_role(provider)
    create_dispatcher_lambda_function(provider, context.config, str(context.project_path))
    create_dispatcher_iot_rule(provider, context.config)
    
    # 4. IoT Things
    if context.config.iot_devices:
        from .layer_1_iot import create_iot_thing
        logger.info("[L1] Creating IoT Things...")
        for device in context.config.iot_devices:
            create_iot_thing(device, provider, context.config, str(context.project_path))
    
    # Post init values
    if context.config.iot_devices:
        logger.info("[L1] Posting initial values to IoT Core...")
        post_init_values_to_iot_core(provider, context.config.iot_devices)
    
    logger.info(f"[L1] Layer 1 deployment complete")


def destroy_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 1 (Data Acquisition) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_1_iot import (
        destroy_dispatcher_iot_rule,
        destroy_dispatcher_lambda_function,
        destroy_dispatcher_iam_role,
        destroy_iot_thing, # dynamic import
    )
    
    logger.info(f"[L1] Destroying Layer 1 (IoT) for {context.config.digital_twin_name}")
    context.set_active_layer(1)
    
    # Pass provider explicitly to each function
    destroy_dispatcher_iot_rule(provider)
    destroy_dispatcher_lambda_function(provider)
    destroy_dispatcher_iam_role(provider)
    
    if context.config.iot_devices:
        logger.info("[L1] Destroying IoT Things...")
        for device in context.config.iot_devices:
            destroy_iot_thing(device, provider, str(context.project_path))
    
    logger.info(f"[L1] Layer 1 destruction complete")


def info_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Check status of Layer 1 (Data Acquisition) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_1_iot import info_l1 as _info_l1_impl
    
    logger.info(f"[L1] Checking status for {context.config.digital_twin_name}")
    _info_l1_impl(context, provider)
