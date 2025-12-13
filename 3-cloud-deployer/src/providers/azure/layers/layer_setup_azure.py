"""
Azure Setup Layer - Foundational Resource Management.

This module contains functions to create/destroy/check foundational Azure resources
that must exist before any other deployment can proceed.

Resources managed:
- Resource Group: Container for all twin resources
- User-Assigned Managed Identity: Shared identity for all Function Apps
- Storage Account: Required for Function App deployments

Deployment Order:
    1. Resource Group (must be first)
    2. Managed Identity
    3. Storage Account

Note:
    This module mirrors the AWS `layer_X_*.py` pattern but is unique to Azure
    since AWS does not require a pre-deployment setup layer.
"""

from typing import TYPE_CHECKING, Optional
import logging

from azure.core.exceptions import (
    ResourceNotFoundError,
    HttpResponseError,
    ClientAuthenticationError,
    AzureError
)

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


# ==========================================
# Resource Group Management
# ==========================================

def create_resource_group(provider: 'AzureProvider', location: str = "westeurope") -> str:
    """
    Create the Resource Group for the digital twin.
    
    The Resource Group is the foundational container for ALL Azure resources
    in a digital twin deployment. It must be created before any other resources.
    
    Args:
        provider: Azure Provider instance with initialized clients
        location: Azure region for the Resource Group (default: westeurope)
    
    Returns:
        The Resource Group name
    
    Raises:
        azure.core.exceptions.HttpResponseError: If creation fails
    """
    rg_name = provider.naming.resource_group()
    
    logger.info(f"Creating Resource Group: {rg_name} in {location}")
    
    try:
        # Resource Groups are idempotent - create_or_update handles existing RGs
        provider.clients["resource"].resource_groups.create_or_update(
            resource_group_name=rg_name,
            parameters={"location": location}
        )
        
        logger.info(f"✓ Resource Group created: {rg_name}")
        return rg_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating Resource Group: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create Resource Group: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating Resource Group: {type(e).__name__}: {e}")
        raise


def destroy_resource_group(provider: 'AzureProvider') -> None:
    """
    Delete the Resource Group and ALL resources within it.
    
    Warning:
        This is a destructive operation that will delete ALL resources
        in the digital twin's Resource Group.
    
    Args:
        provider: Azure Provider instance
    """
    rg_name = provider.naming.resource_group()
    
    logger.info(f"Deleting Resource Group: {rg_name}")
    
    try:
        # begin_delete returns a poller for async operation
        poller = provider.clients["resource"].resource_groups.begin_delete(rg_name)
        # Wait for completion
        poller.result()
        logger.info(f"✓ Resource Group deleted: {rg_name}")
    except ResourceNotFoundError:
        logger.info(f"Resource Group already deleted: {rg_name}")


def check_resource_group(provider: 'AzureProvider') -> bool:
    """
    Check if the Resource Group exists.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        True if the Resource Group exists, False otherwise
    """
    rg_name = provider.naming.resource_group()
    
    try:
        provider.clients["resource"].resource_groups.get(rg_name)
        logger.info(f"✓ Resource Group exists: {rg_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Resource Group not found: {rg_name}")
        return False


# ==========================================
# Managed Identity Management
# ==========================================

def create_managed_identity(provider: 'AzureProvider') -> dict:
    """
    Create User-Assigned Managed Identity for the digital twin.
    
    This identity is shared by all Function Apps in the twin and is used
    to access Azure resources (Cosmos DB, Blob Storage, IoT Hub) without
    storing credentials.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        Dictionary with identity info: {id, client_id, principal_id}
    
    Note:
        Permissions are NOT granted here. They are granted when each
        resource (Cosmos DB, Storage, etc.) is created in other layers.
    """
    rg_name = provider.naming.resource_group()
    identity_name = provider.naming.managed_identity()
    location = provider.location
    
    logger.info(f"Creating Managed Identity: {identity_name}")
    
    try:
        # Create or update the identity
        identity = provider.clients["msi"].user_assigned_identities.create_or_update(
            resource_group_name=rg_name,
            resource_name=identity_name,
            parameters={"location": location}
        )
        
        result = {
            "id": identity.id,
            "client_id": identity.client_id,
            "principal_id": identity.principal_id
        }
        
        logger.info(f"✓ Managed Identity created: {identity_name}")
        logger.info(f"  Client ID: {identity.client_id}")
        
        return result
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating Managed Identity: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create Managed Identity: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating Managed Identity: {type(e).__name__}: {e}")
        raise


