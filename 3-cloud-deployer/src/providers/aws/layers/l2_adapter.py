"""
Layer 2 (Compute) Adapter for AWS.

This module provides context-based wrappers around the Layer 2
deployment functions, passing provider and config explicitly.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l2(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 2 (Data Processing) components for AWS.
    
    Creates:
        1. Persister IAM Role and Lambda Function
        2. Processors (one per device type)
        3. Event Checker Infrastructure (optional)
        4. Event Actions (dynamic)
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_2_compute import (
        create_persister_iam_role,
        create_persister_lambda_function,
        create_event_checker_iam_role,
        create_event_checker_lambda_function,
        create_lambda_chain_iam_role,
        create_lambda_chain_step_function,
        create_event_feedback_iam_role,
        create_event_feedback_lambda_function,
        create_processor_iam_role,
        create_processor_lambda_function,
        deploy_lambda_actions,
        # Multi-cloud: Ingestion
        create_ingestion_iam_role,
        create_ingestion_lambda_function,
    )
    
    logger.info(f"[L2] Deploying Layer 2 (Compute) for {context.config.digital_twin_name}")
    context.set_active_layer(2)
    
    # Path to tool source code (where core lambdas live)
    # Assuming standard structure: tool_root/src/providers/aws/lambda_functions
    tool_root = str(context.project_path.parent.parent)
    
    # Path to user project (where config and custom lambdas live)
    user_project_root = str(context.project_path)
    
    # 1. Persister (Core)
    create_persister_iam_role(provider)
    create_persister_lambda_function(provider, context.config, tool_root)

    # 2. Processors
    if context.config.iot_devices:
        for device in context.config.iot_devices:
            create_processor_iam_role(device, provider)
            create_processor_lambda_function(device, provider, context.config, tool_root)

    # 3. Event Checker (Optional)
    if context.config.is_optimization_enabled("useEventChecking"):
        logger.info("[L2] Deploying Event Checking infrastructure...")
        create_event_checker_iam_role(provider)
        
        # Dependencies
        if context.config.is_optimization_enabled("triggerNotificationWorkflow"):
            create_lambda_chain_iam_role(provider)
            create_lambda_chain_step_function(provider, user_project_root)
            
        if context.config.is_optimization_enabled("returnFeedbackToDevice"):
            create_event_feedback_iam_role(provider)
            create_event_feedback_lambda_function(provider, context.config, tool_root)
            
        create_event_checker_lambda_function(provider, context.config, tool_root)

    # 4. Event Actions (Dynamic)
    if context.config.events:
        logger.info("[L2] Deploying Event Action Lambdas...")
        deploy_lambda_actions(provider, context.config, user_project_root)

    # NOTE: Ingestion (multi-cloud L1→L2 receiver) is now deployed by L0 adapter

    logger.info(f"[L2] Layer 2 deployment complete")


def destroy_l2(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 2 (Data Processing) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_2_compute import (
        destroy_persister_lambda_function,
        destroy_persister_iam_role,
        destroy_event_checker_lambda_function,
        destroy_event_checker_iam_role,
        destroy_lambda_chain_step_function,
        destroy_lambda_chain_iam_role,
        destroy_event_feedback_lambda_function,
        destroy_event_feedback_iam_role,
        destroy_processor_lambda_function,
        destroy_processor_iam_role,
        destroy_lambda_actions,
        # Multi-cloud: Ingestion
        destroy_ingestion_lambda_function,
        destroy_ingestion_iam_role,
    )
    
    logger.info(f"[L2] Destroying Layer 2 (Compute) for {context.config.digital_twin_name}")
    context.set_active_layer(2)
    
    # Destroy in reverse order
    # NOTE: Ingestion (multi-cloud L1→L2 receiver) is now destroyed by L0 adapter
    
    # 4. Event Actions
    if context.config.events:
         destroy_lambda_actions(provider, context.config)

    # 3. Event Checker & Dependencies
    if context.config.is_optimization_enabled("useEventChecking"):
        destroy_event_checker_lambda_function(provider)
        
        if context.config.is_optimization_enabled("returnFeedbackToDevice"):
            destroy_event_feedback_lambda_function(provider)
            destroy_event_feedback_iam_role(provider)
            
        if context.config.is_optimization_enabled("triggerNotificationWorkflow"):
            destroy_lambda_chain_step_function(provider)
            destroy_lambda_chain_iam_role(provider)
            
        destroy_event_checker_iam_role(provider)

    # 2. Processors
    if context.config.iot_devices:
        for device in context.config.iot_devices:
            destroy_processor_lambda_function(device, provider)
            destroy_processor_iam_role(device, provider)

    # 1. Persister
    destroy_persister_lambda_function(provider)
    destroy_persister_iam_role(provider)
    
    logger.info(f"[L2] Layer 2 destruction complete")


def info_l2(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Check status of Layer 2 (Data Processing) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_2_compute import info_l2 as _info_l2_impl
    
    logger.info(f"[L2] Checking status for {context.config.digital_twin_name}")
    _info_l2_impl(context, provider)
