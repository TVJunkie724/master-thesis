"""
Azure Layer 3 (Storage) Component Implementations.

This module contains ALL L3 component implementations for Azure that are
deployed by the L3 adapter.

Components Managed:
    - Cosmos DB Account: Serverless NoSQL database instance
    - Cosmos DB Database: Container for IoT data
    - Hot Cosmos Container: Real-time data storage (L3 Hot tier)
    - Cold Blob Container: Recent historical data (L3 Cold tier, Cool access)
    - Archive Blob Container: Long-term storage (L3 Archive tier, Archive access)
    - L3 App Service Plan: Dedicated plan for L3 Function App
    - L3 Function App: Hosts Hot Reader and Mover functions
    - Hot Reader Function: Reads data for L4 Digital Twins
    - Hot Reader Last Entry Function: Single-entry variant
    - Hot-Cold Mover Function: Timer-triggered, moves old data to cold
    - Cold-Archive Mover Function: Timer-triggered, moves old data to archive

Architecture:
    L2 (Persister) → Cosmos DB (Hot) ← Hot Reader Functions → L4 (Digital Twins)
                          │
                          ├── Timer (daily) → Hot-Cold Mover → Blob Cool (Cold)
                          │                                         │
                          │                                         └── Timer (daily) → Cold-Archive Mover → Blob Archive
                          │
                          └── Multi-cloud: Hot Writer receives from remote L2 (deployed by L0)

Architecture Note:
    Azure uses Cosmos DB Serverless (pay-per-request) for hot storage,
    while AWS uses DynamoDB. Both are NoSQL key-value stores.
    
    For cold/archive, Azure uses Blob Storage access tiers (Cool/Archive)
    while AWS uses S3 storage classes.
    
    Timer triggers replace AWS EventBridge scheduled rules.

Authentication:
    - Same-cloud: Managed Identity for Cosmos DB and Blob access
    - Multi-cloud: X-Inter-Cloud-Token header for cross-cloud calls

Function Deployment:
    All L3 functions are deployed via Kudu zip deploy to the L3 Function App.
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging
import json
import os
import requests

from azure.core.exceptions import (
    AzureError,
    ResourceNotFoundError,
    HttpResponseError,
    ClientAuthenticationError,
    ServiceRequestError
)

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider
    from src.core.context import ProjectConfig

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def _get_digital_twin_info(config: 'ProjectConfig') -> dict:
    """Build digital twin info dict for Function environment."""
    return {
        "name": config.digital_twin_name,
        "devices": [
            {"id": d.get("id"), "type": d.get("type")}
            for d in (config.iot_devices or [])
        ]
    }


def _get_storage_connection_string(provider: 'AzureProvider') -> str:
    """Get the storage account connection string for Function App."""
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    
    keys = provider.clients["storage"].storage_accounts.list_keys(
        resource_group_name=rg_name,
        account_name=storage_name
    )
    
    key = keys.keys[0].value
    return f"DefaultEndpointsProtocol=https;AccountName={storage_name};AccountKey={key};EndpointSuffix=core.windows.net"


def _get_cosmos_connection_string(provider: 'AzureProvider') -> str:
    """Get the Cosmos DB connection string for Function App."""
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    
    keys = provider.clients["cosmos"].database_accounts.list_keys(
        resource_group_name=rg_name,
        account_name=account_name
    )
    
    # Build connection string
    return f"AccountEndpoint=https://{account_name}.documents.azure.com:443/;AccountKey={keys.primary_master_key};"


def _deploy_function_code_via_kudu(
    provider: 'AzureProvider',
    app_name: str,
    function_dir: str,
    project_path: str
) -> None:
    """
    Deploy function code to a Function App via Kudu zip deploy.
    
    Args:
        provider: Initialized AzureProvider
        app_name: Function App name
        function_dir: Path to function directory to deploy
        project_path: Root project path for resolving relative paths
        
    Raises:
        HttpResponseError: If Kudu deployment fails
    """
    rg_name = provider.naming.resource_group()
    
    # Get publish credentials
    logger.info("  Getting publish credentials...")
    creds = provider.clients["web"].web_apps.begin_list_publishing_credentials(
        resource_group_name=rg_name,
        name=app_name
    ).result()
    
    # Compile function code
    logger.info(f"  Compiling function code from {function_dir}...")
    import src.util as util
    zip_content = util.compile_azure_function(function_dir, project_path)
    
    # Deploy via Kudu using shared helper with retry
    from src.providers.azure.layers.deployment_helpers import deploy_to_kudu
    deploy_to_kudu(
        app_name=app_name,
        zip_content=zip_content,
        publish_username=creds.publishing_user_name,
        publish_password=creds.publishing_password
    )


# ==========================================
# 1. Cosmos DB Account
# ==========================================

def create_cosmos_account(provider: 'AzureProvider') -> str:
    """
    Create an Azure Cosmos DB Account (Serverless mode).
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The Cosmos DB account name
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    location = provider.location
    
    logger.info(f"Creating Cosmos DB Account: {account_name}")
    
    # Cosmos DB Serverless configuration
    params = {
        "location": location,
        "kind": "GlobalDocumentDB",
        "database_account_offer_type": "Standard",
        "capabilities": [
            {"name": "EnableServerless"}
        ],
        "locations": [
            {
                "location_name": location,
                "failover_priority": 0,
                "is_zone_redundant": False
            }
        ],
        "consistency_policy": {
            "default_consistency_level": "Session"
        }
    }
    
    try:
        poller = provider.clients["cosmos"].database_accounts.begin_create_or_update(
            resource_group_name=rg_name,
            account_name=account_name,
            create_update_parameters=params
        )
        account = poller.result()
        logger.info(f"✓ Cosmos DB Account created: {account_name}")
        return account_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating Cosmos DB Account: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"HTTP error creating Cosmos DB Account: {e.status_code} - {e.message}")
        raise


