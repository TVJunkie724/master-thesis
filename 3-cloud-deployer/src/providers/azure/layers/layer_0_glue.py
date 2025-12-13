"""
Layer 0 (Glue) Component Implementations for Azure.

This module contains ALL multi-cloud receiver implementations that are
deployed by the L0 adapter BEFORE the normal layer deployment.

Components Managed:
- Glue Function App: Container for all L0 functions
- Ingestion Function: Receives data from remote L1 (when L1 ≠ L2)
- Hot Writer Function: Writes to Cosmos DB from remote L2 (when L2 ≠ L3)
- Cold Writer Function: Writes to Blob from remote L3 Hot (when L3 Hot ≠ L3 Cold)
- Archive Writer Function: Writes to Archive from remote L3 Cold (when L3 Cold ≠ L3 Archive)
- Hot Reader Endpoints: Exposes Hot Reader for remote L4 (when L3 ≠ L4)

Architecture Note:
    Unlike AWS where each Lambda is a separate resource, Azure groups
    functions into a Function App. All L0 functions share one Function App.

Authentication:
    - Cross-cloud calls: X-Inter-Cloud-Token header (custom token)
    - Azure-only calls: Function Keys (Azure-managed)
"""

from typing import TYPE_CHECKING, Optional
import logging
import secrets
import os

from azure.core.exceptions import ResourceNotFoundError, HttpResponseError, ClientAuthenticationError, AzureError

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider
    from src.core.context import ProjectConfig

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def _get_digital_twin_info(config: 'ProjectConfig') -> dict:
    """
    Build digital twin info dict for Function App environment.
    
    This mirrors the AWS Lambda environment variable pattern.
    """
    return {
        "twin_name": config.digital_twin_name,
        "mode": config.mode,
        "hot_storage_days": str(config.hot_storage_size_in_days),
        "cold_storage_days": str(config.cold_storage_size_in_days),
    }


# ==========================================
# App Service Plan (Consumption)
# ==========================================

def create_consumption_app_service_plan(provider: 'AzureProvider') -> str:
    """
    Create Y1 Consumption App Service Plan for serverless functions.
    
    The Consumption plan (Y1 SKU) provides:
    - Pay-per-execution pricing
    - Auto-scaling
    - Free tier: 1M executions/month, 400K GB-s/month
    
    Args:
        provider: Azure Provider instance
        
    Returns:
        Full resource ID of the App Service Plan
    """
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.glue_app_service_plan()
    location = provider.location
    
    logger.info(f"Creating Consumption App Service Plan: {plan_name}")
    
    try:
        poller = provider.clients["web"].app_service_plans.begin_create_or_update(
            resource_group_name=rg_name,
            name=plan_name,
            app_service_plan={
                "location": location,
                "kind": "functionapp",
                "sku": {"name": "Y1", "tier": "Dynamic"},
                "properties": {"reserved": True}  # Linux
            }
        )
        poller.result()
        
        plan_id = f"/subscriptions/{provider.subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Web/serverfarms/{plan_name}"
        logger.info(f"✓ App Service Plan created: {plan_name}")
        return plan_id
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating App Service Plan: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create App Service Plan: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating App Service Plan: {type(e).__name__}: {e}")
        raise


