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


def _check_setup_deployed(provider: 'AWSProvider') -> None:
    """
    Verify that Setup Layer (Resource Group) is deployed before deploying L1.
    
    L1 depends on Setup Layer for:
    - Resource Group to exist for resource grouping
    - Tags to be properly configured
    
    Raises:
        ValueError: If Setup Layer Resource Group is not deployed
    """
    from .layer_setup_aws import check_resource_group
    
    if check_resource_group(provider):
        logger.info("[L1] ✓ Pre-flight check: Setup Layer Resource Group exists")
        return
    else:
        raise ValueError(
            "[L1] Pre-flight check FAILED: Setup Layer Resource Group is NOT deployed. "
            "Deploy Setup Layer first using deploy_setup()."
        )


def _check_l0_deployed(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Verify that L0 (Glue Layer) is deployed before deploying L1.
    
    L1 depends on L0 for:
    - Ingestion Function URL (if L1 != L2)
    - Inter-cloud token configuration
    
    Raises:
        ValueError: If multi-cloud mode and L0 Ingestion is not deployed
    """
    from .layer_0_glue import check_ingestion_lambda_function
    
    providers = context.config.providers
    l1_provider = providers["layer_1_provider"]
    l2_provider = providers["layer_2_provider"]
    
    # If single-cloud (L1 == L2), no L0 dependency
    if l1_provider == l2_provider:
        logger.info("[L1] ✓ Pre-flight check: Single-cloud mode, L0 not required")
        return
    
    # Multi-cloud: Check if Ingestion is deployed
    if check_ingestion_lambda_function(provider):
        logger.info("[L1] ✓ Pre-flight check: L0 Ingestion is deployed")
        return
    else:
        raise ValueError(
            f"[L1] Pre-flight check FAILED: L0 Ingestion is NOT deployed. "
            f"Deploy L0 first (L1={l1_provider} requires Ingestion on L2={l2_provider})."
        )


def deploy_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 1 (Data Acquisition) components for AWS.
    
    Creates:
        1. Dispatcher IAM Role
        2. Dispatcher Lambda Function
        3. IoT Topic Rule
        4. IoT Things (per device)
        5. Connector Lambda (if L2 is on different cloud)
    
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
    
    # Pre-flight check: Verify Setup Layer is deployed
    _check_setup_deployed(provider)
    
    # Pre-flight check: Verify L0 is deployed (raises ValueError if multi-cloud dependency missing)
    _check_l0_deployed(context, provider)
    
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
    
    # 5. Connector Lambda (multi-cloud: L1 != L2)
    # NOTE: No fallbacks - missing provider config is a critical error
    l1_provider = context.config.providers["layer_1_provider"]
    l2_provider = context.config.providers["layer_2_provider"]
    
    if l1_provider != l2_provider and context.config.iot_devices:
        from .layer_1_iot import create_connector_iam_role, create_connector_lambda_function
        import json
        import os
        
        logger.info(f"[L1] Multi-cloud detected (L1={l1_provider}, L2={l2_provider}). Deploying Connector Lambdas...")
        
        # Read inter-cloud config for remote Ingestion URL and token
        inter_cloud_path = os.path.join(str(context.project_path), "config_inter_cloud.json")
        if os.path.exists(inter_cloud_path):
            with open(inter_cloud_path, "r") as f:
                inter_cloud_config = json.load(f)
        else:
            inter_cloud_config = {"connections": {}}
        
        conn_id = f"{l1_provider}_l1_to_{l2_provider}_l2"
        conn = inter_cloud_config.get("connections", {}).get(conn_id, {})
        remote_url = conn.get("url", "")
        token = conn.get("token", "")
        
        if not remote_url or not token:
            raise ValueError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(remote_url)}, token={bool(token)}. "
                f"Ensure L2 is deployed first and config_inter_cloud.json is populated with connection '{conn_id}'."
            )
        
        import time
        for device in context.config.iot_devices:
            create_connector_iam_role(device, provider)
        
        logger.info("[L1] Waiting for IAM propagation...")
        time.sleep(20)
        
        for device in context.config.iot_devices:
            create_connector_lambda_function(
                device, provider, context.config, str(context.project_path),
                remote_ingestion_url=remote_url,
                inter_cloud_token=token
            )
    
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
        destroy_iot_thing,
        destroy_connector_lambda_function,
        destroy_connector_iam_role,
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
        
        # Also try to destroy Connector components (may not exist if single-cloud)
        logger.info("[L1] Destroying Connector Lambdas (if any)...")
        for device in context.config.iot_devices:
            destroy_connector_lambda_function(device, provider)
            destroy_connector_iam_role(device, provider)
    
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