def destroy_cosmos_account(provider: 'AzureProvider') -> None:
    """
    Delete the Cosmos DB Account.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    
    logger.info(f"Deleting Cosmos DB Account: {account_name}")
    
    try:
        poller = provider.clients["cosmos"].database_accounts.begin_delete(
            resource_group_name=rg_name,
            account_name=account_name
        )
        poller.result()
        logger.info(f"✓ Cosmos DB Account deleted: {account_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ Cosmos DB Account not found (already deleted): {account_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting Cosmos DB Account: {e.message}")
        raise


def check_cosmos_account(provider: 'AzureProvider') -> bool:
    """
    Check if the Cosmos DB Account exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if account exists, False otherwise
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    
    try:
        provider.clients["cosmos"].database_accounts.get(
            resource_group_name=rg_name,
            account_name=account_name
        )
        logger.info(f"✓ Cosmos DB Account exists: {account_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Cosmos DB Account not found: {account_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking Cosmos DB Account: {e.message}")
        raise


# ==========================================
# 2. Cosmos DB Database
# ==========================================

def create_cosmos_database(provider: 'AzureProvider') -> str:
    """
    Create the Cosmos DB Database for IoT data.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The database name
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    database_name = provider.naming.cosmos_database()
    
    logger.info(f"Creating Cosmos DB Database: {database_name}")
    
    params = {
        "resource": {
            "id": database_name
        }
    }
    
    try:
        poller = provider.clients["cosmos"].sql_resources.begin_create_update_sql_database(
            resource_group_name=rg_name,
            account_name=account_name,
            database_name=database_name,
            create_update_sql_database_parameters=params
        )
        poller.result()
        logger.info(f"✓ Cosmos DB Database created: {database_name}")
        return database_name
    except HttpResponseError as e:
        logger.error(f"HTTP error creating Cosmos DB Database: {e.status_code} - {e.message}")
        raise


def destroy_cosmos_database(provider: 'AzureProvider') -> None:
    """
    Delete the Cosmos DB Database.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    database_name = provider.naming.cosmos_database()
    
    logger.info(f"Deleting Cosmos DB Database: {database_name}")
    
    try:
        poller = provider.clients["cosmos"].sql_resources.begin_delete_sql_database(
            resource_group_name=rg_name,
            account_name=account_name,
            database_name=database_name
        )
        poller.result()
        logger.info(f"✓ Cosmos DB Database deleted: {database_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ Cosmos DB Database not found (already deleted): {database_name}")


