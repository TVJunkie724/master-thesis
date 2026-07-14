# src/api/helpers/config_builder.py
"""
Extracted configuration building logic from config.py routes.

This module is retained for older imports only. The canonical configuration
contract is CloudConnection-based and is implemented by
`TwinConfigResponse.from_db` plus `WizardConfigurationService`.
"""

from typing import Dict, Any

from src.services.provider_contract import normalize_provider_id


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
    """Build a legacy-compatible response without reading legacy secret columns."""
    response = {
        "twin_id": config.twin_id,
        "debug_mode": config.debug_mode,
        "highest_step_reached": config.highest_step_reached,
        "aws_configured": bool(getattr(config, "aws_cloud_connection_id", None)),
        "azure_configured": bool(getattr(config, "azure_cloud_connection_id", None)),
        "gcp_configured": bool(getattr(config, "gcp_cloud_connection_id", None)),
        "optimizer_params": config.optimizer_params,
        "optimizer_result": config.optimizer_result,
    }
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
    """Build a non-secret update payload for legacy callers."""
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
    field_name = f"{normalize_provider_id(provider)}_cloud_connection_id"
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
