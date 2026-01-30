"""Azure diagnostic settings via REST API.

Required because azure-mgmt-monitor v7.0.0 removed the diagnostic_settings API.
Uses API version 2021-05-01-preview (latest stable for diagnostic settings).
"""
import logging
import time

import requests
from azure.core.exceptions import ClientAuthenticationError

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