def check_cosmos_database(provider: 'AzureProvider') -> bool:
    """
    Check if the Cosmos DB Database exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if database exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    database_name = provider.naming.cosmos_database()
    
    try:
        provider.clients["cosmos"].sql_resources.get_sql_database(
            resource_group_name=rg_name,
            account_name=account_name,
            database_name=database_name
        )
        logger.info(f"✓ Cosmos DB Database exists: {database_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Cosmos DB Database not found: {database_name}")
        return False


# ==========================================
# 3. Hot Cosmos Container
# ==========================================

def create_hot_cosmos_container(provider: 'AzureProvider') -> str:
    """
    Create the Hot Cosmos Container for real-time data.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The container name
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    database_name = provider.naming.cosmos_database()
    container_name = provider.naming.hot_cosmos_container()
    
    logger.info(f"Creating Hot Cosmos Container: {container_name}")
    
    params = {
        "resource": {
            "id": container_name,
            "partition_key": {
                "paths": ["/device_id"],
                "kind": "Hash"
            }
        }
    }
    
    try:
        poller = provider.clients["cosmos"].sql_resources.begin_create_update_sql_container(
            resource_group_name=rg_name,
            account_name=account_name,
            database_name=database_name,
            container_name=container_name,
            create_update_sql_container_parameters=params
        )
        poller.result()
        logger.info(f"✓ Hot Cosmos Container created: {container_name}")
        return container_name
    except HttpResponseError as e:
        logger.error(f"HTTP error creating Hot Cosmos Container: {e.status_code} - {e.message}")
        raise


def destroy_hot_cosmos_container(provider: 'AzureProvider') -> None:
    """
    Delete the Hot Cosmos Container.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    database_name = provider.naming.cosmos_database()
    container_name = provider.naming.hot_cosmos_container()
    
    logger.info(f"Deleting Hot Cosmos Container: {container_name}")
    
    try:
        poller = provider.clients["cosmos"].sql_resources.begin_delete_sql_container(
            resource_group_name=rg_name,
            account_name=account_name,
            database_name=database_name,
            container_name=container_name
        )
        poller.result()
        logger.info(f"✓ Hot Cosmos Container deleted: {container_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ Hot Cosmos Container not found (already deleted): {container_name}")


def check_hot_cosmos_container(provider: 'AzureProvider') -> bool:
    """
    Check if the Hot Cosmos Container exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if container exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    account_name = provider.naming.cosmos_account()
    database_name = provider.naming.cosmos_database()
    container_name = provider.naming.hot_cosmos_container()
    
    try:
        provider.clients["cosmos"].sql_resources.get_sql_container(
            resource_group_name=rg_name,
            account_name=account_name,
            database_name=database_name,
            container_name=container_name
        )
        logger.info(f"✓ Hot Cosmos Container exists: {container_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Hot Cosmos Container not found: {container_name}")
        return False


# ==========================================
# 4. Cold Blob Container
# ==========================================

def create_cold_blob_container(provider: 'AzureProvider') -> str:
    """
    Create the Cold Blob Container for recent historical data.
    
    Uses Cool access tier for cost-effective storage of infrequently accessed data.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The container name
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    container_name = provider.naming.cold_blob_container()
    
    logger.info(f"Creating Cold Blob Container: {container_name}")
    
    try:
        provider.clients["blob"].blob_containers.create(
            resource_group_name=rg_name,
            account_name=storage_name,
            container_name=container_name,
            blob_container={
                "default_encryption_scope": "$account-encryption-key",
                "deny_encryption_scope_override": False,
                "public_access": "None"
            }
        )
        logger.info(f"✓ Cold Blob Container created: {container_name}")
        return container_name
    except HttpResponseError as e:
        if "ContainerAlreadyExists" in str(e):
            logger.info(f"✓ Cold Blob Container already exists: {container_name}")
            return container_name
        logger.error(f"HTTP error creating Cold Blob Container: {e.status_code} - {e.message}")
        raise


def destroy_cold_blob_container(provider: 'AzureProvider') -> None:
    """
    Delete the Cold Blob Container.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    container_name = provider.naming.cold_blob_container()
    
    logger.info(f"Deleting Cold Blob Container: {container_name}")
    
    try:
        provider.clients["blob"].blob_containers.delete(
            resource_group_name=rg_name,
            account_name=storage_name,
            container_name=container_name
        )
        logger.info(f"✓ Cold Blob Container deleted: {container_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ Cold Blob Container not found (already deleted): {container_name}")


