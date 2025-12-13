"""
Azure L1 (IoT/Data Acquisition) Adapter Layer.

This module provides orchestration functions for deploying, destroying,
and checking the status of Layer 1 components.

Functions:
    deploy_l1: Deploy all L1 components in correct order
    destroy_l1: Destroy all L1 components in reverse order
    info_l1: Check status of all L1 components

Deployment Order:
    1. IoT Hub (create first - may take 1-2 minutes)
    2. RBAC Role Assignments (wait 30s for propagation)
    3. L1 App Service Plan (Y1 Consumption)
    4. L1 Function App
    5. Dispatcher Function
    6. Event Grid Subscription
    7. IoT Devices (per config)
    8. Connector Function (if L1 != L2, multi-cloud)

Pre-flight Checks:
    - Verifies Setup Layer is fully deployed
    - Verifies L0 Glue Layer if Azure is L2 provider in multi-cloud

Note:
    This adapter follows the pattern established by l0_adapter.py and
    mirrors the AWS l1_adapter.py structure.
"""

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


def deploy_l1(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 1 (Data Acquisition) components for Azure.
    
    Deploys IoT Hub, Function App, Dispatcher, Event Grid subscription,
    IoT devices, and Connector function (if multi-cloud).
    
    Args:
        context: Deployment context with config and project_path
        provider: Initialized AzureProvider instance
        
    Raises:
        RuntimeError: If Setup Layer not deployed
        ValueError: If required configuration is missing
    """
    from .layer_1_iot import (
        create_iot_hub,
        assign_managed_identity_roles,
        create_l1_app_service_plan,
        create_l1_function_app,
        deploy_dispatcher_function,
        create_event_grid_subscription,
        create_iot_device,
        deploy_connector_function,
    )
    
    config = context.config
    project_path = context.project_path
    
    logger.info(f"========== Azure L1 Layer Deploy: {config.digital_twin_name} ==========")
    
    # ==========================================
    # Pre-flight checks
    # ==========================================
    
    # 1. VERIFY SETUP LAYER (simple pass/fail)
    from src.providers.azure.layers.l_setup_adapter import info_setup
    setup_status = info_setup(context, provider)
    
    setup_ok = all([
        setup_status.get("resource_group"),
        setup_status.get("managed_identity"),
        setup_status.get("storage_account")
    ])
    
    if not setup_ok:
        raise RuntimeError(
            "Setup Layer not fully deployed. Run deploy_setup first before deploying L1."
        )
    
    logger.info("✓ Pre-flight check: Setup Layer OK")
    
    # 2. VERIFY L0 GLUE (if multi-cloud and Azure is L2+)
    l1_provider = config.providers.get("layer_1_provider", "azure")
    l2_provider = config.providers.get("layer_2_provider", "azure")
    
    if l1_provider != l2_provider and l2_provider == "azure":
        from src.providers.azure.layers.l0_adapter import info_l0
        l0_status = info_l0(context, provider)
        
        l0_ok = l0_status.get("function_app", False)
        
        if not l0_ok:
            raise RuntimeError(
                "L0 Glue Layer not deployed. Run deploy_l0 first (Azure is L2 provider in multi-cloud)."
            )
        
        logger.info("✓ Pre-flight check: L0 Glue Layer OK")
    
    # ==========================================
    # Deploy L1 components
    # ==========================================
    
    # 1. Create IoT Hub (takes 1-2 minutes)
    create_iot_hub(provider)
    
    # 2. Assign RBAC roles to Managed Identity (includes 30s wait)
    assign_managed_identity_roles(provider)
    
    # 3. Create L1 App Service Plan
    create_l1_app_service_plan(provider)
    
    # 4. Create L1 Function App
    create_l1_function_app(provider, config)
    
    # 5. Deploy Dispatcher Function
    deploy_dispatcher_function(provider, project_path)
    
    # 6. Create Event Grid Subscription
    create_event_grid_subscription(provider, config)
    
    # 7. Create IoT Devices
    if config.iot_devices:
        logger.info(f"Creating {len(config.iot_devices)} IoT devices...")
        for device in config.iot_devices:
            create_iot_device(device, provider, config, project_path)
    
    # 8. Deploy Connector Function (if multi-cloud, L1 != L2)
    if l1_provider != l2_provider and l1_provider == "azure":
        logger.info("Multi-cloud detected: Azure L1 → different L2 provider")
        
        # Load inter-cloud config for remote ingestion URL and token
        import os
        import json
        inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
        
        if os.path.exists(inter_cloud_path):
            with open(inter_cloud_path, "r") as f:
                inter_cloud_config = json.load(f)
            
            remote_ingestion_url = inter_cloud_config.get("L2_boundary", {}).get("endpoint_url", "")
            inter_cloud_token = inter_cloud_config.get("L2_boundary", {}).get("inter_cloud_token", "")
            
            if remote_ingestion_url and inter_cloud_token:
                deploy_connector_function(
                    provider, config, project_path,
                    remote_ingestion_url, inter_cloud_token
                )
            else:
                logger.warning("Missing remote URL or token in config_inter_cloud.json for connector")
        else:
            logger.warning(f"config_inter_cloud.json not found at {inter_cloud_path}")
    
    logger.info(f"========== Azure L1 Layer Deploy Complete ==========")


def destroy_l1(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy all L1 (Data Acquisition) components for Azure.
    
    Destroys components in reverse order to respect dependencies:
    Connector → IoT Devices → Event Grid → Dispatcher → Function App → 
    App Service Plan → RBAC Roles → IoT Hub
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
    """
    from .layer_1_iot import (
        destroy_iot_hub,
        destroy_managed_identity_roles,
        destroy_l1_app_service_plan,
        destroy_l1_function_app,
        destroy_dispatcher_function,
        destroy_event_grid_subscription,
        destroy_iot_device,
        destroy_connector_function,
    )
    
    config = context.config
    
    logger.info(f"========== Azure L1 Layer Destroy: {config.digital_twin_name} ==========")
    
    # Check if multi-cloud (Azure is L1)
    l1_provider = config.providers.get("layer_1_provider", "azure")
    l2_provider = config.providers.get("layer_2_provider", "azure")
    
    # Destroy in reverse order
    
    # 8. Connector Function (if deployed)
    if l1_provider != l2_provider and l1_provider == "azure":
        destroy_connector_function(provider)
    
    # 7. IoT Devices
    if config.iot_devices:
        for device in config.iot_devices:
            destroy_iot_device(device, provider)
    
    # 6. Event Grid Subscription
    destroy_event_grid_subscription(provider)
    
    # 5. Dispatcher Function
    destroy_dispatcher_function(provider)
    
    # 4. L1 Function App
    destroy_l1_function_app(provider)
    
    # 3. L1 App Service Plan
    destroy_l1_app_service_plan(provider)
    
    # 2. RBAC Role Assignments
    destroy_managed_identity_roles(provider)
    
    # 1. IoT Hub
    destroy_iot_hub(provider)
    
    logger.info(f"========== Azure L1 Layer Destroy Complete ==========")


def info_l1(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Check status of all L1 (Data Acquisition) components.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with component status:
            - iot_hub: bool
            - rbac_roles: bool
            - app_service_plan: bool
            - function_app: bool
            - dispatcher_function: bool
            - event_grid_subscription: bool
            - devices: dict of device_id -> bool
            - connector_function: bool (if multi-cloud)
    """
    from .layer_1_iot import info_l1 as _info_l1_impl
    
    config = context.config
    
    logger.info(f"[L1] Checking Azure L1 status for {config.digital_twin_name}")
    
    return _info_l1_impl(context, provider)
