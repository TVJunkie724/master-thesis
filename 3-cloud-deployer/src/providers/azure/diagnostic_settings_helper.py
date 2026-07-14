"""Azure diagnostic settings via REST API.

Required because azure-mgmt-monitor v7.0.0 removed the diagnostic_settings API.
Uses API version 2021-05-01-preview (latest stable for diagnostic settings).
"""
import logging
import time

import requests
from azure.core.exceptions import ClientAuthenticationError
from src.api.deployment_trace import sanitize_deployment_message
from src.providers.cleanup_registry import resource_name_owned_by_prefix

logger = logging.getLogger(__name__)


class DiagnosticSettingsHelper:
    """Helper for Azure diagnostic settings operations via REST API.
    
    The azure-mgmt-monitor v7.0.0 SDK removed the diagnostic_settings API,
    so we interact with the REST API directly.
    """
    
    API_VERSION = "2021-05-01-preview"
    SCOPE = "https://management.azure.com/.default"
    BASE_URL = "https://management.azure.com"
    MAX_RETRIES = 3
    TIMEOUT = 30  # seconds
    
    def __init__(self, credential, subscription_id: str):
        """Initialize the helper.
        
        Args:
            credential: Azure credential object (e.g., ClientSecretCredential)
            subscription_id: Azure subscription ID
        """
        self.credential = credential
        self.subscription_id = subscription_id
        
    def _get_headers(self) -> dict:
        """Get HTTP headers with fresh auth token.
        
        Token is acquired fresh per request to handle long-running cleanups
        where token might expire.
        """
        token = self.credential.get_token(self.SCOPE)
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
    
    def _request_with_retry(self, method: str, url: str) -> requests.Response:
        """Make HTTP request with retry logic for rate limiting.
        
        Args:
            method: HTTP method (GET, DELETE, etc.)
            url: Full URL to request
            
        Returns:
            Response object
            
        Raises:
            ClientAuthenticationError: If auth fails (401/403)
        """
        last_response = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = requests.request(
                    method, 
                    url, 
                    headers=self._get_headers(), 
                    timeout=self.TIMEOUT
                )
                last_response = resp
                
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited (429), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                    
                if resp.status_code in (401, 403):
                    raise ClientAuthenticationError(
                        f"Authentication failed: {resp.status_code} - {resp.text}"
                    )
                    
                return resp
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout, attempt {attempt + 1}/{self.MAX_RETRIES}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
                
        return last_response
        
    def list(self, resource_id: str) -> list[dict]:
        """List all diagnostic settings for a resource.
        
        Args:
            resource_id: Full Azure resource ID
            
        Returns:
            List of diagnostic setting dicts with 'name' and 'properties' keys.
            Empty list if resource not found or has no settings.
        """
        url = (
            f"{self.BASE_URL}{resource_id}/providers/microsoft.insights/"
            f"diagnosticSettings?api-version={self.API_VERSION}"
        )
        
        resp = self._request_with_retry("GET", url)
        
        if resp.status_code == 404:
            return []
            
        resp.raise_for_status()
        return resp.json().get("value", [])
        
    def delete(self, resource_id: str, setting_name: str) -> bool:
        """Delete a diagnostic setting from a resource.
        
        Args:
            resource_id: Full Azure resource ID
            setting_name: Name of the diagnostic setting to delete
            
        Returns:
            True if deleted successfully, False if setting not found
        """
        url = (
            f"{self.BASE_URL}{resource_id}/providers/microsoft.insights/"
            f"diagnosticSettings/{setting_name}?api-version={self.API_VERSION}"
        )
        
        resp = self._request_with_retry("DELETE", url)
        
        if resp.status_code == 404:
            logger.debug(f"Diagnostic setting '{setting_name}' not found (already deleted?)")
            return False
            
        resp.raise_for_status()
        return True
    
    def cleanup_orphaned_by_prefix(self, prefix: str, dry_run: bool = False) -> dict:
        """Delete all diagnostic settings matching prefix across subscription.
        
        This catches orphaned diagnostic settings from previous deployments that 
        had different deployment suffixes but the same resource names. These cause
        409 Conflict errors when creating new diagnostic settings.
        
        Args:
            prefix: Resource name prefix to match (e.g., 'sc2-aws-azure')
            dry_run: If True, log what would be deleted without deleting
            
        Returns:
            Dict with 'deleted' and 'errors' counts
        """
        from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient
        from azure.mgmt.storage import StorageManagementClient
        
        results = {"deleted": 0, "errors": 0, "resources_checked": 0}
        
        logger.info(f"[Diagnostic Settings] Scanning subscription for orphans matching '{prefix}'...")
        
        # Check all ADT instances
        try:
            adt_client = AzureDigitalTwinsManagementClient(self.credential, self.subscription_id)
            for adt in adt_client.digital_twins.list():
                if resource_name_owned_by_prefix(adt.name.lower(), prefix.lower()):
                    results["resources_checked"] += 1
                    for setting in self.list(adt.id):
                        setting_name = setting.get("name", "unknown")
                        if resource_name_owned_by_prefix(
                            setting_name.lower(),
                            prefix.lower(),
                        ):
                            logger.info(f"  ADT '{adt.name}': {setting_name}")
                            if dry_run:
                                logger.info("    [DRY RUN] Would delete")
                            else:
                                try:
                                    self.delete(adt.id, setting_name)
                                    results["deleted"] += 1
                                    logger.info("    ✓ Deleted")
                                except Exception as e:
                                    results["errors"] += 1
                                    logger.warning(
                                        "    Delete failed: %s",
                                        sanitize_deployment_message(str(e)),
                                    )
        except Exception as e:
            results["errors"] += 1
            logger.warning(
                "  ADT scan failed: %s",
                sanitize_deployment_message(str(e)),
            )
        
        # Check all Storage accounts (including blobServices/default sub-resource)
        try:
            storage_client = StorageManagementClient(self.credential, self.subscription_id)
            for account in storage_client.storage_accounts.list():
                if resource_name_owned_by_prefix(
                    account.name.lower(),
                    prefix.lower(),
                    allow_compact=True,
                ):
                    results["resources_checked"] += 1
                    # Storage account itself
                    for setting in self.list(account.id):
                        setting_name = setting.get("name", "unknown")
                        if resource_name_owned_by_prefix(
                            setting_name.lower(),
                            prefix.lower(),
                        ):
                            logger.info(f"  Storage '{account.name}': {setting_name}")
                            if dry_run:
                                logger.info("    [DRY RUN] Would delete")
                            else:
                                try:
                                    self.delete(account.id, setting_name)
                                    results["deleted"] += 1
                                    logger.info("    ✓ Deleted")
                                except Exception as e:
                                    results["errors"] += 1
                                    logger.warning(
                                        "    Delete failed: %s",
                                        sanitize_deployment_message(str(e)),
                                    )
                    
                    # blobServices/default sub-resource
                    blob_id = f"{account.id}/blobServices/default"
                    for setting in self.list(blob_id):
                        setting_name = setting.get("name", "unknown")
                        if resource_name_owned_by_prefix(
                            setting_name.lower(),
                            prefix.lower(),
                        ):
                            logger.info(f"  Storage '{account.name}/blobServices/default': {setting_name}")
                            if dry_run:
                                logger.info("    [DRY RUN] Would delete")
                            else:
                                try:
                                    self.delete(blob_id, setting_name)
                                    results["deleted"] += 1
                                    logger.info("    ✓ Deleted")
                                except Exception as e:
                                    results["errors"] += 1
                                    logger.warning(
                                        "    Delete failed: %s",
                                        sanitize_deployment_message(str(e)),
                                    )
        except Exception as e:
            results["errors"] += 1
            logger.warning(
                "  Storage scan failed: %s",
                sanitize_deployment_message(str(e)),
            )
        
        logger.info(f"[Diagnostic Settings] Scan complete: {results['resources_checked']} resources checked, "
                    f"{results['deleted']} deleted, {results['errors']} errors")
        
        return results