def destroy_managed_identity(provider: 'AzureProvider') -> None:
    """
    Delete the User-Assigned Managed Identity.
    
    Args:
        provider: Azure Provider instance
    """
    rg_name = provider.naming.resource_group()
    identity_name = provider.naming.managed_identity()
    
    logger.info(f"Deleting Managed Identity: {identity_name}")
    
    try:
        provider.clients["msi"].user_assigned_identities.delete(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        logger.info(f"✓ Managed Identity deleted: {identity_name}")
    except ResourceNotFoundError:
        logger.info(f"Managed Identity already deleted: {identity_name}")


def check_managed_identity(provider: 'AzureProvider') -> bool:
    """
    Check if the Managed Identity exists.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        True if identity exists, False otherwise
    """
    rg_name = provider.naming.resource_group()
    identity_name = provider.naming.managed_identity()
    
    try:
        provider.clients["msi"].user_assigned_identities.get(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        logger.info(f"✓ Managed Identity exists: {identity_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Managed Identity not found: {identity_name}")
        return False


def get_managed_identity_id(provider: 'AzureProvider') -> Optional[str]:
    """
    Get the full resource ID of the Managed Identity.
    
    This ID is needed when assigning the identity to Function Apps.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        Full resource ID string, or None if identity doesn't exist
    """
    rg_name = provider.naming.resource_group()
    identity_name = provider.naming.managed_identity()
    
    try:
        identity = provider.clients["msi"].user_assigned_identities.get(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        return identity.id
    except ResourceNotFoundError:
        return None


# ==========================================
# Storage Account Management
# ==========================================

def create_storage_account(provider: 'AzureProvider') -> str:
    """
    Create Storage Account for Function App deployments.
    
    Azure Functions require a Storage Account to store deployment packages,
    function state, and logs.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        Storage account name
    
    Note:
        Storage account names must be 3-24 chars, lowercase alphanumeric only.
        The naming module handles this constraint.
    """
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    location = provider.location
    
    logger.info(f"Creating Storage Account: {storage_name}")
    
    try:
        # Create storage account with Standard_LRS for cost efficiency
        poller = provider.clients["storage"].storage_accounts.begin_create(
            resource_group_name=rg_name,
            account_name=storage_name,
            parameters={
                "location": location,
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
                "properties": {
                    "supportsHttpsTrafficOnly": True,
                    "minimumTlsVersion": "TLS1_2"
                }
            }
        )
        
        # Wait for completion
        poller.result()
        
        logger.info(f"✓ Storage Account created: {storage_name}")
        return storage_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating Storage Account: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create Storage Account: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating Storage Account: {type(e).__name__}: {e}")
        raise


def destroy_storage_account(provider: 'AzureProvider') -> None:
    """
    Delete the Storage Account.
    
    Args:
        provider: Azure Provider instance
    """
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    
    logger.info(f"Deleting Storage Account: {storage_name}")
    
    try:
        provider.clients["storage"].storage_accounts.delete(
            resource_group_name=rg_name,
            account_name=storage_name
        )
        logger.info(f"✓ Storage Account deleted: {storage_name}")
    except ResourceNotFoundError:
        logger.info(f"Storage Account already deleted: {storage_name}")


def check_storage_account(provider: 'AzureProvider') -> bool:
    """
    Check if the Storage Account exists.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        True if storage account exists, False otherwise
    """
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    
    try:
        provider.clients["storage"].storage_accounts.get_properties(
            resource_group_name=rg_name,
            account_name=storage_name
        )
        logger.info(f"✓ Storage Account exists: {storage_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Storage Account not found: {storage_name}")
        return False
