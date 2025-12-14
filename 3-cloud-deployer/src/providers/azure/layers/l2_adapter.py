"""
Layer 2 (Compute) Adapter for Azure.

This module provides context-based wrappers around the Layer 2
deployment functions, passing provider and config explicitly.

Architecture:
    deployer_strategy.deploy_l2()
        → l2_adapter.deploy_l2()
            → layer_2_compute.create_l2_app_service_plan()
            → layer_2_compute.create_l2_function_app()
            → layer_2_compute.deploy_persister_function()
            → layer_2_compute.deploy_processor_function() (per device)
            → layer_2_compute.deploy_event_checker_function() (optional)
            → layer_2_compute.create_logic_app_workflow() (optional)
            → layer_2_compute.deploy_event_feedback_function() (optional)
            → layer_2_compute.deploy_event_action_functions() (dynamic)
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AzureProvider


def _check_l1_deployed(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Verify that L1 (IoT) is deployed before deploying L2.
    
    L2 depends on L1 for:
    - IoT Hub (source of telemetry messages)
    - Function App (Dispatcher invokes Processors)
    
    Raises:
        RuntimeError: If L1 is not fully deployed
    """
    from src.providers.azure.layers.l1_adapter import info_l1
    
    l1_status = info_l1(context, provider)
    
    iot_hub_ok = l1_status.get("iot_hub")
    function_app_ok = l1_status.get("function_app")
    
    if iot_hub_ok and function_app_ok:
        logger.info("✓ Pre-flight check: L1 Layer deployed")
        return
    else:
        missing = []
        if not iot_hub_ok:
            missing.append("IoT Hub")
        if not function_app_ok:
            missing.append("Function App")
        raise RuntimeError(
            f"[L2] Pre-flight check FAILED: L1 Layer not fully deployed. "
            f"Missing: {', '.join(missing)}. Run deploy_l1 first."
        )


def deploy_l2(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 2 (Data Processing) components for Azure.
    
    Creates:
        1. L2 App Service Plan (Y1 Consumption)
        2. L2 Function App
        3. Persister Function
        4. Processor Functions (one per device type)
        5. Event Checker Infrastructure (optional)
        6. Logic Apps Workflow (if triggerNotificationWorkflow enabled)
        7. Event Action Functions (from events config)
    
    Args:
        context: Deployment context with config and project_path
        provider: Initialized AzureProvider instance
        
    Raises:
        RuntimeError: If L1 Layer not deployed
        ValueError: If required configuration is missing
    """
    from .layer_2_compute import (
        create_l2_app_service_plan,
        create_l2_function_app,
        deploy_persister_function,
        deploy_processor_function,
        deploy_event_checker_function,
        deploy_event_feedback_function,
        create_logic_app_workflow,
        deploy_event_action_functions,
    )
    
    config = context.config
    project_path = str(context.project_path)
    
    logger.info(f"========== Azure L2 Layer Deploy: {config.digital_twin_name} ==========")
    
    # ==========================================
    # Pre-flight check (raises on failure)
    # ==========================================
    _check_l1_deployed(context, provider)
    
    # ==========================================
    # Deploy L2 Components
    # ==========================================
    
    # 1. L2 App Service Plan
    create_l2_app_service_plan(provider)
    
    # 2. L2 Function App
    create_l2_function_app(provider, config)
    
    # 3. Persister Function
    deploy_persister_function(provider, project_path)
    
    # 4. Processor Functions (one per device)
    if config.iot_devices:
        logger.info(f"[L2] Deploying {len(config.iot_devices)} Processor function(s)...")
        for device in config.iot_devices:
            deploy_processor_function(device, provider, config, project_path)
    
    # 5. Event Checker (Optional)
    if config.is_optimization_enabled("useEventChecking"):
        logger.info("[L2] Deploying Event Checking infrastructure...")
        deploy_event_checker_function(provider, config, project_path)
        
        # 6. Logic Apps Workflow (if triggerNotificationWorkflow enabled)
        if config.is_optimization_enabled("triggerNotificationWorkflow"):
            create_logic_app_workflow(provider, config)
        
        # 7. Event Feedback (if returnFeedbackToDevice enabled)
        if config.is_optimization_enabled("returnFeedbackToDevice"):
            deploy_event_feedback_function(provider, config, project_path)
    
    # 8. Event Action Functions (Dynamic)
    if config.events:
        logger.info("[L2] Deploying Event Action Functions...")
        deploy_event_action_functions(provider, config, project_path)
    
    logger.info(f"========== Azure L2 Layer Deploy Complete ==========")


def destroy_l2(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy Layer 2 (Data Processing) components for Azure.
    
    Destroys in reverse order:
        1. Event Action Functions
        2. Event Feedback Function
        3. Logic Apps Workflow
        4. Event Checker Function
        5. Processor Functions
        6. Persister Function
        7. L2 Function App
        8. L2 App Service Plan
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
    """
    from .layer_2_compute import (
        destroy_l2_app_service_plan,
        destroy_l2_function_app,
        destroy_persister_function,
        destroy_processor_function,
        destroy_event_checker_function,
        destroy_event_feedback_function,
        destroy_logic_app_workflow,
        destroy_event_action_functions,
    )
    
    config = context.config
    
    logger.info(f"========== Azure L2 Layer Destroy: {config.digital_twin_name} ==========")
    
    # Destroy in reverse order
    
    # 1. Event Action Functions
    if config.events:
        destroy_event_action_functions(provider, config)
    
    # 2. Event Feedback
    if config.is_optimization_enabled("returnFeedbackToDevice"):
        destroy_event_feedback_function(provider)
    
    # 3. Logic Apps Workflow
    if config.is_optimization_enabled("triggerNotificationWorkflow"):
        destroy_logic_app_workflow(provider)
    
    # 4. Event Checker
    if config.is_optimization_enabled("useEventChecking"):
        destroy_event_checker_function(provider)
    
    # 5. Processor Functions
    if config.iot_devices:
        for device in config.iot_devices:
            destroy_processor_function(device, provider)
    
    # 6. Persister Function
    destroy_persister_function(provider)
    
    # 7. L2 Function App
    destroy_l2_function_app(provider)
    
    # 8. L2 App Service Plan
    destroy_l2_app_service_plan(provider)
    
    logger.info(f"========== Azure L2 Layer Destroy Complete ==========")


def info_l2(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Check status of Layer 2 (Data Processing) components for Azure.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of all L2 components
    """
    from .layer_2_compute import info_l2 as _info_l2_impl
    
    logger.info(f"[L2] Checking status for {context.config.digital_twin_name}")
    return _info_l2_impl(context, provider)
