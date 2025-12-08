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
        2. Event Checker IAM Role and Lambda (if optimization enabled)
        3. Step Function State Machine (if optimization enabled)
        4. Event Feedback Lambda (if optimization enabled)
    
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
    )
    
    logger.info(f"[L2] Deploying Layer 2 (Compute) for {context.config.digital_twin_name}")
    context.set_active_layer(2)
    
    project_path = str(context.project_path.parent.parent)  # Get to src/
    upload_path = str(context.project_path)
    
    # Core components (always deployed)
    create_persister_iam_role(provider)
    create_persister_lambda_function(provider, context.config, project_path)
    
    # Optional event processing (check via context)
    if context.config.is_optimization_enabled("useEventChecking"):
        create_event_checker_iam_role(provider)
        create_event_checker_lambda_function(provider, context.config, project_path)
        
        if context.config.is_optimization_enabled("triggerNotificationWorkflow"):
            create_lambda_chain_iam_role(provider)
            create_lambda_chain_step_function(provider, upload_path)
            create_event_feedback_iam_role(provider)
            create_event_feedback_lambda_function(provider, context.config, upload_path)
    
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
    )
    
    logger.info(f"[L2] Destroying Layer 2 (Compute) for {context.config.digital_twin_name}")
    context.set_active_layer(2)
    
    # Destroy in reverse order (optional components first)
    destroy_event_feedback_lambda_function(provider)
    destroy_event_feedback_iam_role(provider)
    destroy_lambda_chain_step_function(provider)
    destroy_lambda_chain_iam_role(provider)
    destroy_event_checker_lambda_function(provider)
    destroy_event_checker_iam_role(provider)
    
    # Core components
    destroy_persister_lambda_function(provider)
    destroy_persister_iam_role(provider)
    
    logger.info(f"[L2] Layer 2 destruction complete")
