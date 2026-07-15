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


def get_publishing_credentials_with_retry(
    web_client: Any,
    resource_group: str,
    app_name: str,
    max_retries: int = 10,
    retry_delay: int = 30
) -> Any:
    """
    Get publishing credentials for a Function App with retry logic.
    
    The list_publishing_credentials API can fail with ServiceUnavailable (503)
    when the Function App is still initializing. This function retries until
    the credentials are available.
    
    Args:
        web_client: Azure WebSiteManagementClient
        resource_group: Resource group name
        app_name: Function App name
        max_retries: Maximum retry attempts (default 10, ~5 min with 30s delay)
        retry_delay: Seconds to wait between retries (default 30)
        
    Returns:
        Publishing credentials object with publishing_user_name and publishing_password
        
    Raises:
        HttpResponseError: If credentials cannot be retrieved after all retries
    """
    for attempt in range(1, max_retries + 1):
        try:
            creds = web_client.web_apps.begin_list_publishing_credentials(
                resource_group_name=resource_group,
                name=app_name
            ).result()
            return creds
        except HttpResponseError as e:
            error_str = str(e)
            # Retry on ServiceUnavailable or BadRequest with host runtime error
            if ("ServiceUnavailable" in error_str or 
                "503" in error_str or 
                "host runtime" in error_str.lower()) and attempt < max_retries:
                logger.warning(
                    f"  Function App not ready (attempt {attempt}/{max_retries}), "
                    f"waiting {retry_delay}s..."
                )
                time.sleep(retry_delay)
                continue
            # Not a retryable error or out of retries
            logger.error(f"Failed to get publishing credentials: {e}")
            raise
    
    raise HttpResponseError(
        f"Failed to get publishing credentials for {app_name} after {max_retries} attempts"
    )


def wait_for_function_warmup(app_name: str, warmup_seconds: int = 60) -> None:
    """
    Wait for Azure Function App to warm up after deployment.
    
    After Kudu ZIP deployment, the Azure Function runtime needs time to:
    - Extract and load the function code
    - Initialize the runtime environment
    - Start the function host
    
    This is especially important for:
    - Azure Student accounts (may have slower provisioning)
    - Functions with dependencies (longer cold start)
    - Sequential layer deployments (avoid ServiceUnavailable errors)
    
    Args:
        app_name: Name of the Function App (for logging)
        warmup_seconds: Seconds to wait (default 60)
    """
    logger.info(f"  Waiting {warmup_seconds}s for {app_name} function runtime to warm up...")
    time.sleep(warmup_seconds)
    logger.info(f"  ✓ Warmup complete for {app_name}")


def deploy_to_kudu(
    app_name: str,
    zip_content: bytes,
    publish_username: str,
    publish_password: str,
    max_retries: int = 15,
    retry_delay: int = 30
) -> None:
    """
    Deploy a ZIP package to Azure Function App via Kudu zipdeploy with retry.
    
    Uses async deployment (?isAsync=true) to allow Oryx remote build to complete.
    When ENABLE_ORYX_BUILD=true, Azure runs pip install from requirements.txt
    during deployment, which can take 2-3+ minutes.
    
    Handles transient errors during Function App startup:
    - 401 Unauthorized: SCM Basic Auth not yet active
    - 503 Service Unavailable: Kudu SCM still starting up
    
    Args:
        app_name: Name of the Azure Function App
        zip_content: Compiled ZIP file content (bytes)
        publish_username: Publishing username from Function App credentials
        publish_password: Publishing password from Function App credentials
        max_retries: Maximum retry attempts (default 15, ~7.5 min with 30s delay)
        retry_delay: Seconds to wait between retries (default 30)
        
    Raises:
        HttpResponseError: If deployment fails after all retries
        
    Note:
        - Kudu SCM may need 2-5+ minutes to become ready after Function App creation.
        - Oryx build (pip install) needs ~180s to complete.
        - Azure Student accounts may require longer wait times.
        - This function automatically retries on 401/503 errors to handle this.
    """
    # Use ?isAsync=true for async deployment - required for ENABLE_ORYX_BUILD
    # This allows the Oryx build system to run pip install from requirements.txt
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
    
    logger.info(f"  Deploying via Kudu async zip deploy to {app_name}...")
    
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
                logger.info("  ✓ ZIP uploaded, waiting for Oryx build to complete...")
                # Wait for Oryx build (pip install) to complete
                # This is critical - without it, functions won't have their dependencies
                wait_for_function_warmup(app_name, warmup_seconds=180)
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
        logger.info("  ✓ SCM Basic Auth enabled")
    except Exception as e:
        logger.error(f"Failed to enable SCM Basic Auth: {e}")
        raise


