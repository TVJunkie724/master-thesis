"""
Azure Layer 5 (Visualization) Adapter.

This module provides context-based wrappers around the Layer 5
deployment functions, passing provider and config explicitly.

The adapter is the entry point called by the deployer strategy
and orchestrates the deployment of all L5 components.

Deployment Order:
    1. Pre-flight check (verify L3 Hot Storage deployed)
    2. Azure Managed Grafana Workspace
    3. Hot Reader URL resolution (single or multi-cloud)
    4. JSON API Datasource configuration

Pre-flight Check:
    L5 requires L3 Hot to be deployed first for the Hot Reader
    that Grafana needs to query data from.

Architecture Note:
    Azure L5 uses JSON API datasource to query data from L3 Hot Reader.
    - Single-cloud: Grafana → JSON API → L3 Function App → Cosmos DB
    - Multi-cloud: Grafana → JSON API → L0 Hot Reader URL → Remote L3
"""

from typing import TYPE_CHECKING, Dict, Any
import os
import json
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AzureProvider


def _check_l3_deployed(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Verify that L3 Hot Storage is deployed before deploying L5.
    
    L5 depends on L3 for:
    - Hot Reader function to query data
    - Cosmos DB hot storage (single-cloud) or remote endpoint (multi-cloud)
    
    Single-cloud (L3=L5): Check local L3 components exist
    Multi-cloud (L3≠L5): Check config_inter_cloud.json has Hot Reader URL
    
    Raises:
        RuntimeError: If L3 Hot is not fully deployed
    """
    l3_hot_provider = context.config.providers.get("layer_3_hot_provider")
    l5_provider = context.config.providers.get("layer_5_provider")
    
    if not l3_hot_provider:
        raise ValueError(
            "[L5] Configuration error: 'layer_3_hot_provider' is not set in config.providers. "
            "This is required to determine single-cloud vs multi-cloud deployment."
        )
    if not l5_provider:
        raise ValueError(
            "[L5] Configuration error: 'layer_5_provider' is not set in config.providers. "
            "This is required to determine single-cloud vs multi-cloud deployment."
        )
    
    l3_hot_provider = l3_hot_provider.lower()
    l5_provider = l5_provider.lower()
    
    if l3_hot_provider == l5_provider:
        # Single-cloud: Check local L3 components
        _check_l3_single_cloud(provider)
    else:
        # Multi-cloud: Check config_inter_cloud.json has Hot Reader URL
        _check_l3_multi_cloud(context.project_path)


def _check_l3_single_cloud(provider: 'AzureProvider') -> None:
    """
    Verify L3 Hot Storage components exist locally (single-cloud).
    
    Raises:
        RuntimeError: If L3 Hot is not fully deployed
    """
    from .layer_3_storage import (
        check_cosmos_account,
        check_hot_cosmos_container,
        check_hot_reader_function,
        check_l3_function_app
    )
    
    # Check core L3 components
    cosmos_exists = check_cosmos_account(provider)
    container_exists = check_hot_cosmos_container(provider) if cosmos_exists else False
    function_app_exists = check_l3_function_app(provider)
    hot_reader_exists = check_hot_reader_function(provider) if function_app_exists else False
    
    if cosmos_exists and container_exists and function_app_exists and hot_reader_exists:
        logger.info("[L5] ✓ Pre-flight check: L3 Hot Storage is deployed (single-cloud)")
        return
    
    missing = []
    if not cosmos_exists:
        missing.append("Cosmos DB Account")
    if not container_exists:
        missing.append("Hot Container")
    if not function_app_exists:
        missing.append("L3 Function App")
    if not hot_reader_exists:
        missing.append("Hot Reader Function")
    
    raise RuntimeError(
        f"[L5] Pre-flight check FAILED: L3 Hot is NOT fully deployed. "
        f"Missing: {', '.join(missing)}. Run deploy_l3_hot first."
    )


def _check_l3_multi_cloud(project_path: str) -> None:
    """
    Verify Hot Reader URL exists in config_inter_cloud.json (multi-cloud).
    
    Raises:
        RuntimeError: If Hot Reader URL not found
    """
    inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
    
    if not os.path.exists(inter_cloud_path):
        raise RuntimeError(
            "[L5] Pre-flight check FAILED: config_inter_cloud.json not found. "
            "Deploy L0 glue layer first for multi-cloud scenario."
        )
    
    with open(inter_cloud_path, 'r') as f:
        config = json.load(f)
    
    # Look for Hot Reader URL in any provider section
    hot_reader_url = None
    for provider_name, provider_config in config.items():
        if isinstance(provider_config, dict):
            url = provider_config.get("l3_hot_reader_url")
            if url:
                hot_reader_url = url
                break
    
    if not hot_reader_url:
        raise RuntimeError(
            "[L5] Pre-flight check FAILED: Hot Reader URL not found in config_inter_cloud.json. "
            "Ensure L0 glue layer deployed the Hot Reader endpoint."
        )
    
    logger.info(f"[L5] ✓ Pre-flight check: Hot Reader endpoint exists (multi-cloud)")
    logger.info(f"[L5]   URL: {hot_reader_url}")


def _get_or_create_inter_cloud_token(project_path: str) -> str:
    """
    Get or create the inter-cloud authentication token.
    
    Tries to read from config_inter_cloud.json first.
    If not found, generates a new token and saves it.
    
    Args:
        project_path: Path to project root
        
    Returns:
        The inter-cloud token
    """
    inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
    
    # Try to load existing config
    if os.path.exists(inter_cloud_path):
        with open(inter_cloud_path, 'r') as f:
            config = json.load(f)
        
        # Look for existing token
        for provider_config in config.values():
            if isinstance(provider_config, dict):
                token = provider_config.get("l3_hot_reader_token")
                if token:
                    return token
        
        # Check global token
        if "inter_cloud_token" in config:
            return config["inter_cloud_token"]
    else:
        config = {}
    
    # Generate new token if not found
    import secrets
    token = secrets.token_urlsafe(32)
    
    # Save to config
    config["inter_cloud_token"] = token
    with open(inter_cloud_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info("[L5] Generated new inter-cloud token")
    return token


def _save_grafana_url_to_inter_cloud(project_path: str, grafana_url: str) -> None:
    """
    Save Grafana workspace URL to config_inter_cloud.json.
    
    Args:
        project_path: Path to project root
        grafana_url: The Grafana workspace endpoint URL
    """
    inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
    
    # Load existing config or create new
    if os.path.exists(inter_cloud_path):
        with open(inter_cloud_path, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Add Grafana URL under Azure section
    if "azure" not in config:
        config["azure"] = {}
    config["azure"]["l5_grafana_url"] = grafana_url
    
    # Save back
    with open(inter_cloud_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"[L5] ✓ Saved Grafana URL to config_inter_cloud.json")


def deploy_l5(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 5 Visualization components.
    
    Components deployed:
        - Azure Managed Grafana Workspace
        - JSON API Datasource (configured to point to Hot Reader)
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AzureProvider instance
        
    Raises:
        RuntimeError: If L3 is not deployed
        ValueError: If required parameters are None
    """
    from .layer_5_grafana import (
        create_grafana_workspace,
        get_hot_reader_url,
        configure_json_api_datasource
    )
    
    if context is None:
        raise ValueError("context is required")
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info(f"[L5] ========== Deploying Layer 5 (Visualization) ==========")
    logger.info(f"[L5] Twin: {context.config.digital_twin_name}")
    
    project_path = context.project_path
    
    # Pre-flight check: verify L3 is deployed
    _check_l3_deployed(context, provider)
    
    # Step 1: Create Grafana Workspace
    logger.info("[L5] --- Step 1: Create Grafana Workspace ---")
    grafana_url = create_grafana_workspace(provider)
    _save_grafana_url_to_inter_cloud(project_path, grafana_url)
    
    # Step 2: Get Hot Reader URL
    logger.info("[L5] --- Step 2: Get Hot Reader URL ---")
    hot_reader_url = get_hot_reader_url(context, provider, project_path)
    
    # Step 3: Get or create inter-cloud token
    logger.info("[L5] --- Step 3: Configure Authentication ---")
    inter_cloud_token = _get_or_create_inter_cloud_token(project_path)
    
    # Step 4: Configure JSON API Datasource
    logger.info("[L5] --- Step 4: Configure JSON API Datasource ---")
    configure_json_api_datasource(provider, hot_reader_url, inter_cloud_token)
    
    logger.info(f"[L5] ========== Layer 5 Deployment Complete ==========")
    logger.info(f"[L5] Grafana URL: {grafana_url}")


def destroy_l5(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy Layer 5 Visualization components.
    
    Components destroyed:
        - Azure Managed Grafana Workspace
    
    Note: Datasource configuration is removed when workspace is deleted.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Raises:
        ValueError: If required parameters are None
    """
    from .layer_5_grafana import destroy_grafana_workspace
    
    if context is None:
        raise ValueError("context is required")
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info(f"[L5] ========== Destroying Layer 5 (Visualization) ==========")
    logger.info(f"[L5] Twin: {context.config.digital_twin_name}")
    
    # Destroy Grafana Workspace (datasource config is removed with it)
    destroy_grafana_workspace(provider)
    
    logger.info(f"[L5] ========== Layer 5 Destruction Complete ==========")


def info_l5(context: 'DeploymentContext', provider: 'AzureProvider') -> Dict[str, Any]:
    """
    Check status of Layer 5 (Visualization) components.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of all L5 components
        
    Raises:
        ValueError: If required parameters are None
    """
    from .layer_5_grafana import info_l5 as grafana_info_l5
    
    if context is None:
        raise ValueError("context is required")
    if provider is None:
        raise ValueError("provider is required")
    
    return grafana_info_l5(context, provider)
