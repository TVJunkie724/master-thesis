import asyncio
from typing import Any, Dict, Tuple

from src.clients.deployer_client import DeployerClient
from src.clients.optimizer_client import OptimizerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.provider_contract import normalize_provider_id
from src.services.secret_redaction import redact_secret_like_text


async def validate_with_optimizer(provider: str, credentials: dict) -> Tuple[bool, str]:
    """
    Validate credentials against the Optimizer API.
    Uses simpler schema - just cloud provider access for pricing lookups.
    
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        data = await OptimizerClient().verify_permissions(normalize_provider_id(provider), credentials)
        return data.get("valid", False) or data.get("status") == "valid", data.get("message", "OK")
    except ExternalServiceUnavailable:
        return False, "Optimizer API timeout"
    except ExternalServiceError as exc:
        return False, f"Optimizer validation failed: {exc.upstream_status_code or 502}"
    except Exception as exc:
        return False, f"Unexpected error: {redact_secret_like_text(str(exc))}"


async def validate_with_deployer(provider: str, credentials: dict) -> Tuple[bool, str]:
    """
    Validate credentials against the Deployer API.
    Requires full schema - infrastructure deployment permissions.
    
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        data = await DeployerClient().verify_permissions(normalize_provider_id(provider), credentials)
        return data.get("valid", False) or data.get("status") == "valid", data.get("message", "OK")
    except ExternalServiceUnavailable:
        return False, "Deployer API timeout"
    except ExternalServiceError as exc:
        return False, f"Deployer validation failed: {exc.upstream_status_code or 502}"
    except Exception as exc:
        return False, f"Unexpected error: {redact_secret_like_text(str(exc))}"


async def perform_dual_validation(
    provider: str,
    optimizer_creds: dict,
    deployer_creds: dict
) -> Dict[str, Any]:
    """
    Validate credentials against BOTH Optimizer and Deployer APIs in parallel.
    
    Args:
        provider: Cloud provider (aws, azure, gcp)
        optimizer_creds: Credentials formatted for Optimizer API
        deployer_creds: Credentials formatted for Deployer API
        
    Returns:
        Dict with 'optimizer' and 'deployer' results, each containing 'valid' and 'message'
    """
    # Run both validations in parallel
    optimizer_task = asyncio.create_task(
        validate_with_optimizer(provider, optimizer_creds)
    )
    deployer_task = asyncio.create_task(
        validate_with_deployer(provider, deployer_creds)
    )
    
    optimizer_valid, optimizer_msg = await optimizer_task
    deployer_valid, deployer_msg = await deployer_task
    
    return {
        "optimizer": {
            "valid": optimizer_valid,
            "message": optimizer_msg
        },
        "deployer": {
            "valid": deployer_valid,
            "message": deployer_msg
        },
        "overall_valid": optimizer_valid and deployer_valid
    }


def build_optimizer_credentials(provider: str, raw_credentials: dict) -> dict:
    """
    Build credentials dict in the format expected by Optimizer API.
    Optimizer uses simpler schema - just what's needed for pricing lookups.
    """
    provider_lower = normalize_provider_id(provider)
    
    if provider_lower == "aws":
        return {
            "access_key_id": raw_credentials.get("access_key_id"),
            "secret_access_key": raw_credentials.get("secret_access_key"),
            "region": raw_credentials.get("region", "us-east-1")
        }
    elif provider_lower == "azure":
        return {
            "subscription_id": raw_credentials.get("subscription_id"),
            "tenant_id": raw_credentials.get("tenant_id"),
            "client_id": raw_credentials.get("client_id"),
            "client_secret": raw_credentials.get("client_secret")
        }
    elif provider_lower == "gcp":
        return {
            "project_id": raw_credentials.get("project_id"),
            "service_account_json": raw_credentials.get("service_account_json")
        }
    else:
        return raw_credentials


def build_deployer_credentials(provider: str, raw_credentials: dict) -> dict:
    """
    Build credentials dict in the format expected by Deployer API.
    Deployer requires full schema for infrastructure deployment.
    """
    provider_lower = normalize_provider_id(provider)
    
    if provider_lower == "aws":
        return {
            "access_key_id": raw_credentials.get("access_key_id"),
            "secret_access_key": raw_credentials.get("secret_access_key"),
            "region": raw_credentials.get("region", "us-east-1"),
            "account_id": raw_credentials.get("account_id")
        }
    elif provider_lower == "azure":
        return {
            "subscription_id": raw_credentials.get("subscription_id"),
            "tenant_id": raw_credentials.get("tenant_id"),
            "client_id": raw_credentials.get("client_id"),
            "client_secret": raw_credentials.get("client_secret"),
            "resource_group": raw_credentials.get("resource_group")
        }
    elif provider_lower == "gcp":
        return {
            "project_id": raw_credentials.get("project_id"),
            "service_account_json": raw_credentials.get("service_account_json"),
            "region": raw_credentials.get("region", "us-central1")
        }
    else:
        return raw_credentials


def get_required_fields(provider: str) -> Dict[str, list]:
    """
    Get required credential fields for each provider.
    Returns separate lists for optimizer and deployer.
    """
    provider_lower = normalize_provider_id(provider)
    
    requirements = {
        "aws": {
            "optimizer": ["access_key_id", "secret_access_key"],
            "deployer": ["access_key_id", "secret_access_key", "region"]
        },
        "azure": {
            "optimizer": ["subscription_id", "tenant_id", "client_id", "client_secret"],
            "deployer": ["subscription_id", "tenant_id", "client_id", "client_secret"]
        },
        "gcp": {
            "optimizer": ["project_id", "service_account_json"],
            "deployer": ["project_id", "service_account_json"]
        }
    }
    
    return requirements.get(provider_lower, {"optimizer": [], "deployer": []})
