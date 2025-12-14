"""
Azure Layer 3 (Storage) Adapter.

This module provides context-based wrappers around the Layer 3
deployment functions, passing provider and config explicitly.

The adapter is the entry point called by the deployer strategy
and orchestrates the deployment of all L3 components.

Deployment Order:
    L3 Hot:
        1. Cosmos DB Account (Serverless)
        2. Cosmos DB Database
        3. Hot Cosmos Container
        4. L3 App Service Plan (dedicated)
        5. L3 Function App
        6. Hot Reader Function
        7. Hot Reader Last Entry Function
    
    L3 Cold:
        1. Cold Blob Container
        2. Hot-Cold Mover Function (timer: daily)
    
    L3 Archive:
        1. Archive Blob Container
        2. Cold-Archive Mover Function (timer: daily)

Pre-flight Check:
    L3 requires L2 to be deployed first. The adapter verifies this
    before proceeding with L3 deployment.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AzureProvider


def _check_l2_deployed(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Verify that L2 is deployed before deploying L3.
    
    L3 depends on L2 for:
    - L2 Function App (Persister writes to storage)
    
    Raises:
        RuntimeError: If L2 Function App is not deployed
    """
    # Check if L2 Function App exists
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info("[L3] ✓ Pre-flight check: L2 is deployed")
        return
    except Exception:
        raise RuntimeError(
            "[L3] Pre-flight check FAILED: L2 Function App not deployed. "
            "Run deploy_l2 first."
        )


def deploy_l3_hot(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 3 Hot Storage components.
    
    Components deployed:
        - Cosmos DB Account (Serverless)
        - Cosmos DB Database
        - Hot Cosmos Container
        - L3 App Service Plan
        - L3 Function App
        - Hot Reader Function
        - Hot Reader Last Entry Function
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AzureProvider instance
        
    Raises:
        RuntimeError: If L2 is not deployed
        ValueError: If required parameters are missing
    """
    from .layer_3_storage import (
        create_cosmos_account,
        create_cosmos_database,
        create_hot_cosmos_container,
        create_l3_app_service_plan,
        create_l3_function_app,
        deploy_hot_reader_function,
        deploy_hot_reader_last_entry_function,
    )
    
    logger.info(f"[L3-Hot] Deploying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    # Pre-flight check (raises on failure)
    _check_l2_deployed(context, provider)
    
    project_path = str(context.project_path.parent.parent)
    
    # 1. Cosmos DB infrastructure
    create_cosmos_account(provider)
    create_cosmos_database(provider)
    create_hot_cosmos_container(provider)
    
    # 2. L3 Function App infrastructure
    create_l3_app_service_plan(provider)
    create_l3_function_app(provider, context.config)
    
    # 3. Deploy Hot Reader functions
    deploy_hot_reader_function(provider, project_path)
    deploy_hot_reader_last_entry_function(provider, project_path)
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage deployment complete")


def destroy_l3_hot(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy Layer 3 Hot Storage components.
    
    Note: Destroying in reverse order of creation.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
    """
    from .layer_3_storage import (
        destroy_hot_reader_function,
        destroy_hot_reader_last_entry_function,
        destroy_l3_function_app,
        destroy_l3_app_service_plan,
        destroy_hot_cosmos_container,
        destroy_cosmos_database,
        destroy_cosmos_account,
    )
    
    logger.info(f"[L3-Hot] Destroying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    # Destroy in reverse order
    destroy_hot_reader_last_entry_function(provider)
    destroy_hot_reader_function(provider)
    destroy_l3_function_app(provider)
    destroy_l3_app_service_plan(provider)
    destroy_hot_cosmos_container(provider)
    destroy_cosmos_database(provider)
    destroy_cosmos_account(provider)
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage destruction complete")


def deploy_l3_cold(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 3 Cold Storage components.
    
    Components deployed:
        - Cold Blob Container (Cool access tier)
        - Hot-Cold Mover Function (timer: daily)
    
    Note: Multi-cloud Cold Writer is deployed by L0 adapter when needed.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AzureProvider instance
    """
    from .layer_3_storage import (
        create_cold_blob_container,
        deploy_hot_cold_mover_function,
    )
    
    logger.info(f"[L3-Cold] Deploying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    project_path = str(context.project_path.parent.parent)
    
    # 1. Cold storage
    create_cold_blob_container(provider)
    
    # 2. Hot-Cold Mover (timer-triggered, daily)
    deploy_hot_cold_mover_function(provider, context.config, project_path)
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage deployment complete")


def destroy_l3_cold(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy Layer 3 Cold Storage components.
    
    Args:
        context: Deployment context
        provider: Initialized AzureProvider instance
    """
    from .layer_3_storage import (
        destroy_hot_cold_mover_function,
        destroy_cold_blob_container,
    )
    
    logger.info(f"[L3-Cold] Destroying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    destroy_hot_cold_mover_function(provider)
    destroy_cold_blob_container(provider)
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage destruction complete")


def deploy_l3_archive(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 3 Archive Storage components.
    
    Components deployed:
        - Archive Blob Container (Archive access tier)
        - Cold-Archive Mover Function (timer: daily)
    
    Note: Multi-cloud Archive Writer is deployed by L0 adapter when needed.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AzureProvider instance
    """
    from .layer_3_storage import (
        create_archive_blob_container,
        deploy_cold_archive_mover_function,
    )
    
    logger.info(f"[L3-Archive] Deploying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    project_path = str(context.project_path.parent.parent)
    
    # 1. Archive storage
    create_archive_blob_container(provider)
    
    # 2. Cold-Archive Mover (timer-triggered, daily)
    deploy_cold_archive_mover_function(provider, context.config, project_path)
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage deployment complete")


def destroy_l3_archive(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy Layer 3 Archive Storage components.
    
    Args:
        context: Deployment context
        provider: Initialized AzureProvider instance
    """
    from .layer_3_storage import (
        destroy_cold_archive_mover_function,
        destroy_archive_blob_container,
    )
    
    logger.info(f"[L3-Archive] Destroying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    destroy_cold_archive_mover_function(provider)
    destroy_archive_blob_container(provider)
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage destruction complete")


def info_l3(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Check status of Layer 3 (Storage) components for Azure.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of all L3 components
    """
    from .layer_3_storage import info_l3 as layer_info_l3
    
    return layer_info_l3(context, provider)
