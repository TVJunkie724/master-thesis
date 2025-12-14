"""
Layer 5 (Visualization) Component Implementations for Azure.

This module contains ALL Grafana workspace implementations that are
deployed by the L5 adapter.

Components Managed:
- Azure Managed Grafana Workspace: The visualization platform
- Hot Reader HTTP Endpoint: For single-cloud, creates endpoint for Grafana
- JSON API Datasource: Configured to point to Hot Reader

Data Flow:
    Single-cloud (L3=L5): Grafana → JSON API → L5-created endpoint → L3 Hot Reader → Cosmos DB
    Multi-cloud (L3≠L5): Grafana → JSON API → L0 Hot Reader URL → Remote L3

Authentication:
    - Uses X-Inter-Cloud-Token header for Hot Reader endpoints
    - Grafana uses System-Assigned Managed Identity for Azure resources
"""

from typing import TYPE_CHECKING, Dict, Any, Optional
import os
import json
import time
import requests
from logger import logger
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.core.config import ProjectConfig
    from ..provider import AzureProvider


# ==========================================
# 1. Grafana Workspace - Create/Destroy/Check Triplet
# ==========================================

def create_grafana_workspace(provider: 'AzureProvider') -> str:
    """
    Create an Azure Managed Grafana workspace.
    
    Creates the workspace with System-Assigned Managed Identity for
    accessing other Azure resources.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The Grafana workspace endpoint URL
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()
    location = provider.location
    
    logger.info(f"[L5] Creating Azure Managed Grafana workspace: {workspace_name}")
    
    # Grafana workspace parameters
    workspace_params = {
        "location": location,
        "sku": {"name": "Standard"},  # Standard tier for production features
        "identity": {"type": "SystemAssigned"},  # For accessing Azure resources
        "properties": {
            "zoneRedundancy": "Disabled",  # Cost optimization for dev/test
            "publicNetworkAccess": "Enabled",  # Allow public access
            "apiKey": "Enabled",  # Enable API key auth for datasource config
        }
    }
    
    try:
        poller = provider.clients["dashboard"].grafana.begin_create(
            resource_group_name=rg_name,
            workspace_name=workspace_name,
            request_body_parameters=workspace_params
        )
        workspace = poller.result()
        
        endpoint = workspace.properties.endpoint
        logger.info(f"[L5] ✓ Grafana workspace created: {workspace_name}")
        logger.info(f"[L5]   Endpoint: {endpoint}")
        
        # Wait for workspace to be fully ready
        logger.info("[L5]   Waiting for workspace to be fully provisioned...")
        time.sleep(30)  # Azure Managed Grafana needs time to initialize
        
        return endpoint
        
    except HttpResponseError as e:
        logger.error(f"[L5] HTTP error creating Grafana workspace: {e.status_code} - {e.message}")
        raise


def destroy_grafana_workspace(provider: 'AzureProvider') -> None:
    """
    Delete the Azure Managed Grafana workspace.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()
    
    logger.info(f"[L5] Deleting Grafana workspace: {workspace_name}")
    
    try:
        poller = provider.clients["dashboard"].grafana.begin_delete(
            resource_group_name=rg_name,
            workspace_name=workspace_name
        )
        poller.result()
        logger.info(f"[L5] ✓ Grafana workspace deleted: {workspace_name}")
    except ResourceNotFoundError:
        logger.info(f"[L5] ✗ Grafana workspace not found (already deleted): {workspace_name}")
    except HttpResponseError as e:
        if "ResourceNotFound" in str(e):
            logger.info(f"[L5] ✗ Grafana workspace not found: {workspace_name}")
        else:
            logger.error(f"[L5] HTTP error deleting Grafana workspace: {e.status_code} - {e.message}")
            raise


def check_grafana_workspace(provider: 'AzureProvider') -> bool:
    """
    Check if the Azure Managed Grafana workspace exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if workspace exists, False otherwise
        
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()
    
    try:
        provider.clients["dashboard"].grafana.get(
            resource_group_name=rg_name,
            workspace_name=workspace_name
        )
        logger.info(f"[L5] ✓ Grafana workspace exists: {workspace_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"[L5] ✗ Grafana workspace not found: {workspace_name}")
        return False
    except HttpResponseError as e:
        if "ResourceNotFound" in str(e):
            logger.info(f"[L5] ✗ Grafana workspace not found: {workspace_name}")
            return False
        raise


def get_grafana_workspace_url(provider: 'AzureProvider') -> Optional[str]:
    """
    Get the endpoint URL of the Azure Managed Grafana workspace.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The Grafana workspace endpoint URL, or None if not found
        
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()
    
    try:
        workspace = provider.clients["dashboard"].grafana.get(
            resource_group_name=rg_name,
            workspace_name=workspace_name
        )
        return workspace.properties.endpoint
    except ResourceNotFoundError:
        return None
    except HttpResponseError:
        return None


