"""
Layer 5 (Visualization) SDK Operations for AWS.

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
         └── L3 Hot Reader Lambda (via API Gateway)

Note:
    Infrastructure (Grafana workspace, IAM roles) is handled by Terraform.
    This file handles SDK-managed datasource configuration.
"""

from typing import TYPE_CHECKING, Dict, Any, Optional
import logging
import requests

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def _get_grafana_workspace_id(provider: 'AWSProvider') -> Optional[str]:
    """
    Get the Grafana workspace ID.
    
    Args:
        provider: Initialized AWSProvider
        
    Returns:
        Workspace ID or None if not found
        
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    workspace_name = provider.naming.grafana_workspace()
    client = provider.clients["grafana"]
    
    try:
        response = client.list_workspaces()
        for workspace in response.get("workspaces", []):
            if workspace.get("name") == workspace_name:
                return workspace.get("id")
        logger.info(f"✗ Grafana workspace not found: {workspace_name}")
        return None
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            logger.error(f"PERMISSION DENIED listing Grafana workspaces: {e}")
            raise
        else:
            logger.error(f"AWS error listing Grafana workspaces: {error_code} - {e}")
            raise


def _get_grafana_workspace_url(provider: 'AWSProvider') -> Optional[str]:
    """
    Get the Grafana workspace URL.
    
    Args:
        provider: Initialized AWSProvider
        
    Returns:
        Workspace URL or None if not found
    """
    if provider is None:
        raise ValueError("provider is required")
    
    workspace_id = _get_grafana_workspace_id(provider)
    if not workspace_id:
        return None
    
    client = provider.clients["grafana"]
    
    try:
        response = client.describe_workspace(workspaceId=workspace_id)
        return response.get("workspace", {}).get("endpoint")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"AWS error getting Grafana workspace: {error_code}")
        return None


def _get_grafana_api_key(provider: 'AWSProvider', workspace_id: str) -> Optional[str]:
    """
    Get or create a Grafana API key for datasource configuration.
    
    Args:
        provider: Initialized AWSProvider
        workspace_id: Grafana workspace ID
        
    Returns:
        API key or None if not available
    """
    if provider is None:
        raise ValueError("provider is required")
    if not workspace_id:
        raise ValueError("workspace_id is required")
    
    client = provider.clients["grafana"]
    key_name = f"{provider.twin_name}-deployer-key"
    
    try:
        # Create a new API key
        response = client.create_workspace_api_key(
            workspaceId=workspace_id,
            keyName=key_name,
            keyRole="ADMIN",
            secondsToLive=3600  # 1 hour
        )
        return response.get("key")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ConflictException":
            # Key already exists, delete and recreate
            try:
                client.delete_workspace_api_key(
                    workspaceId=workspace_id,
                    keyName=key_name
                )
                response = client.create_workspace_api_key(
                    workspaceId=workspace_id,
                    keyName=key_name,
                    keyRole="ADMIN",
                    secondsToLive=3600
                )
                return response.get("key")
            except ClientError:
                logger.warning("Could not create Grafana API key")
                return None
        else:
            logger.warning(f"Could not create Grafana API key: {error_code}")
            return None


# ==========================================
# SDK-Managed Resource Checks
# ==========================================

def check_datasource(datasource_name: str, provider: 'AWSProvider') -> bool:
    """
    Check if a Grafana datasource exists.
    
    Uses the Grafana HTTP API to check datasource status.
    
    Args:
        datasource_name: Name of the datasource to check
        provider: Initialized AWSProvider
        
    Returns:
        True if datasource exists, False otherwise
        
    Raises:
        ValueError: If datasource_name or provider is None
    """
    if datasource_name is None:
        raise ValueError("datasource_name is required")
    if provider is None:
        raise ValueError("provider is required")
    
    workspace_id = _get_grafana_workspace_id(provider)
    if not workspace_id:
        logger.info("✗ Grafana workspace not accessible")
        return False
    
    grafana_url = _get_grafana_workspace_url(provider)
    if not grafana_url:
        return False
    
    api_key = _get_grafana_api_key(provider, workspace_id)
    if not api_key:
        logger.info("✗ Could not get Grafana API key")
        return False
    
    try:
        response = requests.get(
            f"https://{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info(f"✓ Grafana datasource exists: {datasource_name}")
            return True
        elif response.status_code == 404:
            logger.info(f"✗ Grafana datasource not found: {datasource_name}")
            return False
        else:
            logger.warning(f"Unexpected response: {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"HTTP error checking datasource: {e}")
        return False


def info_l5(context: 'DeploymentContext', provider: 'AWSProvider') -> Dict[str, Any]:
    """
    Check status of SDK-managed L5 resources.
    
    Checks Grafana datasource configuration status.
    
    Args:
        context: Deployment context with config
        provider: Initialized AWSProvider
        
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
    
    workspace_url = _get_grafana_workspace_url(provider)
    datasource_name = f"{context.config.digital_twin_name}-hot-reader"
    datasource_exists = False
    
    if workspace_url:
        datasource_exists = check_datasource(datasource_name, provider)
    
    return {
        "layer": "5",
        "provider": "aws",
        "grafana_url": workspace_url,
        "datasources": {
            datasource_name: datasource_exists
        }
    }


# ==========================================
# Post-Terraform SDK Operations
# ==========================================

def configure_grafana_datasource(provider: 'AWSProvider', hot_reader_url: str) -> None:
    """
    Configure JSON API datasource in AWS Managed Grafana (post-Terraform).
    
    Creates a JSON API datasource that points to the Hot Reader Lambda
    for data visualization.
    
    Args:
        provider: Initialized AWSProvider
        hot_reader_url: URL of the Hot Reader Lambda (via API Gateway)
        
    Raises:
        ValueError: If provider or hot_reader_url is None/empty
        requests.RequestException: If HTTP request fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not hot_reader_url:
        raise ValueError("hot_reader_url is required")
    
    workspace_id = _get_grafana_workspace_id(provider)
    if not workspace_id:
        logger.warning("Grafana workspace not found, skipping datasource config")
        return
    
    grafana_url = _get_grafana_workspace_url(provider)
    if not grafana_url:
        logger.warning("Grafana workspace URL not found, skipping datasource config")
        return
    
    api_key = _get_grafana_api_key(provider, workspace_id)
    if not api_key:
        logger.warning("Could not get Grafana API key, skipping datasource config")
        return
    
    datasource_name = f"{provider.twin_name}-hot-reader"
    
    logger.info(f"Configuring Grafana datasource: {datasource_name}")
    logger.info(f"  Hot Reader URL: {hot_reader_url}")
    
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
        # Check if datasource exists
        response = requests.get(
            f"https://{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )
        
        if response.status_code == 200:
            # Update existing
            existing_ds = response.json()
            datasource_id = existing_ds.get("id")
            
            response = requests.put(
                f"https://{grafana_url}/api/datasources/{datasource_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=datasource_config,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Grafana datasource updated: {datasource_name}")
            else:
                logger.warning(f"Failed to update datasource: {response.status_code}")
        else:
            # Create new
            response = requests.post(
                f"https://{grafana_url}/api/datasources",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=datasource_config,
                timeout=30
            )
            
            if response.status_code in (200, 201):
                logger.info(f"✓ Grafana datasource created: {datasource_name}")
            else:
                logger.warning(f"Failed to create datasource: {response.status_code}")
                
    except requests.RequestException as e:
        logger.error(f"HTTP error configuring datasource: {e}")
        raise
    
    logger.info("✓ Grafana datasource configuration complete")
