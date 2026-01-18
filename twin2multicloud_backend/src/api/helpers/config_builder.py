# src/api/helpers/config_builder.py
"""
Extracted configuration building logic from config.py routes.

Provides:
- Safe credential masking for API responses
- Config payload building for updates
- Provider configuration status checking
"""

from typing import Dict, Any, Optional
from src.utils.crypto import decrypt


def mask_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive credential values in config for API responses.
    Replaces actual values with masked placeholders.
    
    Args:
        config: Raw configuration dict with credentials
        
    Returns:
        Config dict with masked credential values
    """
    masked = dict(config)
    
    # Define sensitive fields per provider
    sensitive_fields = {
        "aws": ["access_key_id", "secret_access_key"],
        "azure": ["client_id", "client_secret"],
        "gcp": ["service_account_json"]
    }
    
    for provider, fields in sensitive_fields.items():
        if provider in masked and masked[provider]:
            provider_config = dict(masked[provider])
            for field in fields:
                if field in provider_config and provider_config[field]:
                    # Replace with mask
                    provider_config[field] = "••••••••"
            masked[provider] = provider_config
    
    return masked


def build_config_response(
    config: Any,
    encryption_key: str
) -> Dict[str, Any]:
    """
    Build a safe config response for API clients.
    Decrypts stored credentials and masks sensitive values.
    
    Args:
        config: TwinConfiguration database model
        encryption_key: Key for credential decryption
        
    Returns:
        Dict suitable for JSON response
    """
    response = {
        "twin_id": config.twin_id,
        "debug_mode": config.debug_mode,
        "highest_step_reached": config.highest_step_reached,
        "aws_configured": False,
        "azure_configured": False,
        "gcp_configured": False,
        "optimizer_params": config.optimizer_params,
        "optimizer_result": config.optimizer_result,
    }
    
    # Add provider configs with masking
    if config.aws_credentials_encrypted:
        response["aws_configured"] = True
        try:
            decrypted = decrypt(config.aws_credentials_encrypted, encryption_key)
            response["aws"] = _mask_provider_creds("aws", decrypted)
        except Exception:
            response["aws"] = None
            
    if config.azure_credentials_encrypted:
        response["azure_configured"] = True
        try:
            decrypted = decrypt(config.azure_credentials_encrypted, encryption_key)
            response["azure"] = _mask_provider_creds("azure", decrypted)
        except Exception:
            response["azure"] = None
            
    if config.gcp_credentials_encrypted:
        response["gcp_configured"] = True
        try:
            decrypted = decrypt(config.gcp_credentials_encrypted, encryption_key)
            response["gcp"] = _mask_provider_creds("gcp", decrypted)
        except Exception:
            response["gcp"] = None
    
    return response


def _mask_provider_creds(provider: str, creds: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields for a single provider."""
    if not creds:
        return {}
    
    masked = dict(creds)
    
    sensitive = {
        "aws": ["access_key_id", "secret_access_key"],
        "azure": ["client_id", "client_secret"],
        "gcp": ["service_account_json"]
    }
    
    for field in sensitive.get(provider, []):
        if field in masked and masked[field]:
            masked[field] = "••••••••"
    
    return masked


def build_update_payload(
    current_config: Any,
    updates: Dict[str, Any],
    encryption_key: str
) -> Dict[str, Any]:
    """
    Build database update payload from API request.
    Handles credential encryption and null handling.
    
    Args:
        current_config: Current TwinConfiguration
        updates: Dict of fields to update
        encryption_key: Key for credential encryption
        
    Returns:
        Dict of fields to update in database
    """
    from src.utils.crypto import encrypt
    
    payload = {}
    
    # Simple fields
    if "debug_mode" in updates:
        payload["debug_mode"] = updates["debug_mode"]
        
    if "highest_step_reached" in updates:
        payload["highest_step_reached"] = updates["highest_step_reached"]
        
    if "optimizer_params" in updates:
        payload["optimizer_params"] = updates["optimizer_params"]
        
    if "optimizer_result" in updates:
        payload["optimizer_result"] = updates["optimizer_result"]
    
    # Credential fields - encrypt if present, clear if null
    for provider in ["aws", "azure", "gcp"]:
        if provider in updates:
            field_name = f"{provider}_credentials_encrypted"
            if updates[provider] is None:
                # Clear credentials
                payload[field_name] = None
            else:
                # Encrypt new credentials
                payload[field_name] = encrypt(updates[provider], encryption_key)
    
    return payload


def check_provider_configured(config: Any, provider: str) -> bool:
    """
    Check if a provider has valid credentials configured.
    
    Args:
        config: TwinConfiguration model
        provider: Provider name (aws, azure, gcp)
        
    Returns:
        True if provider has encrypted credentials stored
    """
    field_name = f"{provider.lower()}_credentials_encrypted"
    return getattr(config, field_name, None) is not None


def get_configured_providers(config: Any) -> list:
    """
    Get list of providers with valid credentials.
    
    Args:
        config: TwinConfiguration model
        
    Returns:
        List of provider names with credentials
    """
    configured = []
    for provider in ["aws", "azure", "gcp"]:
        if check_provider_configured(config, provider):
            configured.append(provider.upper())
    return configured