def destroy_consumption_app_service_plan(provider: 'AzureProvider') -> None:
    """Delete the Consumption App Service Plan."""
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.glue_app_service_plan()
    
    logger.info(f"Deleting App Service Plan: {plan_name}")
    
    try:
        provider.clients["web"].app_service_plans.delete(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ App Service Plan deleted: {plan_name}")
    except ResourceNotFoundError:
        logger.info(f"App Service Plan already deleted: {plan_name}")


def check_consumption_app_service_plan(provider: 'AzureProvider') -> bool:
    """
    Check if the Consumption App Service Plan exists.
    
    Args:
        provider: Azure Provider instance
        
    Returns:
        True if App Service Plan exists, False otherwise
    """
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.glue_app_service_plan()
    
    try:
        provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ App Service Plan exists: {plan_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ App Service Plan not found: {plan_name}")
        return False


# ==========================================
# Glue Function App Management
# ==========================================

def create_glue_function_app(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> str:
    """
    Create the L0 Glue Function App.
    
    This Function App hosts all multi-cloud receiver functions:
    - ingestion
    - hot-writer
    - cold-writer
    - archive-writer
    - hot-reader
    - hot-reader-last-entry
    
    Args:
        provider: Azure Provider instance
        config: Project configuration
    
    Returns:
        Function App name
        
    Raises:
        ValueError: If Managed Identity is not found (Setup Layer must run first)
    """
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    storage_name = provider.naming.storage_account()
    location = provider.location
    
    logger.info(f"Creating L0 Glue Function App: {app_name}")
    
    # Get managed identity ID - FAIL-FAST if not found
    from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
    identity_id = get_managed_identity_id(provider)
    
    if not identity_id:
        raise ValueError(
            "Managed Identity not found. Run Setup Layer first (deploy_setup). "
            "The Setup Layer creates the Resource Group, Managed Identity, and Storage Account."
        )
    
    # Create App Service Plan first (required for Function App)
    plan_id = create_consumption_app_service_plan(provider)
    
    # Build site config
    site_config = {
        "pythonVersion": "3.11",
        "linuxFxVersion": "PYTHON|3.11",
        "http20Enabled": True,
        "minTlsVersion": "1.2",
    }
    
    # Build Function App parameters
    params = {
        "location": location,
        "kind": "functionapp,linux",
        "properties": {
            "serverFarmId": plan_id,  # Use actual App Service Plan ID
            "reserved": True,  # Linux
            "siteConfig": site_config,
            "httpsOnly": True,
        },
        "identity": {
            "type": "UserAssigned",
            "userAssignedIdentities": {
                identity_id: {}
            }
        }
    }
    
    try:
        # Create or update the Function App
        poller = provider.clients["web"].web_apps.begin_create_or_update(
            resource_group_name=rg_name,
            name=app_name,
            site_envelope=params
        )
        
        # Wait for completion
        app = poller.result()
        
        # Configure app settings (connection strings, environment variables)
        _configure_function_app_settings(provider, config, storage_name)
        
        # Deploy all L0 function code via zip deploy
        _deploy_glue_functions(provider)
        
        logger.info(f"✓ L0 Glue Function App created: {app_name}")
        return app_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L0 Function App: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L0 Function App: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating L0 Function App: {type(e).__name__}: {e}")
        raise


def _deploy_glue_functions(provider: 'AzureProvider') -> None:
    """
    Deploy all L0 Glue function code via Kudu zip deploy.
    
    Bundles all L0 functions (ingestion, hot-writer, cold-writer,
    archive-writer, hot-reader, hot-reader-last-entry) into a single
    zip and deploys to the Glue Function App.
    """
    import requests
    import util
    import zipfile
    import io
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    logger.info("  Deploying L0 Glue function code...")
    
    # 1. Get publish credentials
    try:
        creds = provider.clients["web"].web_apps.list_publishing_credentials(
            resource_group_name=rg_name,
            name=app_name
        ).result()
        
        publish_username = creds.publishing_user_name
        publish_password = creds.publishing_password
    except Exception as e:
        logger.error(f"Failed to get publish credentials: {e}")
        raise
    
    # 2. Build combined zip with all L0 functions
    azure_functions_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "azure_functions"
    )
    
    # L0 functions to include
    l0_functions = [
        "ingestion",
        "hot-writer",
        "cold-writer",
        "archive-writer",
        "hot-reader",
        "hot-reader-last-entry"
    ]
    
    # Create zip buffer
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add _shared directory
        shared_dir = os.path.join(azure_functions_dir, "_shared")
        if os.path.exists(shared_dir):
            for root, dirs, files in os.walk(shared_dir):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, azure_functions_dir)
                        zf.write(file_path, rel_path)
        
        # Add each function directory
        for func_name in l0_functions:
            func_dir = os.path.join(azure_functions_dir, func_name)
            if os.path.exists(func_dir):
                for root, dirs, files in os.walk(func_dir):
                    for file in files:
                        if file.endswith('.py') or file == 'function.json':
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, azure_functions_dir)
                            zf.write(file_path, rel_path)
        
        # Add host.json and requirements.txt if present
        for extra_file in ['host.json', 'requirements.txt']:
            extra_path = os.path.join(azure_functions_dir, extra_file)
            if os.path.exists(extra_path):
                zf.write(extra_path, extra_file)
    
    zip_content = zip_buffer.getvalue()
    
    # 3. Deploy to Kudu
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy"
    
    try:
        response = requests.post(
            kudu_url,
            data=zip_content,
            auth=(publish_username, publish_password),
            headers={"Content-Type": "application/zip"},
            timeout=300
        )
        
        if response.status_code in (200, 202):
            logger.info(f"  ✓ L0 function code deployed ({len(l0_functions)} functions)")
        else:
            logger.error(f"Kudu deploy failed: {response.status_code} - {response.text}")
            raise HttpResponseError(
                message=f"Kudu zip deploy failed: {response.status_code}",
                response=response
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during Kudu deploy: {e}")
        raise


def _configure_function_app_settings(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    storage_name: str
) -> None:
    """Configure Function App settings and environment variables."""
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    # Get storage connection string
    storage_keys = provider.clients["storage"].storage_accounts.list_keys(
        resource_group_name=rg_name,
        account_name=storage_name
    )
    storage_key = storage_keys.keys[0].value
    storage_conn_str = f"DefaultEndpointsProtocol=https;AccountName={storage_name};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    
    # Build digital twin info
    twin_info = _get_digital_twin_info(config)
    
    # App settings
    settings = {
        "AzureWebJobsStorage": storage_conn_str,
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "FUNCTIONS_EXTENSION_VERSION": "~4",
        "DIGITAL_TWIN_NAME": twin_info["twin_name"],
        "DIGITAL_TWIN_MODE": twin_info["mode"],
        "FUNCTION_APP_BASE_URL": f"https://{app_name}.azurewebsites.net",
    }
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )


def destroy_glue_function_app(provider: 'AzureProvider') -> None:
    """
    Delete the L0 Glue Function App and all its functions.
    
    Args:
        provider: Azure Provider instance
    """
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    logger.info(f"Deleting L0 Glue Function App: {app_name}")
    
    try:
        provider.clients["web"].web_apps.delete(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L0 Glue Function App deleted: {app_name}")
    except ResourceNotFoundError:
        logger.info(f"Function App already deleted: {app_name}")


def check_glue_function_app(provider: 'AzureProvider') -> bool:
    """
    Check if the L0 Glue Function App exists.
    
    Args:
        provider: Azure Provider instance
    
    Returns:
        True if Function App exists, False otherwise
    """
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    try:
        provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L0 Glue Function App exists: {app_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L0 Glue Function App not found: {app_name}")
        return False


# ==========================================
# Ingestion Function (L1 → L2)
# ==========================================

def deploy_ingestion_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    expected_token: str
) -> str:
    """
    Deploy the Ingestion function to the Glue Function App.
    
    This function receives data from remote Connectors (L1) and routes
    to local Processors (L2).
    
    Args:
        provider: Azure Provider instance
        config: Project configuration
        expected_token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Function endpoint URL
    
    Raises:
        ValueError: If expected_token is not set
    """
    if not expected_token:
        raise ValueError("expected_token not set for Ingestion function")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    function_name = provider.naming.ingestion_function()
    
    logger.info(f"Deploying Ingestion function: {function_name}")
    
    # Update app settings with token
    _add_function_app_setting(provider, "INTER_CLOUD_TOKEN", expected_token)
    
    # Get the function endpoint URL
    endpoint_url = f"https://{app_name}.azurewebsites.net/api/{function_name}"
    
    logger.info(f"✓ Ingestion function deployed: {endpoint_url}")
    return endpoint_url


def destroy_ingestion_function(provider: 'AzureProvider') -> None:
    """Remove Ingestion function configuration by removing its token."""
    logger.info("Removing Ingestion function configuration")
    _remove_function_app_setting(provider, "INTER_CLOUD_TOKEN")
    logger.info("✓ Ingestion function configuration removed")


def check_ingestion_function(provider: 'AzureProvider') -> bool:
    """Check if Ingestion function is deployed."""
    # Check if the Function App exists and has the ingestion route
    if not check_glue_function_app(provider):
        return False
    
    function_name = provider.naming.ingestion_function()
    logger.info(f"✓ Ingestion function available: {function_name}")
    return True


# ==========================================
# Hot Writer Function (L2 → L3)
# ==========================================

def deploy_hot_writer_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    expected_token: str
) -> str:
    """
    Deploy the Hot Writer function.
    
    This function receives data from remote Persisters (L2) and writes
    to Cosmos DB (L3 Hot).
    
    Args:
        provider: Azure Provider instance
        config: Project configuration
        expected_token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Function endpoint URL
    
    Raises:
        ValueError: If expected_token is not set
    """
    if not expected_token:
        raise ValueError("expected_token not set for Hot Writer function")
    
    app_name = provider.naming.glue_function_app()
    function_name = provider.naming.hot_writer_function()
    
    logger.info(f"Deploying Hot Writer function: {function_name}")
    
    # Update app settings with token
    _add_function_app_setting(provider, "HOT_WRITER_TOKEN", expected_token)
    
    # Get the function endpoint URL
    endpoint_url = f"https://{app_name}.azurewebsites.net/api/{function_name}"
    
    logger.info(f"✓ Hot Writer function deployed: {endpoint_url}")
    return endpoint_url