# =============================================================================
# Async Helpers (for SSE streaming)
# =============================================================================

async def get_publishing_credentials_async(
    web_client: Any,
    resource_group: str,
    app_name: str,
    max_retries: int = 10,
    retry_delay: int = 30
):
    """
    Get publishing credentials with async retry logic.
    
    Uses run_in_executor since Azure SDK is synchronous.
    
    Yields:
        Status messages during retry
        
    Returns:
        Publishing credentials object
    """
    import asyncio
    
    loop = asyncio.get_event_loop()
    
    for attempt in range(1, max_retries + 1):
        try:
            creds = await loop.run_in_executor(
                None,
                lambda: web_client.web_apps.begin_list_publishing_credentials(
                    resource_group_name=resource_group,
                    name=app_name
                ).result()
            )
            return creds
        except HttpResponseError as e:
            error_str = str(e)
            if ("ServiceUnavailable" in error_str or 
                "503" in error_str or 
                "host runtime" in error_str.lower()) and attempt < max_retries:
                # Don't yield here - just wait and retry
                await asyncio.sleep(retry_delay)
                continue
            raise
    
    raise HttpResponseError(
        f"Failed to get publishing credentials for {app_name} after {max_retries} attempts"
    )


async def deploy_to_kudu_async(
    app_name: str,
    zip_content: bytes,
    publish_username: str,
    publish_password: str,
    max_retries: int = 15,
    retry_delay: int = 30,
    warmup_seconds: int = 180
):
    """
    Deploy ZIP to Azure Function App via Kudu with async streaming.
    
    Uses aiohttp for async HTTP and asyncio.sleep for non-blocking waits.
    Yields status messages during the deployment for SSE streaming.
    
    Args:
        app_name: Function App name
        zip_content: ZIP file bytes
        publish_username: Kudu username
        publish_password: Kudu password
        max_retries: Maximum retry attempts
        retry_delay: Seconds between retries
        warmup_seconds: Seconds to wait for Oryx build
        
    Yields:
        Status messages during deployment
    """
    import asyncio
    import aiohttp
    from aiohttp import BasicAuth
    
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
    
    yield f"  Deploying via Kudu to {app_name}..."
    
    for attempt in range(1, max_retries + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=300)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    kudu_url,
                    data=zip_content,
                    auth=BasicAuth(publish_username, publish_password),
                    headers={"Content-Type": "application/zip"}
                ) as response:
                    if response.status in (200, 202):
                        yield "  ✓ ZIP uploaded, waiting for Oryx build..."
                        # Non-blocking warmup with progress updates
                        for i in range(0, warmup_seconds, 30):
                            await asyncio.sleep(30)
                            elapsed = i + 30
                            yield f"    Oryx build: {elapsed}s / {warmup_seconds}s"
                        yield f"  ✓ Warmup complete for {app_name}"
                        return
                    elif response.status in (401, 503) and attempt < max_retries:
                        yield f"  Kudu returned {response.status} (attempt {attempt}/{max_retries}), retrying..."
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        text = await response.text()
                        raise HttpResponseError(
                            f"Kudu zip deploy failed: {response.status} - {text}"
                        )
        except aiohttp.ClientError as e:
            if attempt < max_retries:
                yield f"  Network error (attempt {attempt}/{max_retries}), retrying..."
                await asyncio.sleep(retry_delay)
                continue
            raise HttpResponseError(f"Kudu zip deploy network error: {e}")
    
    raise HttpResponseError(
        f"Kudu zip deploy failed: max retries ({max_retries}) exceeded"
    )

