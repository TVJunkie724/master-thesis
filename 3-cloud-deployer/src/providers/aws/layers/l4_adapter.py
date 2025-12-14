"""
Layer 4 (TwinMaker) Adapter for AWS.

This module provides context-based wrappers around the Layer 4
deployment functions, passing provider explicitly.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def _check_l3_deployed(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Verify that L3 (Storage) is deployed before deploying L4.
    
    L4 depends on L3 for:
    - DynamoDB Hot Storage (stores twin property data)
    - Hot Reader (for Digital Twin Data Connector)
    
    Raises:
        ValueError: If L3 Hot components are not deployed
    """
    from .layer_3_storage import (
        check_hot_dynamodb_table,
        check_hot_reader_lambda_function,
    )
    
    table_exists = check_hot_dynamodb_table(provider)
    reader_exists = check_hot_reader_lambda_function(provider)
    
    if table_exists and reader_exists:
        logger.info("[L4] ✓ Pre-flight check: L3 Hot is deployed")
        return
    else:
        missing = []
        if not table_exists:
            missing.append("DynamoDB Hot Table")
        if not reader_exists:
            missing.append("Hot Reader Lambda")
        raise ValueError(
            f"[L4] Pre-flight check FAILED: L3 Hot is NOT fully deployed. "
            f"Missing: {', '.join(missing)}. Deploy L3 first."
        )


def deploy_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 4 (Digital Twin) components for AWS.
    
    Creates:
        1. TwinMaker S3 Bucket
        2. TwinMaker IAM Role
        3. TwinMaker Workspace
        4. Digital Twin Data Connector (if L3 is on different cloud)
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_4_twinmaker import (
        create_twinmaker_s3_bucket,
        create_twinmaker_iam_role,
        create_twinmaker_workspace,
        create_twinmaker_hierarchy,
    )
    
    logger.info(f"[L4] Deploying Layer 4 (TwinMaker) for {context.config.digital_twin_name}")
    context.set_active_layer(4)
    
    # Pre-flight check: Verify L3 is deployed (raises ValueError if missing)
    _check_l3_deployed(context, provider)
    
    create_twinmaker_s3_bucket(provider)
    create_twinmaker_iam_role(provider)
    create_twinmaker_workspace(provider)

    if context.config.iot_devices:
        from .layer_4_twinmaker import create_twinmaker_component_type
        logger.info("[L4] Creating TwinMaker Component Types...")
        for device in context.config.iot_devices:
             create_twinmaker_component_type(device, provider)
    
    if context.config.twinmaker_hierarchy:
        logger.info("[L4] Creating TwinMaker Hierarchy...")
        create_twinmaker_hierarchy(provider, context.config.twinmaker_hierarchy, context.config)
    
    # Multi-cloud: Digital Twin Data Connector (when L3 is on different cloud)
    # NOTE: No fallbacks - missing provider config is a critical error
    l3_provider = context.config.providers["layer_3_hot_provider"]
    l4_provider = context.config.providers["layer_4_provider"]
    
    if l3_provider != l4_provider:
        from .layer_3_storage import (
            create_digital_twin_data_connector_iam_role,
            create_digital_twin_data_connector_lambda_function,
            create_digital_twin_data_connector_last_entry_iam_role,
            create_digital_twin_data_connector_last_entry_lambda_function,
        )
        import time
        import os
        import json
        
        logger.info(f"[L4] Multi-cloud: Deploying Digital Twin Data Connector (L3 on {l3_provider}, L4 on {l4_provider})")
        
        # Read inter-cloud config for remote Hot Reader URL and token
        inter_cloud_path = os.path.join(str(context.project_path), "config_inter_cloud.json")
        if os.path.exists(inter_cloud_path):
            with open(inter_cloud_path, "r") as f:
                inter_cloud_config = json.load(f)
        else:
            inter_cloud_config = {"connections": {}}
        
        conn_id = f"{l3_provider}_l3_to_{l4_provider}_l4"
        conn = inter_cloud_config.get("connections", {}).get(conn_id, {})
        remote_url = conn.get("url", "")
        token = conn.get("token", "")
        
        conn_id_last_entry = f"{conn_id}_last_entry"
        conn_last_entry = inter_cloud_config.get("connections", {}).get(conn_id_last_entry, {})
        remote_url_last_entry = conn_last_entry.get("url", "")
        
        if not remote_url or not token:
            raise ValueError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(remote_url)}, token={bool(token)}. "
                f"Ensure L3 is deployed first and config_inter_cloud.json is populated with connection '{conn_id}'."
            )
        
        project_path = str(context.project_path.parent.parent)
        
        create_digital_twin_data_connector_iam_role(provider)
        create_digital_twin_data_connector_last_entry_iam_role(provider)
        
        logger.info("[L4] Waiting for IAM propagation...")
        time.sleep(10)
        
        create_digital_twin_data_connector_lambda_function(
            provider, context.config, project_path,
            remote_hot_reader_url=remote_url,
            inter_cloud_token=token
        )
        create_digital_twin_data_connector_last_entry_lambda_function(
            provider, context.config, project_path,
            remote_hot_reader_url=remote_url_last_entry or remote_url,
            inter_cloud_token=token
        )
        
        logger.info("[L4] Multi-cloud: Digital Twin Data Connector deployed")
    
    logger.info(f"[L4] Layer 4 deployment complete")


def destroy_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 4 (Digital Twin) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_4_twinmaker import (
        destroy_twinmaker_workspace,
        destroy_twinmaker_iam_role,
        destroy_twinmaker_s3_bucket,
        destroy_twinmaker_hierarchy,
        destroy_twinmaker_component_type,
    )
    
    logger.info(f"[L4] Destroying Layer 4 (TwinMaker) for {context.config.digital_twin_name}")
    context.set_active_layer(4)
    
    # Multi-cloud: Digital Twin Data Connector (when L3 is on different cloud)
    # NOTE: No fallbacks - missing provider config is a critical error
    l3_provider = context.config.providers["layer_3_hot_provider"]
    l4_provider = context.config.providers["layer_4_provider"]
    
    if l3_provider != l4_provider:
        from .layer_3_storage import (
            destroy_digital_twin_data_connector_lambda_function,
            destroy_digital_twin_data_connector_iam_role,
            destroy_digital_twin_data_connector_last_entry_lambda_function,
            destroy_digital_twin_data_connector_last_entry_iam_role,
        )
        
        logger.info(f"[L4] Multi-cloud: Destroying Digital Twin Data Connector")
        destroy_digital_twin_data_connector_lambda_function(provider)
        destroy_digital_twin_data_connector_iam_role(provider)
        destroy_digital_twin_data_connector_last_entry_lambda_function(provider)
        destroy_digital_twin_data_connector_last_entry_iam_role(provider)
    
    if context.config.twinmaker_hierarchy:
        destroy_twinmaker_hierarchy(provider, context.config.twinmaker_hierarchy)
    
    if context.config.iot_devices:
        logger.info("[L4] Destroying TwinMaker Component Types...")
        for device in context.config.iot_devices:
             destroy_twinmaker_component_type(device, provider)

    destroy_twinmaker_workspace(provider)
    destroy_twinmaker_iam_role(provider)
    destroy_twinmaker_s3_bucket(provider)
    
    logger.info(f"[L4] Layer 4 destruction complete")


def info_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Check status of Layer 4 (Digital Twin) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_4_twinmaker import info_l4 as _info_l4_impl
    
    logger.info(f"[L4] Checking status for {context.config.digital_twin_name}")
    _info_l4_impl(context, provider)