def check_cold_blob_container(provider: 'AzureProvider') -> bool:
    """
    Check if the Cold Blob Container exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if container exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    container_name = provider.naming.cold_blob_container()
    
    try:
        provider.clients["blob"].blob_containers.get(
            resource_group_name=rg_name,
            account_name=storage_name,
            container_name=container_name
        )
        logger.info(f"✓ Cold Blob Container exists: {container_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Cold Blob Container not found: {container_name}")
        return False


# ==========================================
# 5. Archive Blob Container
# ==========================================

def create_archive_blob_container(provider: 'AzureProvider') -> str:
    """
    Create the Archive Blob Container for long-term storage.
    
    Uses Archive access tier for lowest-cost storage.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The container name
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    container_name = provider.naming.archive_blob_container()
    
    logger.info(f"Creating Archive Blob Container: {container_name}")
    
    try:
        provider.clients["blob"].blob_containers.create(
            resource_group_name=rg_name,
            account_name=storage_name,
            container_name=container_name,
            blob_container={
                "default_encryption_scope": "$account-encryption-key",
                "deny_encryption_scope_override": False,
                "public_access": "None"
            }
        )
        logger.info(f"✓ Archive Blob Container created: {container_name}")
        return container_name
    except HttpResponseError as e:
        if "ContainerAlreadyExists" in str(e):
            logger.info(f"✓ Archive Blob Container already exists: {container_name}")
            return container_name
        logger.error(f"HTTP error creating Archive Blob Container: {e.status_code} - {e.message}")
        raise


def destroy_archive_blob_container(provider: 'AzureProvider') -> None:
    """
    Delete the Archive Blob Container.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    container_name = provider.naming.archive_blob_container()
    
    logger.info(f"Deleting Archive Blob Container: {container_name}")
    
    try:
        provider.clients["blob"].blob_containers.delete(
            resource_group_name=rg_name,
            account_name=storage_name,
            container_name=container_name
        )
        logger.info(f"✓ Archive Blob Container deleted: {container_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ Archive Blob Container not found (already deleted): {container_name}")


def check_archive_blob_container(provider: 'AzureProvider') -> bool:
    """
    Check if the Archive Blob Container exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if container exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    container_name = provider.naming.archive_blob_container()
    
    try:
        provider.clients["blob"].blob_containers.get(
            resource_group_name=rg_name,
            account_name=storage_name,
            container_name=container_name
        )
        logger.info(f"✓ Archive Blob Container exists: {container_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Archive Blob Container not found: {container_name}")
        return False


# ==========================================
# 6. L3 App Service Plan
# ==========================================