# ==========================================
# 2. Hot Reader HTTP Endpoint for Grafana
# ==========================================

def create_hot_reader_endpoint_for_grafana(
    provider: 'AzureProvider',
    inter_cloud_token: str
) -> str:
    """
    Create or get the HTTP endpoint for Hot Reader (single-cloud scenario).
    
    In single-cloud (L3=L5 provider), the Hot Reader function exists in L3
    but may not have an HTTP endpoint configured. This function creates
    the endpoint so Grafana can access it via JSON API.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        inter_cloud_token: The shared authentication token
        
    Returns:
        The Hot Reader HTTP URL
        
    Raises:
        ValueError: If provider is None
        RuntimeError: If Hot Reader function doesn't exist
    """
    if provider is None:
        raise ValueError("provider is required")
    if not inter_cloud_token:
        raise ValueError("inter_cloud_token is required")
    
    # The L3 Function App hosts the Hot Reader
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    function_name = provider.naming.hot_reader_function()
    
    logger.info(f"[L5] Getting Hot Reader endpoint from {app_name}")
    
    # Get the function app default hostname
    try:
        app = provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        default_hostname = app.default_host_name
        
        # Construct the function URL
        # Azure Functions HTTP triggers use: https://{app}.azurewebsites.net/api/{function}
        hot_reader_url = f"https://{default_hostname}/api/{function_name}"
        
        logger.info(f"[L5] ✓ Hot Reader endpoint: {hot_reader_url}")
        return hot_reader_url
        
    except ResourceNotFoundError:
        raise RuntimeError(
            f"[L5] L3 Function App '{app_name}' not found. "
            "Deploy L3 first before deploying L5."
        )


# ==========================================
# 3. Hot Reader URL Resolution
# ==========================================

