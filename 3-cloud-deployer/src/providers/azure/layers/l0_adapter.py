"""
Layer 0 Adapter - Orchestration Logic for Azure.

This module orchestrates the deployment of multi-cloud receiver components
based on provider boundaries. It mirrors the AWS `l0_adapter.py` pattern.

Provider Boundary Detection:
    L0 components are only deployed when there's a cloud boundary:
    - Ingestion: Deployed when L1 ≠ L2
    - Hot Writer: Deployed when L2 ≠ L3 Hot
    - Cold Writer: Deployed when L3 Hot ≠ L3 Cold
    - Archive Writer: Deployed when L3 Cold ≠ L3 Archive
    - Hot Reader URL: Created when L3 Hot ≠ L4

Token Management:
    Secure tokens are generated for inter-cloud authentication.
    These are stored in the inter-cloud connection config.
"""

from typing import TYPE_CHECKING
import logging
import secrets

from src.providers.azure.layers.layer_0_glue import (
    create_glue_function_app,
    destroy_glue_function_app,
    check_glue_function_app,
    check_consumption_app_service_plan,
    deploy_ingestion_function,
    destroy_ingestion_function,
    check_ingestion_function,
    deploy_hot_writer_function,
    destroy_hot_writer_function,
    check_hot_writer_function,
    deploy_cold_writer_function,
    destroy_cold_writer_function,
    check_cold_writer_function,
    deploy_archive_writer_function,
    destroy_archive_writer_function,
    check_archive_writer_function,
    create_hot_reader_endpoint,
    create_hot_reader_last_entry_endpoint,
    destroy_hot_reader_endpoint,
    destroy_hot_reader_last_entry_endpoint,
    check_hot_reader_endpoint,
    check_hot_reader_last_entry_endpoint,
)
from src.core.config_loader import save_inter_cloud_connection

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


def _generate_secure_token() -> str:
    """Generate a secure random token for inter-cloud authentication."""
    return secrets.token_urlsafe(32)


def _get_provider_for_layer(config, layer_key: str) -> str:
    """Get the provider name for a specific layer from config."""
    return config.providers.get(layer_key, "").lower()