def destroy_hot_writer_function(provider: 'AzureProvider') -> None:
    """Remove Hot Writer function configuration by removing its token."""
    logger.info("Removing Hot Writer function configuration")
    _remove_function_app_setting(provider, "HOT_WRITER_TOKEN")
    logger.info("✓ Hot Writer function configuration removed")


def check_hot_writer_function(provider: 'AzureProvider') -> bool:
    """Check if Hot Writer function is deployed."""
    if not check_glue_function_app(provider):
        return False
    
    function_name = provider.naming.hot_writer_function()
    logger.info(f"✓ Hot Writer function available: {function_name}")
    return True


# ==========================================
# Cold Writer Function (L3 Hot → L3 Cold)
# ==========================================

def deploy_cold_writer_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    expected_token: str
) -> str:
    """
    Deploy the Cold Writer function.
    
    This function receives chunked data from remote Hot-to-Cold Movers
    and writes to Blob Storage (Cool tier).
    
    Args:
        provider: Azure Provider instance
        config: Project configuration
        expected_token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Function endpoint URL
    
    Raises:
        ValueError: If expected_token is not set
    """
    if not expected_token:
        raise ValueError("expected_token not set for Cold Writer function")
    
    app_name = provider.naming.glue_function_app()
    function_name = provider.naming.cold_writer_function()
    
    logger.info(f"Deploying Cold Writer function: {function_name}")
    
    # Update app settings with token
    _add_function_app_setting(provider, "COLD_WRITER_TOKEN", expected_token)
    
    # Get the function endpoint URL
    endpoint_url = f"https://{app_name}.azurewebsites.net/api/{function_name}"
    
    logger.info(f"✓ Cold Writer function deployed: {endpoint_url}")
    return endpoint_url


def destroy_cold_writer_function(provider: 'AzureProvider') -> None:
    """Remove Cold Writer function configuration by removing its token."""
    logger.info("Removing Cold Writer function configuration")
    _remove_function_app_setting(provider, "COLD_WRITER_TOKEN")
    logger.info("✓ Cold Writer function configuration removed")


def check_cold_writer_function(provider: 'AzureProvider') -> bool:
    """Check if Cold Writer function is deployed."""
    if not check_glue_function_app(provider):
        return False
    
    function_name = provider.naming.cold_writer_function()
    logger.info(f"✓ Cold Writer function available: {function_name}")
    return True


# ==========================================
# Archive Writer Function (L3 Cold → L3 Archive)
# ==========================================

def deploy_archive_writer_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    expected_token: str
) -> str:
    """
    Deploy the Archive Writer function.
    
    This function receives data from remote Cold-to-Archive Movers
    and writes to Blob Storage (Archive tier).
    
    Args:
        provider: Azure Provider instance
        config: Project configuration
        expected_token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Function endpoint URL
    
    Raises:
        ValueError: If expected_token is not set
    """
    if not expected_token:
        raise ValueError("expected_token not set for Archive Writer function")
    
    app_name = provider.naming.glue_function_app()
    function_name = provider.naming.archive_writer_function()
    
    logger.info(f"Deploying Archive Writer function: {function_name}")
    
    # Update app settings with token
    _add_function_app_setting(provider, "ARCHIVE_WRITER_TOKEN", expected_token)
    
    # Get the function endpoint URL
    endpoint_url = f"https://{app_name}.azurewebsites.net/api/{function_name}"
    
    logger.info(f"✓ Archive Writer function deployed: {endpoint_url}")
    return endpoint_url


def destroy_archive_writer_function(provider: 'AzureProvider') -> None:
    """Remove Archive Writer function configuration by removing its token."""
    logger.info("Removing Archive Writer function configuration")
    _remove_function_app_setting(provider, "ARCHIVE_WRITER_TOKEN")
    logger.info("✓ Archive Writer function configuration removed")


def check_archive_writer_function(provider: 'AzureProvider') -> bool:
    """Check if Archive Writer function is deployed."""
    if not check_glue_function_app(provider):
        return False
    
    function_name = provider.naming.archive_writer_function()
    logger.info(f"✓ Archive Writer function available: {function_name}")
    return True


# ==========================================
# Hot Reader Endpoints (L3 → L4)
# ==========================================

