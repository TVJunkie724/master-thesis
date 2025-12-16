"""
Layer 5 (Visualization) SDK Operations for Azure.

This module provides:
1. Post-Terraform SDK operations (Grafana datasource configuration)
2. SDK-managed resource checks (datasource status)

Components Managed:
- Grafana Datasource: JSON API datasource pointing to Hot Reader

Architecture:
    Hot Reader URL → Grafana Datasource → Dashboard Panels
         │                   │                   │
         │                   │                   └── Visualizations
         │                   └── JSON API Config
         └── L3 Hot Reader endpoint

Note:
    Infrastructure (Grafana workspace) is handled by Terraform.
    This file handles SDK-managed datasource configuration.
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging
import requests

from azure.core.exceptions import (
    ResourceNotFoundError,
    ClientAuthenticationError,
    HttpResponseError,
    AzureError
)

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def get_grafana_workspace_url(provider: 'AzureProvider') -> Optional[str]:
    """
    Get the endpoint URL of the Azure Managed Grafana workspace.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The Grafana workspace URL or None if not found
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()
    
    try:
        grafana_client = provider.clients.get("dashboard")
        if grafana_client is None:
            logger.warning("Dashboard client not initialized")
            return None
        
        workspace = grafana_client.grafana.get(
            resource_group_name=rg_name,
            workspace_name=workspace_name
        )
        if workspace.properties and workspace.properties.endpoint:
            return workspace.properties.endpoint
        return None
    except ResourceNotFoundError:
        logger.info(f"✗ Grafana workspace not found: {workspace_name}")
        return None
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED getting Grafana workspace: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error getting Grafana workspace: {type(e).__name__}: {e}")
        raise


def _get_grafana_service_account_token(provider: 'AzureProvider') -> Optional[str]:
    """
    Get a service account token for Grafana API access.
    
    Azure Managed Grafana uses Azure AD authentication.
    This function retrieves an access token for the Grafana API.
    
    Args:
        provider: Initialized AzureProvider
        
    Returns:
        Access token for Grafana API or None if not available
    """
    if provider is None:
        raise ValueError("provider is required")
    
    try:
        from azure.identity import DefaultAzureCredential
        
        credential = DefaultAzureCredential()
        # Get token for Azure Managed Grafana resource
        token = credential.get_token("https://grafana.azure.com/.default")
        return token.token
    except Exception as e:
        logger.warning(f"Could not get Grafana API token: {e}")
        return None


# ==========================================
# SDK-Managed Resource Checks
# ==========================================

def check_datasource(datasource_name: str, provider: 'AzureProvider') -> bool:
    """
    Check if a Grafana datasource exists.
    
    Uses the Grafana HTTP API to check datasource status.
    
    Args:
        datasource_name: Name of the datasource to check
        provider: Initialized AzureProvider
        
    Returns:
        True if datasource exists, False otherwise
        
    Raises:
        ValueError: If datasource_name or provider is None
    """
    if datasource_name is None:
        raise ValueError("datasource_name is required")
    if provider is None:
        raise ValueError("provider is required")
    
    grafana_url = get_grafana_workspace_url(provider)
    if not grafana_url:
        logger.info("✗ Grafana workspace not accessible")
        return False
    
    token = _get_grafana_service_account_token(provider)
    if not token:
        logger.info("✗ Could not get Grafana API token")
        return False
    
    try:
        response = requests.get(
            f"{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info(f"✓ Grafana datasource exists: {datasource_name}")
            return True
        elif response.status_code == 404:
            logger.info(f"✗ Grafana datasource not found: {datasource_name}")
            return False
        else:
            logger.warning(f"Unexpected response checking datasource: {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"HTTP error checking datasource: {e}")
        return False


def info_l5(context: 'DeploymentContext', provider: 'AzureProvider') -> Dict[str, Any]:
    """
    Check status of SDK-managed L5 resources.
    
    Checks Grafana datasource configuration status.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider
        
    Returns:
        Dictionary with L5 status information
        
    Raises:
        ValueError: If context or provider is None
    """
    if context is None:
        raise ValueError("context is required")
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info(f"[L5] Checking SDK-managed resources for {context.config.digital_twin_name}")
    
    workspace_url = get_grafana_workspace_url(provider)
    datasource_name = f"{context.config.digital_twin_name}-hot-reader"
    datasource_exists = False
    
    if workspace_url:
        datasource_exists = check_datasource(datasource_name, provider)
    
    return {
        "layer": "5",
        "provider": "azure",
        "grafana_url": workspace_url,
        "datasources": {
            datasource_name: datasource_exists
        }
    }


# ==========================================
# Post-Terraform SDK Operations
# ==========================================

def configure_grafana_datasource(provider: 'AzureProvider', hot_reader_url: str) -> None:
    """
    Configure JSON API datasource in Grafana (post-Terraform).
    
    Creates a JSON API datasource in Azure Managed Grafana that points
    to the Hot Reader function for data visualization.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        hot_reader_url: URL of the Hot Reader function (L3)
        
    Raises:
        ValueError: If provider or hot_reader_url is None/empty
        requests.RequestException: If HTTP request fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not hot_reader_url:
        raise ValueError("hot_reader_url is required")
    
    grafana_url = get_grafana_workspace_url(provider)
    if not grafana_url:
        logger.warning("Grafana workspace not found, skipping datasource config")
        return
    
    token = _get_grafana_service_account_token(provider)
    if not token:
        logger.warning("Could not get Grafana API token, skipping datasource config")
        return
    
    datasource_name = f"{provider.twin_name}-hot-reader"
    
    logger.info(f"Configuring Grafana datasource: {datasource_name}")
    logger.info(f"  Hot Reader URL: {hot_reader_url}")
    
    # Create JSON API datasource
    datasource_config = {
        "name": datasource_name,
        "type": "marcusolsson-json-datasource",
        "url": hot_reader_url,
        "access": "proxy",
        "basicAuth": False,
        "jsonData": {
            "httpMethod": "GET"
        }
    }
    
    try:
        # Check if datasource already exists
        response = requests.get(
            f"{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            # Update existing datasource
            existing_ds = response.json()
            datasource_id = existing_ds.get("id")
            
            response = requests.put(
                f"{grafana_url}/api/datasources/{datasource_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=datasource_config,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Grafana datasource updated: {datasource_name}")
            else:
                logger.warning(f"Failed to update datasource: {response.status_code} - {response.text}")
        else:
            # Create new datasource
            response = requests.post(
                f"{grafana_url}/api/datasources",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=datasource_config,
                timeout=30
            )
            
            if response.status_code in (200, 201):
                logger.info(f"✓ Grafana datasource created: {datasource_name}")
            else:
                logger.warning(f"Failed to create datasource: {response.status_code} - {response.text}")
                
    except requests.RequestException as e:
        logger.error(f"HTTP error configuring Grafana datasource: {e}")
        raise
    
    logger.info("✓ Grafana datasource configuration complete")