def deploy_l0(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 0 multi-cloud receiver components for Azure.
    
    Only deploys components where there's a cloud boundary (different providers).
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance
    
    Provider Boundaries:
        - L1 → L2: If L1 ≠ L2, deploy Ingestion
        - L2 → L3: If L2 ≠ L3 Hot, deploy Hot Writer
        - L3 Hot → L3 Cold: If different, deploy Cold Writer
        - L3 Cold → L3 Archive: If different, deploy Archive Writer
        - L3 → L4: If L3 Hot ≠ L4, create Hot Reader endpoint
    """
    config = context.config
    twin_name = config.digital_twin_name
    project_path = context.project_path
    
    logger.info(f"========== Azure L0 Glue Layer: {twin_name} ==========")
    
    # Get provider assignments
    l1_provider = _get_provider_for_layer(config, "layer_1_provider")
    l2_provider = _get_provider_for_layer(config, "layer_2_provider")
    l3_hot_provider = _get_provider_for_layer(config, "layer_3_hot_provider")
    l3_cold_provider = _get_provider_for_layer(config, "layer_3_cold_provider")
    l3_archive_provider = _get_provider_for_layer(config, "layer_3_archive_provider")
    l4_provider = _get_provider_for_layer(config, "layer_4_provider")
    
    # Determine which components to deploy
    deploy_ingestion = l1_provider != l2_provider and l2_provider == "azure"
    deploy_hot_writer = l2_provider != l3_hot_provider and l3_hot_provider == "azure"
    deploy_cold_writer = l3_hot_provider != l3_cold_provider and l3_cold_provider == "azure"
    deploy_archive_writer = l3_cold_provider != l3_archive_provider and l3_archive_provider == "azure"
    deploy_hot_reader = l3_hot_provider != l4_provider and l3_hot_provider == "azure"
    
    # Check if any L0 components are needed
    needs_l0 = any([
        deploy_ingestion,
        deploy_hot_writer,
        deploy_cold_writer,
        deploy_archive_writer,
        deploy_hot_reader
    ])
    
    if not needs_l0:
        logger.info("No L0 components needed (all layers on same cloud or different cloud)")
        return
    
    # Create the Function App first (shared by all L0 functions)
    logger.info("Creating L0 Glue Function App...")
    create_glue_function_app(provider, config)
    
    # Deploy components based on boundaries
    connection_details = {}
    
    if deploy_ingestion:
        logger.info("Deploying Ingestion (L1→L2 boundary)...")
        token = _generate_secure_token()
        url = deploy_ingestion_function(provider, config, token)
        connection_details["l2_ingestion_url"] = url
        connection_details["l2_ingestion_token"] = token
    
    if deploy_hot_writer:
        logger.info("Deploying Hot Writer (L2→L3 boundary)...")
        token = _generate_secure_token()
        url = deploy_hot_writer_function(provider, config, token)
        connection_details["l3_hot_writer_url"] = url
        connection_details["l3_hot_writer_token"] = token
    
    if deploy_cold_writer:
        logger.info("Deploying Cold Writer (L3 Hot→Cold boundary)...")
        token = _generate_secure_token()
        url = deploy_cold_writer_function(provider, config, token)
        connection_details["l3_cold_writer_url"] = url
        connection_details["l3_cold_writer_token"] = token
    
    if deploy_archive_writer:
        logger.info("Deploying Archive Writer (L3 Cold→Archive boundary)...")
        token = _generate_secure_token()
        url = deploy_archive_writer_function(provider, config, token)
        connection_details["l3_archive_writer_url"] = url
        connection_details["l3_archive_writer_token"] = token
    
    if deploy_hot_reader:
        logger.info("Creating Hot Reader endpoints (L3→L4 boundary)...")
        token = _generate_secure_token()
        url = create_hot_reader_endpoint(provider, token)
        last_entry_url = create_hot_reader_last_entry_endpoint(provider, token)
        connection_details["l3_hot_reader_url"] = url
        connection_details["l3_hot_reader_last_entry_url"] = last_entry_url
        connection_details["l3_hot_reader_token"] = token
    
    # Save connection details for cross-cloud communication
    if connection_details:
        save_inter_cloud_connection(project_path, "azure", connection_details)
        logger.info(f"Saved inter-cloud connection details for Azure")
    
    logger.info(f"========== Azure L0 Glue Layer Complete ==========")


def destroy_l0(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy all Layer 0 multi-cloud receiver components.
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance
    """
    twin_name = context.config.digital_twin_name
    
    logger.info(f"========== Destroying Azure L0 Glue Layer: {twin_name} ==========")
    
    # Destroy individual function configurations
    destroy_hot_reader_last_entry_endpoint(provider)
    destroy_hot_reader_endpoint(provider)
    destroy_archive_writer_function(provider)
    destroy_cold_writer_function(provider)
    destroy_hot_writer_function(provider)
    destroy_ingestion_function(provider)
    
    # Destroy the entire Function App (removes all functions)
    destroy_glue_function_app(provider)
    
    # Destroy the App Service Plan (created during deploy)
    from src.providers.azure.layers.layer_0_glue import destroy_consumption_app_service_plan
    destroy_consumption_app_service_plan(provider)
    
    logger.info(f"========== Azure L0 Glue Layer Destroyed ==========")


def info_l0(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Get status information for all L0 components.
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance
    
    Returns:
        Dictionary with component status
    """
    config = context.config
    twin_name = config.digital_twin_name
    
    logger.info(f"========== Azure L0 Glue Layer Info: {twin_name} ==========")
    
    # Get provider assignments
    l1_provider = _get_provider_for_layer(config, "layer_1_provider")
    l2_provider = _get_provider_for_layer(config, "layer_2_provider")
    l3_hot_provider = _get_provider_for_layer(config, "layer_3_hot_provider")
    l3_cold_provider = _get_provider_for_layer(config, "layer_3_cold_provider")
    l3_archive_provider = _get_provider_for_layer(config, "layer_3_archive_provider")
    l4_provider = _get_provider_for_layer(config, "layer_4_provider")
    
    status = {
        "app_service_plan": check_consumption_app_service_plan(provider),
        "function_app": check_glue_function_app(provider),
    }
    
    # Check components based on boundaries
    if l1_provider != l2_provider and l2_provider == "azure":
        status["ingestion"] = check_ingestion_function(provider)
    
    if l2_provider != l3_hot_provider and l3_hot_provider == "azure":
        status["hot_writer"] = check_hot_writer_function(provider)
    
    if l3_hot_provider != l3_cold_provider and l3_cold_provider == "azure":
        status["cold_writer"] = check_cold_writer_function(provider)
    
    if l3_cold_provider != l3_archive_provider and l3_archive_provider == "azure":
        status["archive_writer"] = check_archive_writer_function(provider)
    
    if l3_hot_provider != l4_provider and l3_hot_provider == "azure":
        status["hot_reader"] = check_hot_reader_endpoint(provider)
        status["hot_reader_last_entry"] = check_hot_reader_last_entry_endpoint(provider)
    
    # Summary
    if not status.get("function_app"):
        logger.info("✗ L0 Glue Function App not deployed")
    else:
        all_ok = all(v for k, v in status.items())
        if all_ok:
            logger.info("✓ All L0 components exist")
        else:
            missing = [k for k, v in status.items() if not v]
            logger.info(f"✗ Missing components: {', '.join(missing)}")
    
    return status