def create_l3_app_service_plan(provider: 'AzureProvider') -> str:
    """
    Create the App Service Plan for L3 Function App.
    
    Each layer has its own dedicated App Service Plan
    (per AI Layer Guide §2.5 - Function App Isolation).
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        App Service Plan resource ID
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l3_app_service_plan()
    location = provider.location
    
    logger.info(f"Creating L3 App Service Plan: {plan_name}")
    
    from azure.mgmt.web.models import AppServicePlan, SkuDescription
    
    plan_params = AppServicePlan(
        location=location,
        reserved=True,  # Required for Linux
        sku=SkuDescription(
            name="Y1",
            tier="Dynamic",
            size="Y1",
            family="Y",
            capacity=0
        ),
        kind="functionapp"
    )
    
    try:
        poller = provider.clients["web"].app_service_plans.begin_create_or_update(
            resource_group_name=rg_name,
            name=plan_name,
            app_service_plan=plan_params
        )
        plan = poller.result()
        logger.info(f"✓ L3 App Service Plan created: {plan_name}")
        return plan.id
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L3 App Service Plan: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"HTTP error creating L3 App Service Plan: {e.status_code} - {e.message}")
        raise


def destroy_l3_app_service_plan(provider: 'AzureProvider') -> None:
    """
    Delete the L3 App Service Plan.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l3_app_service_plan()
    
    logger.info(f"Deleting L3 App Service Plan: {plan_name}")
    
    try:
        provider.clients["web"].app_service_plans.delete(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L3 App Service Plan deleted: {plan_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ L3 App Service Plan not found (already deleted): {plan_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting L3 App Service Plan: {e.message}")
        raise


def check_l3_app_service_plan(provider: 'AzureProvider') -> bool:
    """
    Check if the L3 App Service Plan exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if App Service Plan exists, False otherwise
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l3_app_service_plan()
    
    try:
        provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L3 App Service Plan exists: {plan_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L3 App Service Plan not found: {plan_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking L3 App Service Plan: {e.message}")
        raise


# ==========================================
# 7. L3 Function App
# ==========================================

def create_l3_function_app(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> str:
    """
    Create the L3 Function App for hosting storage functions.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        
    Returns:
        Function App name
        
    Raises:
        ValueError: If provider or config is None
        HttpResponseError: If creation fails
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    plan_name = provider.naming.l3_app_service_plan()
    storage_name = provider.naming.storage_account()
    location = provider.location
    
    logger.info(f"Creating L3 Function App: {app_name}")
    
    # Get Managed Identity ID
    from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
    identity_id = get_managed_identity_id(provider)
    
    # Get App Service Plan ID
    plan = provider.clients["web"].app_service_plans.get(
        resource_group_name=rg_name,
        name=plan_name
    )
    
    from azure.mgmt.web.models import Site, SiteConfig, ManagedServiceIdentity
    
    site_config = SiteConfig(
        linux_fx_version="PYTHON|3.11",
        app_settings=[]
    )
    
    params = Site(
        location=location,
        server_farm_id=plan.id,
        site_config=site_config,
        kind="functionapp,linux",
        identity=ManagedServiceIdentity(
            type="UserAssigned",
            user_assigned_identities={identity_id: {}}
        ),
        https_only=True
    )
    
    try:
        poller = provider.clients["web"].web_apps.begin_create_or_update(
            resource_group_name=rg_name,
            name=app_name,
            site_envelope=params
        )
        app = poller.result()
        
        # Configure app settings
        _configure_l3_function_app_settings(provider, config, storage_name)
        
        logger.info(f"✓ L3 Function App created: {app_name}")
        return app_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L3 Function App: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"HTTP error creating L3 Function App: {e.status_code} - {e.message}")
        raise


def _configure_l3_function_app_settings(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    storage_name: str
) -> None:
    """Configure L3 Function App settings and environment variables."""
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    
    logger.info(f"  Configuring L3 Function App settings...")
    
    storage_conn = _get_storage_connection_string(provider)
    cosmos_conn = _get_cosmos_connection_string(provider)
    
    settings = {
        "AzureWebJobsStorage": storage_conn,
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "FUNCTIONS_EXTENSION_VERSION": "~4",
        "WEBSITE_RUN_FROM_PACKAGE": "0",
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
        "COSMOS_CONNECTION_STRING": cosmos_conn,
        "COSMOS_DATABASE_NAME": provider.naming.cosmos_database(),
        "COSMOS_CONTAINER_NAME": provider.naming.hot_cosmos_container(),
        "COLD_BLOB_CONTAINER": provider.naming.cold_blob_container(),
        "ARCHIVE_BLOB_CONTAINER": provider.naming.archive_blob_container(),
        "STORAGE_CONNECTION_STRING": storage_conn,
    }
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )
    
    logger.info(f"  ✓ L3 Function App settings configured")


def destroy_l3_function_app(provider: 'AzureProvider') -> None:
    """
    Delete the L3 Function App.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    
    logger.info(f"Deleting L3 Function App: {app_name}")
    
    try:
        provider.clients["web"].web_apps.delete(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L3 Function App deleted: {app_name}")
    except ResourceNotFoundError:
        logger.info(f"✗ L3 Function App not found (already deleted): {app_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting L3 Function App: {e.message}")
        raise


def check_l3_function_app(provider: 'AzureProvider') -> bool:
    """
    Check if the L3 Function App exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if Function App exists, False otherwise
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    
    try:
        provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L3 Function App exists: {app_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L3 Function App not found: {app_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking L3 Function App: {e.message}")
        raise


# ==========================================
# 8. Hot Reader Function
# ==========================================

def deploy_hot_reader_function(
    provider: 'AzureProvider',
    project_path: str
) -> None:
    """
    Deploy the Hot Reader function to L3 Function App.
    
    The Hot Reader fetches data from Cosmos DB for L4 Digital Twins.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        project_path: Path to the project for function code
        
    Raises:
        ValueError: If required parameters are None
        HttpResponseError: If deployment fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    app_name = provider.naming.l3_function_app()
    hot_reader_dir = os.path.join(project_path, "azure_functions", "hot-reader")
    
    logger.info(f"Deploying Hot Reader function to {app_name}...")
    
    if not os.path.exists(hot_reader_dir):
        logger.warning(f"  No hot-reader function found at {hot_reader_dir}. Users must provide their own.")
        return
    
    _deploy_function_code_via_kudu(provider, app_name, hot_reader_dir, project_path)
    
    logger.info(f"✓ Hot Reader function deployed")


def destroy_hot_reader_function(provider: 'AzureProvider') -> None:
    """
    Destroy the Hot Reader function.
    
    Note: In Azure, individual functions are removed with the Function App
    or by redeploying without that function.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    logger.info("✗ Hot Reader function will be removed with L3 Function App")


def check_hot_reader_function(provider: 'AzureProvider') -> bool:
    """
    Check if the Hot Reader function exists in L3 Function App.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if function exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    function_name = "hot-reader"
    
    try:
        functions = provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        )
        
        for func in functions:
            if function_name in func.name.lower():
                logger.info(f"✓ Hot Reader function exists in {app_name}")
                return True
        
        logger.info(f"✗ Hot Reader function not found in {app_name}")
        return False
    except ResourceNotFoundError:
        logger.info(f"✗ L3 Function App not found: {app_name}")
        return False


# ==========================================
# 9. Hot Reader Last Entry Function
# ==========================================

def deploy_hot_reader_last_entry_function(
    provider: 'AzureProvider',
    project_path: str
) -> None:
    """
    Deploy the Hot Reader Last Entry function to L3 Function App.
    
    The Hot Reader Last Entry fetches the most recent data point from Cosmos DB.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        project_path: Path to the project for function code
        
    Raises:
        ValueError: If required parameters are None
        HttpResponseError: If deployment fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    app_name = provider.naming.l3_function_app()
    function_dir = os.path.join(project_path, "azure_functions", "hot-reader-last-entry")
    
    logger.info(f"Deploying Hot Reader Last Entry function to {app_name}...")
    
    if not os.path.exists(function_dir):
        logger.warning(f"  No hot-reader-last-entry function found. Users must provide their own.")
        return
    
    _deploy_function_code_via_kudu(provider, app_name, function_dir, project_path)
    
    logger.info(f"✓ Hot Reader Last Entry function deployed")


def destroy_hot_reader_last_entry_function(provider: 'AzureProvider') -> None:
    """Destroy the Hot Reader Last Entry function."""
    logger.info("✗ Hot Reader Last Entry function will be removed with L3 Function App")


def check_hot_reader_last_entry_function(provider: 'AzureProvider') -> bool:
    """Check if the Hot Reader Last Entry function exists."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    function_name = "hot-reader-last-entry"
    
    try:
        functions = provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        )
        
        for func in functions:
            if function_name in func.name.lower():
                logger.info(f"✓ Hot Reader Last Entry function exists in {app_name}")
                return True
        
        logger.info(f"✗ Hot Reader Last Entry function not found in {app_name}")
        return False
    except ResourceNotFoundError:
        return False


# ==========================================
# 10. Hot-Cold Mover Function
# ==========================================

def deploy_hot_cold_mover_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Deploy the Hot-Cold Mover function to L3 Function App.
    
    The Hot-Cold Mover is timer-triggered (daily) and moves old data
    from Cosmos DB to Blob Cool storage.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to the project for function code
        
    Raises:
        ValueError: If required parameters are None
        HttpResponseError: If deployment fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    app_name = provider.naming.l3_function_app()
    function_dir = os.path.join(project_path, "azure_functions", "hot-cold-mover")
    
    logger.info(f"Deploying Hot-Cold Mover function to {app_name}...")
    
    if not os.path.exists(function_dir):
        logger.warning(f"  No hot-cold-mover function found. Users must provide their own.")
        return
    
    _deploy_function_code_via_kudu(provider, app_name, function_dir, project_path)
    
    logger.info(f"✓ Hot-Cold Mover function deployed (timer: daily at midnight)")


def destroy_hot_cold_mover_function(provider: 'AzureProvider') -> None:
    """Destroy the Hot-Cold Mover function."""
    logger.info("✗ Hot-Cold Mover function will be removed with L3 Function App")


def check_hot_cold_mover_function(provider: 'AzureProvider') -> bool:
    """Check if the Hot-Cold Mover function exists."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    function_name = "hot-cold-mover"
    
    try:
        functions = provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        )
        
        for func in functions:
            if function_name in func.name.lower():
                logger.info(f"✓ Hot-Cold Mover function exists in {app_name}")
                return True
        
        logger.info(f"✗ Hot-Cold Mover function not found in {app_name}")
        return False
    except ResourceNotFoundError:
        return False


# ==========================================
# 11. Cold-Archive Mover Function
# ==========================================

def deploy_cold_archive_mover_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Deploy the Cold-Archive Mover function to L3 Function App.
    
    The Cold-Archive Mover is timer-triggered (daily) and moves old data
    from Blob Cool storage to Blob Archive storage.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to the project for function code
        
    Raises:
        ValueError: If required parameters are None
        HttpResponseError: If deployment fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    app_name = provider.naming.l3_function_app()
    function_dir = os.path.join(project_path, "azure_functions", "cold-archive-mover")
    
    logger.info(f"Deploying Cold-Archive Mover function to {app_name}...")
    
    if not os.path.exists(function_dir):
        logger.warning(f"  No cold-archive-mover function found. Users must provide their own.")
        return
    
    _deploy_function_code_via_kudu(provider, app_name, function_dir, project_path)
    
    logger.info(f"✓ Cold-Archive Mover function deployed (timer: daily at midnight)")


def destroy_cold_archive_mover_function(provider: 'AzureProvider') -> None:
    """Destroy the Cold-Archive Mover function."""
    logger.info("✗ Cold-Archive Mover function will be removed with L3 Function App")


def check_cold_archive_mover_function(provider: 'AzureProvider') -> bool:
    """Check if the Cold-Archive Mover function exists."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l3_function_app()
    function_name = "cold-archive-mover"
    
    try:
        functions = provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        )
        
        for func in functions:
            if function_name in func.name.lower():
                logger.info(f"✓ Cold-Archive Mover function exists in {app_name}")
                return True
        
        logger.info(f"✗ Cold-Archive Mover function not found in {app_name}")
        return False
    except ResourceNotFoundError:
        return False


# ==========================================
# 12. Info/Status Functions
# ==========================================

def info_l3(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Check status of Layer 3 (Storage) components for Azure.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of all L3 components
    """
    from src.core.context import DeploymentContext
    
    logger.info(f"[L3] Checking status for {context.config.digital_twin_name}")
    
    status = {
        # Hot tier
        "cosmos_account": check_cosmos_account(provider),
        "cosmos_database": check_cosmos_database(provider) if check_cosmos_account(provider) else False,
        "hot_cosmos_container": check_hot_cosmos_container(provider) if check_cosmos_account(provider) else False,
        "hot_reader_function": check_hot_reader_function(provider),
        "hot_reader_last_entry_function": check_hot_reader_last_entry_function(provider),
        
        # Cold tier
        "cold_blob_container": check_cold_blob_container(provider),
        "hot_cold_mover_function": check_hot_cold_mover_function(provider),
        
        # Archive tier
        "archive_blob_container": check_archive_blob_container(provider),
        "cold_archive_mover_function": check_cold_archive_mover_function(provider),
        
        # Infrastructure
        "l3_app_service_plan": check_l3_app_service_plan(provider),
        "l3_function_app": check_l3_function_app(provider),
    }
    
    return status