def get_hot_reader_url(
    context: 'DeploymentContext',
    provider: 'AzureProvider',
    project_path: str
) -> str:
    """
    Get the Hot Reader URL based on deployment configuration.
    
    Single-cloud (L3=L5): Get URL from L3 Function App
    Multi-cloud (L3≠L5): Get URL from config_inter_cloud.json
    
    Args:
        context: Deployment context with provider config
        provider: Initialized AzureProvider
        project_path: Path to project root for config files
        
    Returns:
        The Hot Reader HTTP URL
        
    Raises:
        RuntimeError: If URL cannot be determined
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
        # Single-cloud: Get URL from L3 Function App
        logger.info("[L5] Single-cloud: Getting Hot Reader URL from L3 Function App")
        rg_name = provider.naming.resource_group()
        app_name = provider.naming.l3_function_app()
        function_name = provider.naming.hot_reader_function()
        
        try:
            app = provider.clients["web"].web_apps.get(
                resource_group_name=rg_name,
                name=app_name
            )
            url = f"https://{app.default_host_name}/api/{function_name}"
            logger.info(f"[L5] ✓ Hot Reader URL (single-cloud): {url}")
            return url
        except ResourceNotFoundError:
            raise RuntimeError(
                "[L5] L3 Function App not found. Deploy L3 before L5."
            )
    else:
        # Multi-cloud: Get URL from config_inter_cloud.json
        logger.info("[L5] Multi-cloud: Getting Hot Reader URL from config_inter_cloud.json")
        inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
        
        if not os.path.exists(inter_cloud_path):
            raise RuntimeError(
                f"[L5] config_inter_cloud.json not found at {inter_cloud_path}. "
                "Deploy L0 glue layer first."
            )
        
        with open(inter_cloud_path, 'r') as f:
            config = json.load(f)
        
        # Look for Hot Reader URL from the L3 provider's section
        hot_reader_url = None
        for provider_name, provider_config in config.items():
            if isinstance(provider_config, dict):
                url = provider_config.get("l3_hot_reader_url")
                if url:
                    hot_reader_url = url
                    break
        
        if not hot_reader_url:
            raise RuntimeError(
                "[L5] Hot Reader URL not found in config_inter_cloud.json. "
                "Ensure L0 glue layer deployed the Hot Reader endpoint."
            )
        
        logger.info(f"[L5] ✓ Hot Reader URL (multi-cloud): {hot_reader_url}")
        return hot_reader_url


def get_inter_cloud_token(project_path: str) -> str:
    """
    Get the inter-cloud token from config_inter_cloud.json.
    
    Args:
        project_path: Path to project root
        
    Returns:
        The inter-cloud authentication token
        
    Raises:
        RuntimeError: If token not found
    """
    inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
    
    if not os.path.exists(inter_cloud_path):
        raise RuntimeError(
            f"[L5] config_inter_cloud.json not found at {inter_cloud_path}"
        )
    
    with open(inter_cloud_path, 'r') as f:
        config = json.load(f)
    
    # Look for token in any provider section
    for provider_name, provider_config in config.items():
        if isinstance(provider_config, dict):
            token = provider_config.get("l3_hot_reader_token")
            if token:
                return token
    
    # Check for global token
    token = config.get("inter_cloud_token")
    if token:
        return token
    
    raise RuntimeError(
        "[L5] Inter-cloud token not found in config_inter_cloud.json"
    )


# ==========================================
# 4. JSON API Datasource Configuration
# ==========================================

def configure_json_api_datasource(
    provider: 'AzureProvider',
    hot_reader_url: str,
    inter_cloud_token: str
) -> None:
    """
    Configure the JSON API datasource in Grafana to point to Hot Reader.
    
    Uses the Grafana HTTP API to create a datasource that points to
    the Hot Reader endpoint with authentication.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        hot_reader_url: The Hot Reader HTTP URL
        inter_cloud_token: Authentication token for Hot Reader
        
    Raises:
        ValueError: If required parameters are None
        RuntimeError: If datasource configuration fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not hot_reader_url:
        raise ValueError("hot_reader_url is required")
    if not inter_cloud_token:
        raise ValueError("inter_cloud_token is required")
    
    # Get Grafana workspace details
    grafana_url = get_grafana_workspace_url(provider)
    if not grafana_url:
        raise RuntimeError("[L5] Grafana workspace not found. Create workspace first.")
    
    logger.info(f"[L5] Configuring JSON API datasource pointing to: {hot_reader_url}")
    
    # Get Grafana API key for authentication
    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()
    
    try:
        # Create a service account API key for datasource management
        api_key_response = provider.clients["dashboard"].grafana.create_service_account_token(
            resource_group_name=rg_name,
            workspace_name=workspace_name,
            service_account_name="l5-deployer",
            body={
                "name": "l5-datasource-config",
                "secondsToLive": 3600  # 1 hour validity
            }
        )
        api_key = api_key_response.key
    except Exception as e:
        # If service account API fails, try legacy API key
        logger.warning(f"[L5] Could not create service account token: {e}")
        logger.info("[L5] Attempting legacy API key creation...")
        try:
            api_key_response = provider.clients["dashboard"].grafana.create_api_key(
                resource_group_name=rg_name,
                workspace_name=workspace_name,
                body={
                    "name": "l5-datasource-config",
                    "role": "Admin",
                    "secondsToLive": 3600
                }
            )
            api_key = api_key_response.key
        except Exception as e2:
            raise RuntimeError(
                f"[L5] Failed to create Grafana API key for datasource configuration. "
                f"Service account error: {e}, Legacy API key error: {e2}"
            )
    
    # Configure datasource via Grafana HTTP API
    datasource_config = {
        "name": "Hot-Reader-Data",
        "type": "marcusolsson-json-datasource",  # JSON API plugin
        "url": hot_reader_url,
        "access": "proxy",  # Grafana server proxies requests
        "basicAuth": False,
        "jsonData": {
            "httpHeaderName1": "X-Inter-Cloud-Token"
        },
        "secureJsonData": {
            "httpHeaderValue1": inter_cloud_token
        }
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{grafana_url}/api/datasources",
            json=datasource_config,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in (200, 201):
            logger.info("[L5] ✓ JSON API datasource configured successfully")
        elif response.status_code == 409:
            logger.info("[L5] ✓ JSON API datasource already exists")
        else:
            raise RuntimeError(
                f"[L5] Datasource configuration failed with status {response.status_code}. "
                f"Response: {response.text[:200]}"
            )
            
    except requests.RequestException as e:
        raise RuntimeError(
            f"[L5] Failed to configure datasource via Grafana API: {e}"
        )


# ==========================================
# 5. Info/Status Functions
# ==========================================

def info_l5(context: 'DeploymentContext', provider: 'AzureProvider') -> Dict[str, Any]:
    """
    Check status of Layer 5 (Visualization) components.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of all L5 components
    """
    logger.info(f"[L5] Checking status for {context.config.digital_twin_name}")
    
    workspace_exists = check_grafana_workspace(provider)
    workspace_url = get_grafana_workspace_url(provider) if workspace_exists else None
    
    status = {
        "grafana_workspace": {
            "exists": workspace_exists,
            "url": workspace_url
        }
    }
    
    return status