def create_hot_reader_endpoint(
    provider: 'AzureProvider',
    token: str
) -> str:
    """
    Create Hot Reader endpoint for remote L4 access.
    
    This enables TwinMaker (L4) on a different cloud to query
    Hot data via HTTP.
    
    Args:
        provider: Azure Provider instance
        token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Hot Reader endpoint URL
    """
    app_name = provider.naming.glue_function_app()
    function_name = provider.naming.hot_reader_function()
    
    logger.info(f"Creating Hot Reader endpoint: {function_name}")
    
    # Update app settings with token
    _add_function_app_setting(provider, "HOT_READER_TOKEN", token)
    
    endpoint_url = f"https://{app_name}.azurewebsites.net/api/{function_name}"
    
    logger.info(f"✓ Hot Reader endpoint created: {endpoint_url}")
    return endpoint_url


def create_hot_reader_last_entry_endpoint(
    provider: 'AzureProvider',
    token: str
) -> str:
    """
    Create Hot Reader Last Entry endpoint for remote L4 access.
    
    Args:
        provider: Azure Provider instance
        token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Hot Reader Last Entry endpoint URL
    """
    app_name = provider.naming.glue_function_app()
    function_name = provider.naming.hot_reader_last_entry_function()
    
    logger.info(f"Creating Hot Reader Last Entry endpoint: {function_name}")
    
    # Token is shared with hot reader
    endpoint_url = f"https://{app_name}.azurewebsites.net/api/{function_name}"
    
    logger.info(f"✓ Hot Reader Last Entry endpoint created: {endpoint_url}")
    return endpoint_url


def destroy_hot_reader_endpoint(provider: 'AzureProvider') -> None:
    """Remove Hot Reader endpoint configuration by removing its token."""
    logger.info("Removing Hot Reader endpoint configuration")
    _remove_function_app_setting(provider, "HOT_READER_TOKEN")
    logger.info("✓ Hot Reader endpoint configuration removed")


def destroy_hot_reader_last_entry_endpoint(provider: 'AzureProvider') -> None:
    """Remove Hot Reader Last Entry endpoint configuration.
    
    Note: Token is shared with Hot Reader, so no additional cleanup needed.
    """
    logger.info("Removing Hot Reader Last Entry endpoint configuration")
    # Token is shared with hot reader, no additional cleanup
    logger.info("✓ Hot Reader Last Entry endpoint configuration removed")


def check_hot_reader_endpoint(provider: 'AzureProvider') -> bool:
    """Check if Hot Reader endpoint exists."""
    if not check_glue_function_app(provider):
        return False
    
    function_name = provider.naming.hot_reader_function()
    logger.info(f"✓ Hot Reader endpoint available: {function_name}")
    return True


def check_hot_reader_last_entry_endpoint(provider: 'AzureProvider') -> bool:
    """Check if Hot Reader Last Entry endpoint exists."""
    if not check_glue_function_app(provider):
        return False
    
    function_name = provider.naming.hot_reader_last_entry_function()
    logger.info(f"✓ Hot Reader Last Entry endpoint available: {function_name}")
    return True


# ==========================================
# Helper: App Settings Management
# ==========================================

def _add_function_app_setting(
    provider: 'AzureProvider',
    key: str,
    value: str
) -> None:
    """
    Add or update a single app setting on the Function App.
    
    Args:
        provider: Azure Provider instance
        key: Setting key
        value: Setting value
    """
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    # Get current settings
    current = provider.clients["web"].web_apps.list_application_settings(
        resource_group_name=rg_name,
        name=app_name
    )
    
    # Update with new setting
    settings = dict(current.properties) if current.properties else {}
    settings[key] = value
    
    # Apply updated settings
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )


def _remove_function_app_setting(
    provider: 'AzureProvider',
    key: str
) -> None:
    """
    Remove a single app setting from the Function App.
    
    Used by destroy_* functions to clean up tokens.
    
    Args:
        provider: Azure Provider instance
        key: Setting key to remove
    """
    from azure.core.exceptions import ResourceNotFoundError
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    try:
        # Get current settings
        current = provider.clients["web"].web_apps.list_application_settings(
            resource_group_name=rg_name,
            name=app_name
        )
        
        # Remove the setting if it exists
        settings = dict(current.properties) if current.properties else {}
        if key in settings:
            del settings[key]
            
            # Apply updated settings
            provider.clients["web"].web_apps.update_application_settings(
                resource_group_name=rg_name,
                name=app_name,
                app_settings={"properties": settings}
            )
            logger.info(f"Removed app setting: {key}")
        else:
            logger.info(f"App setting not found (already removed): {key}")
    except ResourceNotFoundError:
        logger.info(f"Function App not found - settings cleanup skipped")
