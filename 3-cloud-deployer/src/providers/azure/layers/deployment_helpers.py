"""
Shared Azure deployment helpers.

This module provides reusable helper functions for Azure deployments,
including Kudu ZIP deployment with retry logic.
"""

import time
import logging
import requests
from typing import Any

from azure.core.exceptions import HttpResponseError


logger = logging.getLogger("digital_twin")


def deploy_to_kudu(
    app_name: str,
    zip_content: bytes,
    publish_username: str,
    publish_password: str,
    max_retries: int = 10,
    retry_delay: int = 20
) -> None:
    """
    Deploy a ZIP package to Azure Function App via Kudu zipdeploy with retry.
    
    Handles transient errors during Function App startup:
    - 401 Unauthorized: SCM Basic Auth not yet active
    - 503 Service Unavailable: Kudu SCM still starting up
    
    Args:
        app_name: Name of the Azure Function App
        zip_content: Compiled ZIP file content (bytes)
        publish_username: Publishing username from Function App credentials
        publish_password: Publishing password from Function App credentials
        max_retries: Maximum retry attempts (default 10, ~3.3 min with 20s delay)
        retry_delay: Seconds to wait between retries (default 20)
        
    Raises:
        HttpResponseError: If deployment fails after all retries
        
    Note:
        Kudu SCM may need 2-3+ minutes to become ready after Function App creation.
        This function automatically retries on 401/503 errors to handle this.
    """
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy"
    
    logger.info(f"  Deploying via Kudu zip deploy to {kudu_url}...")
    
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                kudu_url,
                data=zip_content,
                auth=(publish_username, publish_password),
                headers={"Content-Type": "application/zip"},
                timeout=300
            )
            
            if response.status_code in (200, 202):
                logger.info(f"  ✓ Function code deployed successfully")
                return
            elif response.status_code in (401, 503) and attempt < max_retries:
                # 401: Kudu SCM not ready yet (auth not yet active)
                # 503: Kudu service unavailable (still starting up)
                logger.warning(
                    f"  Kudu returned {response.status_code} (attempt {attempt}/{max_retries}), "
                    f"waiting {retry_delay}s for SCM to become ready..."
                )
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"Kudu deploy failed: {response.status_code} - {response.text}")
                raise HttpResponseError(
                    f"Kudu zip deploy failed: {response.status_code} - {response.text}"
                )
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                logger.warning(
                    f"  Network error (attempt {attempt}/{max_retries}), "
                    f"waiting {retry_delay}s..."
                )
                time.sleep(retry_delay)
                continue
            logger.error(f"Network error during Kudu deploy: {e}")
            raise HttpResponseError(f"Kudu zip deploy network error: {e}")
    
    # If we get here, all retries failed
    raise HttpResponseError(
        f"Kudu zip deploy failed: max retries ({max_retries}) exceeded"
    )


def enable_scm_basic_auth(
    web_client: Any,
    resource_group: str,
    app_name: str
) -> None:
    """
    Enable SCM Basic Auth Publishing for a Function App.
    
    Azure Function Apps (since 2023) have SCM Basic Auth disabled by default,
    which is required for Kudu ZIP deployments. This function enables it.
    
    Args:
        web_client: Azure WebSiteManagementClient
        resource_group: Resource group name
        app_name: Function App name
        
    Note:
        Requires 'Microsoft.Web/sites/basicPublishingCredentialsPolicies/write' permission.
    """
    logger.info(f"  Enabling SCM Basic Auth for {app_name}...")
    try:
        web_client.web_apps.update_scm_allowed(
            resource_group_name=resource_group,
            name=app_name,
            csmPublishingAccessPoliciesEntity={"allow": True}
        )
        logger.info(f"  ✓ SCM Basic Auth enabled")
    except Exception as e:
        logger.error(f"Failed to enable SCM Basic Auth: {e}")
        raise
