"""
Azure Layer 2 (Compute/Data Processing) Component Implementations.

This module contains ALL L2 component implementations for Azure that are
deployed by the L2 adapter.

Components Managed:
    - L2 App Service Plan: Consumption (Y1 Dynamic) plan for L2 Function App
    - L2 Function App: Hosts Persister, Processors, Event Checker, Event Feedback
    - Persister Function: Writes processed data to L3 storage (via Kudu zip deploy)
    - Processor Functions: Per-device data processing (via Kudu zip deploy)
    - Event Checker Function: Evaluates data against rules (optional)
    - Event Feedback Function: Sends feedback to IoT devices (optional)
    - Logic Apps Workflow: Notification workflow for triggered events (optional)
    - Event Action Functions: Custom action functions (dynamic, per config)

Architecture:
    L1 (Dispatcher) → Processor Functions → Persister Function → L3 (Storage)
                                                  │
                                                  ├── Event Checker (optional)
                                                  │       │
                                                  │       ├── Logic Apps Workflow
                                                  │       ├── Event Action Functions
                                                  │       └── Event Feedback
                                                  │
                                                  └── Remote Hot Writer (multi-cloud)

Architecture Note:
    Unlike AWS where each Lambda is separate, Azure groups multiple functions
    into a single Function App. All L2 functions are bundled in {twin}-l2-functions.
    This provides cost efficiency and simplified deployment.

Authentication:
    - Same-cloud: Function keys for internal calls
    - Cross-cloud: X-Inter-Cloud-Token header for L2→L3 boundary

Critical Requirements:
    - Every component has create/destroy/check triplet
    - No silent fallbacks - fail-fast validation
    - Comprehensive exception handling (ClientAuthenticationError, HttpResponseError, etc.)
    - All function code deployed via Kudu zip deploy (not just infrastructure)
"""

from typing import TYPE_CHECKING, Optional
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
        "config": {
            "digital_twin_name": config.digital_twin_name,
            "hot_storage_size_in_days": config.hot_storage_size_in_days,
            "cold_storage_size_in_days": config.cold_storage_size_in_days,
            "mode": config.mode,
        },
        "config_iot_devices": config.iot_devices,
        "config_events": config.events,
        "config_providers": config.providers
    }


def _get_storage_connection_string(provider: 'AzureProvider') -> str:
    """Get the storage account connection string for Function App."""
    rg_name = provider.naming.resource_group()
    storage_name = provider.naming.storage_account()
    
    storage_keys = provider.clients["storage"].storage_accounts.list_keys(
        resource_group_name=rg_name,
        account_name=storage_name
    )
    storage_key = storage_keys.keys[0].value
    
    return (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={storage_name};"
        f"AccountKey={storage_key};"
        f"EndpointSuffix=core.windows.net"
    )


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
        project_path: Base project path for resolving relative paths
        
    Raises:
        HttpResponseError: If Kudu deployment fails
    """
    import src.util as util
    
    rg_name = provider.naming.resource_group()
    
    logger.info(f"  Getting publish credentials for {app_name}...")
    
    try:
        creds = provider.clients["web"].web_apps.list_publishing_credentials(
            resource_group_name=rg_name,
            name=app_name
        ).result()
        
        # Compile function code into zip
        logger.info(f"  Compiling function from {os.path.basename(function_dir)}...")
        zip_content = util.compile_azure_function(function_dir, project_path)
        
        # Deploy via Kudu
        kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy"
        logger.info(f"  Deploying via Kudu zip deploy to {kudu_url}...")
        
        response = requests.post(
            kudu_url,
            data=zip_content,
            auth=(creds.publishing_user_name, creds.publishing_password),
            headers={"Content-Type": "application/zip"},
            timeout=300
        )
        
        if response.status_code not in (200, 202):
            raise HttpResponseError(
                f"Kudu zip deploy failed: {response.status_code} - {response.text}"
            )
        
        logger.info(f"  ✓ Function code deployed successfully")
        
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED getting publish credentials: {e.message}")
        raise
    except requests.RequestException as e:
        logger.error(f"HTTP error during Kudu deployment: {e}")
        raise HttpResponseError(f"Kudu deployment failed: {e}")


# ==========================================
# 1. L2 App Service Plan
# ==========================================

def create_l2_app_service_plan(provider: 'AzureProvider') -> str:
    """
    Create the App Service Plan for L2 Function App (Consumption Y1).
    
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
    plan_name = provider.naming.l2_app_service_plan()
    location = provider.location
    
    logger.info(f"Creating L2 App Service Plan: {plan_name}")
    
    try:
        poller = provider.clients["web"].app_service_plans.begin_create_or_update(
            resource_group_name=rg_name,
            name=plan_name,
            app_service_plan={
                "location": location,
                "sku": {
                    "name": "Y1",
                    "tier": "Dynamic"
                },
                "kind": "functionapp",
                "properties": {
                    "reserved": True  # Linux
                }
            }
        )
        plan = poller.result()
        logger.info(f"✓ L2 App Service Plan created: {plan_name}")
        return plan.id
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L2 App Service Plan: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L2 App Service Plan: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating L2 App Service Plan: {type(e).__name__}: {e}")
        raise


def destroy_l2_app_service_plan(provider: 'AzureProvider') -> None:
    """
    Delete the L2 App Service Plan.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l2_app_service_plan()
    
    logger.info(f"Deleting L2 App Service Plan: {plan_name}")
    
    try:
        provider.clients["web"].app_service_plans.delete(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L2 App Service Plan deleted: {plan_name}")
    except ResourceNotFoundError:
        logger.info(f"L2 App Service Plan already deleted: {plan_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting L2 App Service Plan: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting L2 App Service Plan: {type(e).__name__}: {e}")
        raise


def check_l2_app_service_plan(provider: 'AzureProvider') -> bool:
    """
    Check if the L2 App Service Plan exists.
    
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
    plan_name = provider.naming.l2_app_service_plan()
    
    try:
        provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L2 App Service Plan exists: {plan_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L2 App Service Plan not found: {plan_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking L2 App Service Plan: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking L2 App Service Plan: {type(e).__name__}: {e}")
        raise


# ==========================================
# 2. L2 Function App
# ==========================================

def create_l2_function_app(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> str:
    """
    Create the L2 Function App for hosting data processing functions.
    
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
    app_name = provider.naming.l2_function_app()
    storage_name = provider.naming.storage_account()
    location = provider.location
    
    logger.info(f"Creating L2 Function App: {app_name}")
    
    # Get managed identity ID
    from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
    identity_id = get_managed_identity_id(provider)
    
    if not identity_id:
        raise ValueError(
            "Managed Identity not found. Run Setup Layer first (deploy_setup). "
            "The Setup Layer creates the Resource Group, Managed Identity, and Storage Account."
        )
    
    # Get App Service Plan ID
    plan_name = provider.naming.l2_app_service_plan()
    try:
        plan = provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        plan_id = plan.id
    except ResourceNotFoundError:
        raise ValueError(f"L2 App Service Plan not found: {plan_name}. Create it first.")
    
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
            "serverFarmId": plan_id,
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
        poller = provider.clients["web"].web_apps.begin_create_or_update(
            resource_group_name=rg_name,
            name=app_name,
            site_envelope=params
        )
        app = poller.result()
        
        # Configure app settings
        _configure_l2_function_app_settings(provider, config, storage_name)
        
        logger.info(f"✓ L2 Function App created: {app_name}")
        return app_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L2 Function App: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L2 Function App: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating L2 Function App: {type(e).__name__}: {e}")
        raise


def _configure_l2_function_app_settings(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    storage_name: str
) -> None:
    """
    Configure L2 Function App settings and environment variables.
    
    Sets:
        - AzureWebJobsStorage: Storage connection string
        - FUNCTIONS_WORKER_RUNTIME: python
        - FUNCTIONS_EXTENSION_VERSION: ~4
        - DIGITAL_TWIN_INFO: Twin configuration JSON
        - PERSISTER_FUNCTION_URL: URL for Persister invocation
        - USE_EVENT_CHECKING: Whether event checking is enabled
        - EVENT_CHECKER_FUNCTION_URL: URL for Event Checker (if enabled)
    """
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    # Get storage connection string
    storage_conn_str = _get_storage_connection_string(provider)
    
    # Build digital twin info
    digital_twin_info = _get_digital_twin_info(config)
    
    # App settings
    settings = {
        "AzureWebJobsStorage": storage_conn_str,
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "FUNCTIONS_EXTENSION_VERSION": "~4",
        "DIGITAL_TWIN_INFO": json.dumps(digital_twin_info),
        "FUNCTION_APP_BASE_URL": f"https://{app_name}.azurewebsites.net",
        "USE_EVENT_CHECKING": str(config.is_optimization_enabled("useEventChecking")).lower(),
    }
    
    # Multi-cloud: Add remote writer URL if L3 is on different cloud
    l2_provider = config.providers.get("layer_2_provider")
    l3_provider = config.providers.get("layer_3_hot_provider")
    
    if l2_provider and l3_provider and l3_provider != l2_provider:
        inter_cloud = getattr(config, 'inter_cloud', None) or {}
        connections = inter_cloud.get("connections", {})
        conn_id = f"{l2_provider}_l2_to_{l3_provider}_l3"
        conn = connections.get(conn_id, {})
        url = conn.get("url", "")
        token = conn.get("token", "")
        
        if url and token:
            settings["REMOTE_WRITER_URL"] = url
            settings["INTER_CLOUD_TOKEN"] = token
            logger.info(f"  Multi-cloud mode: Persister will POST to {l3_provider} Writer")
        else:
            logger.warning(f"  Multi-cloud config incomplete for {conn_id}")
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )
    
    logger.info(f"  ✓ L2 Function App settings configured")


def destroy_l2_function_app(provider: 'AzureProvider') -> None:
    """
    Delete the L2 Function App.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    logger.info(f"Deleting L2 Function App: {app_name}")
    
    try:
        provider.clients["web"].web_apps.delete(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L2 Function App deleted: {app_name}")
    except ResourceNotFoundError:
        logger.info(f"L2 Function App already deleted: {app_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting L2 Function App: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting L2 Function App: {type(e).__name__}: {e}")
        raise


def check_l2_function_app(provider: 'AzureProvider') -> bool:
    """
    Check if the L2 Function App exists.
    
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
    app_name = provider.naming.l2_function_app()
    
    try:
        provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L2 Function App exists: {app_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L2 Function App not found: {app_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking L2 Function App: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking L2 Function App: {type(e).__name__}: {e}")
        raise


# ==========================================
# 3. Persister Function
# ==========================================

def deploy_persister_function(
    provider: 'AzureProvider',
    project_path: str
) -> None:
    """
    Deploy the Persister function to the L2 Function App.
    
    The Persister writes processed data to L3 storage (Cosmos DB for Azure,
    or remote Hot Writer for multi-cloud).
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        project_path: Path to project root for resolving function code
        
    Raises:
        ValueError: If provider or project_path is None
        HttpResponseError: If deployment fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    app_name = provider.naming.l2_function_app()
    
    logger.info(f"Deploying Persister function to {app_name}")
    
    # Path to persister function in azure_functions directory
    import src.constants as constants
    persister_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "azure_functions",
        "persister"
    )
    
    if not os.path.exists(persister_dir):
        raise ValueError(f"Persister function not found at {persister_dir}")
    
    _deploy_function_code_via_kudu(provider, app_name, persister_dir, project_path)
    
    logger.info(f"✓ Persister function deployed")


def destroy_persister_function(provider: 'AzureProvider') -> None:
    """
    Destroy the Persister function.
    
    Note: In Azure, individual functions are not deleted separately.
    They are removed when the Function App is deleted or when code is redeployed
    without that function.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info("Persister function will be removed with L2 Function App")


def check_persister_function(provider: 'AzureProvider') -> bool:
    """
    Check if the Persister function exists in the L2 Function App.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if function exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        functions = list(provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        ))
        
        for func in functions:
            if "persister" in func.name.lower():
                logger.info(f"✓ Persister function exists")
                return True
        
        logger.info(f"✗ Persister function not found")
        return False
    except ResourceNotFoundError:
        logger.info(f"✗ L2 Function App not found")
        return False
    except AzureError as e:
        logger.error(f"Error checking Persister function: {e}")
        return False


# ==========================================
# 4. Processor Functions (per device)
# ==========================================

def deploy_processor_function(
    iot_device: dict,
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Deploy a Processor function for a specific IoT device.
    
    The Processor handles data transformation for a specific device type
    before passing to the Persister.
    
    Args:
        iot_device: Device configuration dictionary with 'id' key
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to project root
        
    Raises:
        ValueError: If required parameters are None
        HttpResponseError: If deployment fails
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    device_id = iot_device.get("id", iot_device.get("iotDeviceId", "unknown"))
    app_name = provider.naming.l2_function_app()
    processor_name = provider.naming.processor_function(device_id)
    
    logger.info(f"Deploying Processor function: {processor_name}")
    
    # Check for custom processor or use default
    import src.constants as CONSTANTS
    custom_processor_path = os.path.join(
        project_path, 
        CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME if hasattr(CONSTANTS, 'LAMBDA_FUNCTIONS_DIR_NAME') else "lambda_functions",
        "processors",
        device_id
    )
    
    if os.path.exists(custom_processor_path):
        processor_dir = custom_processor_path
        logger.info(f"  Using custom processor for {device_id}")
    else:
        # Use default processor from azure_functions
        processor_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "azure_functions",
            "default-processor"
        )
        logger.info(f"  Using default processor for {device_id}")
    
    if not os.path.exists(processor_dir):
        raise ValueError(f"Processor function not found at {processor_dir}")
    
    # Update app settings with processor-specific config
    rg_name = provider.naming.resource_group()
    
    # Get current settings and add processor config
    current_settings = provider.clients["web"].web_apps.list_application_settings(
        resource_group_name=rg_name,
        name=app_name
    )
    
    settings = dict(current_settings.properties) if current_settings.properties else {}
    settings[f"PROCESSOR_{device_id.upper().replace('-', '_')}_ENABLED"] = "true"
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )
    
    _deploy_function_code_via_kudu(provider, app_name, processor_dir, project_path)
    
    logger.info(f"✓ Processor function deployed: {processor_name}")


def destroy_processor_function(
    iot_device: dict,
    provider: 'AzureProvider'
) -> None:
    """
    Destroy a Processor function for a specific IoT device.
    
    Note: In Azure, individual functions are removed with the Function App
    or by redeploying without that function.
    
    Args:
        iot_device: Device configuration dictionary with 'id' key
        provider: Initialized AzureProvider with clients and naming
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    
    device_id = iot_device.get("id", iot_device.get("iotDeviceId", "unknown"))
    processor_name = provider.naming.processor_function(device_id)
    
    logger.info(f"Processor function {processor_name} will be removed with L2 Function App")


def check_processor_function(
    iot_device: dict,
    provider: 'AzureProvider'
) -> bool:
    """
    Check if a Processor function exists for a specific IoT device.
    
    Args:
        iot_device: Device configuration dictionary with 'id' key
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if function exists, False otherwise
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    
    device_id = iot_device.get("id", iot_device.get("iotDeviceId", "unknown"))
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        functions = list(provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        ))
        
        for func in functions:
            if device_id in func.name.lower() and "processor" in func.name.lower():
                logger.info(f"✓ Processor function exists for {device_id}")
                return True
        
        logger.info(f"✗ Processor function not found for {device_id}")
        return False
    except ResourceNotFoundError:
        logger.info(f"✗ L2 Function App not found")
        return False
    except AzureError as e:
        logger.error(f"Error checking Processor function: {e}")
        return False


# ==========================================
# 5. Event Checker Function (Optional)
# ==========================================

def deploy_event_checker_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Deploy the Event Checker function to the L2 Function App.
    
    The Event Checker evaluates data against configured rules and triggers
    Logic Apps workflows or feedback actions.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to project root
        
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
    
    app_name = provider.naming.l2_function_app()
    
    logger.info(f"Deploying Event Checker function to {app_name}")
    
    # Path to event-checker function
    event_checker_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "azure_functions",
        "event-checker"
    )
    
    if not os.path.exists(event_checker_dir):
        raise ValueError(f"Event Checker function not found at {event_checker_dir}")
    
    # Update app settings for event checker
    rg_name = provider.naming.resource_group()
    
    current_settings = provider.clients["web"].web_apps.list_application_settings(
        resource_group_name=rg_name,
        name=app_name
    )
    
    settings = dict(current_settings.properties) if current_settings.properties else {}
    settings["USE_LOGIC_APPS"] = str(config.is_optimization_enabled("triggerNotificationWorkflow")).lower()
    settings["USE_FEEDBACK"] = str(config.is_optimization_enabled("returnFeedbackToDevice")).lower()
    
    # Add Logic App URL if workflow is enabled
    if config.is_optimization_enabled("triggerNotificationWorkflow"):
        # LOGIC_APP_TRIGGER_URL is set by _update_logic_app_url() after Logic App creation
        # Initial empty value signals pending configuration
        settings["LOGIC_APP_TRIGGER_URL"] = ""
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )
    
    _deploy_function_code_via_kudu(provider, app_name, event_checker_dir, project_path)
    
    logger.info(f"✓ Event Checker function deployed")


def destroy_event_checker_function(provider: 'AzureProvider') -> None:
    """
    Destroy the Event Checker function.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info("Event Checker function will be removed with L2 Function App")


def check_event_checker_function(provider: 'AzureProvider') -> bool:
    """
    Check if the Event Checker function exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if function exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        functions = list(provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        ))
        
        for func in functions:
            if "event-checker" in func.name.lower() or "eventchecker" in func.name.lower():
                logger.info(f"✓ Event Checker function exists")
                return True
        
        logger.info(f"✗ Event Checker function not found")
        return False
    except ResourceNotFoundError:
        logger.info(f"✗ L2 Function App not found")
        return False
    except AzureError as e:
        logger.error(f"Error checking Event Checker function: {e}")
        return False


# ==========================================
# 6. Event Feedback Function (Optional)
# ==========================================

def deploy_event_feedback_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Deploy the Event Feedback function to the L2 Function App.
    
    The Event Feedback function sends feedback messages to IoT devices
    when events are triggered.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to project root
        
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
    
    app_name = provider.naming.l2_function_app()
    
    logger.info(f"Deploying Event Feedback function to {app_name}")
    
    # Check for user-defined event-feedback in lambda_functions
    import src.constants as CONSTANTS
    user_feedback_dir = os.path.join(
        project_path,
        CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME if hasattr(CONSTANTS, 'LAMBDA_FUNCTIONS_DIR_NAME') else "lambda_functions",
        "event-feedback"
    )
    
    if os.path.exists(user_feedback_dir):
        feedback_dir = user_feedback_dir
        logger.info("  Using user-defined Event Feedback function")
    else:
        # No default event-feedback - this is user-defined
        logger.warning("  No event-feedback function found. Users must provide their own.")
        return
    
    _deploy_function_code_via_kudu(provider, app_name, feedback_dir, project_path)
    
    logger.info(f"✓ Event Feedback function deployed")


def destroy_event_feedback_function(provider: 'AzureProvider') -> None:
    """
    Destroy the Event Feedback function.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info("Event Feedback function will be removed with L2 Function App")


def check_event_feedback_function(provider: 'AzureProvider') -> bool:
    """
    Check if the Event Feedback function exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if function exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        functions = list(provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        ))
        
        for func in functions:
            if "feedback" in func.name.lower():
                logger.info(f"✓ Event Feedback function exists")
                return True
        
        logger.info(f"✗ Event Feedback function not found")
        return False
    except ResourceNotFoundError:
        logger.info(f"✗ L2 Function App not found")
        return False
    except AzureError as e:
        logger.error(f"Error checking Event Feedback function: {e}")
        return False


# ==========================================
# 7. Logic Apps Workflow (Optional)
# ==========================================

def create_logic_app_workflow(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> str:
    """
    Create an Azure Logic Apps Workflow for notification processing.
    
    This is the Azure equivalent of AWS Step Functions for the
    `triggerNotificationWorkflow` feature.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        
    Returns:
        The Logic App HTTP trigger URL
        
    Raises:
        ValueError: If required parameters are None
        HttpResponseError: If creation fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    rg_name = provider.naming.resource_group()
    workflow_name = provider.naming.logic_app_workflow()
    location = provider.location
    
    logger.info(f"Creating Logic Apps Workflow: {workflow_name}")
    
    # Basic workflow definition with HTTP trigger
    workflow_definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "triggers": {
            "manual": {
                "type": "Request",
                "kind": "Http",
                "inputs": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "event": {
                                "type": "object"
                            }
                        }
                    }
                }
            }
        },
        "actions": {
            "Response": {
                "type": "Response",
                "kind": "Http",
                "inputs": {
                    "statusCode": 200,
                    "body": {
                        "status": "processed"
                    }
                },
                "runAfter": {}
            }
        },
        "outputs": {}
    }
    
    try:
        # Create Logic App using azure-mgmt-logic
        logic_client = provider.clients.get("logic")
        
        if logic_client is None:
            # Logic client might not be initialized - create it
            from azure.mgmt.logic import LogicManagementClient
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            logic_client = LogicManagementClient(credential, provider.subscription_id)
            provider.clients["logic"] = logic_client
        
        workflow = logic_client.workflows.create_or_update(
            resource_group_name=rg_name,
            workflow_name=workflow_name,
            workflow={
                "location": location,
                "definition": workflow_definition,
                "state": "Enabled"
            }
        )
        
        # Get the HTTP trigger URL
        triggers = logic_client.workflow_triggers.list(
            resource_group_name=rg_name,
            workflow_name=workflow_name
        )
        
        trigger_url = ""
        for trigger in triggers:
            if trigger.name == "manual":
                callback = logic_client.workflow_triggers.list_callback_url(
                    resource_group_name=rg_name,
                    workflow_name=workflow_name,
                    trigger_name="manual"
                )
                trigger_url = callback.value
                break
        
        logger.info(f"✓ Logic Apps Workflow created: {workflow_name}")
        
        # Update Event Checker with the actual Logic App URL
        if trigger_url:
            _update_logic_app_url(provider, trigger_url)
        
        return trigger_url
        
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating Logic Apps Workflow: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create Logic Apps Workflow: {e.status_code} - {e.message}")
        raise
    except Exception as e:
        logger.error(f"Error creating Logic Apps Workflow: {type(e).__name__}: {e}")
        raise


def _update_logic_app_url(provider: 'AzureProvider', trigger_url: str) -> None:
    """Update the L2 Function App with the Logic App trigger URL."""
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        current_settings = provider.clients["web"].web_apps.list_application_settings(
            resource_group_name=rg_name,
            name=app_name
        )
        
        settings = dict(current_settings.properties) if current_settings.properties else {}
        settings["LOGIC_APP_TRIGGER_URL"] = trigger_url
        
        provider.clients["web"].web_apps.update_application_settings(
            resource_group_name=rg_name,
            name=app_name,
            app_settings={"properties": settings}
        )
        
        logger.info(f"  ✓ Updated LOGIC_APP_TRIGGER_URL in L2 Function App")
    except Exception as e:
        logger.warning(f"  Failed to update Logic App URL: {e}")


def destroy_logic_app_workflow(provider: 'AzureProvider') -> None:
    """
    Delete the Logic Apps Workflow.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workflow_name = provider.naming.logic_app_workflow()
    
    logger.info(f"Deleting Logic Apps Workflow: {workflow_name}")
    
    try:
        logic_client = provider.clients.get("logic")
        
        if logic_client is None:
            from azure.mgmt.logic import LogicManagementClient
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            logic_client = LogicManagementClient(credential, provider.subscription_id)
        
        logic_client.workflows.delete(
            resource_group_name=rg_name,
            workflow_name=workflow_name
        )
        logger.info(f"✓ Logic Apps Workflow deleted: {workflow_name}")
    except ResourceNotFoundError:
        logger.info(f"Logic Apps Workflow already deleted: {workflow_name}")
    except Exception as e:
        logger.error(f"Error deleting Logic Apps Workflow: {e}")


def check_logic_app_workflow(provider: 'AzureProvider') -> bool:
    """
    Check if the Logic Apps Workflow exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if workflow exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    workflow_name = provider.naming.logic_app_workflow()
    
    try:
        logic_client = provider.clients.get("logic")
        
        if logic_client is None:
            from azure.mgmt.logic import LogicManagementClient
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            logic_client = LogicManagementClient(credential, provider.subscription_id)
        
        logic_client.workflows.get(
            resource_group_name=rg_name,
            workflow_name=workflow_name
        )
        logger.info(f"✓ Logic Apps Workflow exists: {workflow_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Logic Apps Workflow not found: {workflow_name}")
        return False
    except Exception as e:
        logger.error(f"Error checking Logic Apps Workflow: {e}")
        return False


# ==========================================
# 8. Event Action Functions (Dynamic)
# ==========================================

def deploy_event_action_functions(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Deploy Event Action functions defined in the events config.
    
    This is the Azure equivalent of AWS Lambda Actions.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to project root
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if not project_path:
        raise ValueError("project_path is required")
    
    if not config.events:
        logger.info("No events configured - skipping Event Action deployment")
        return
    
    import src.constants as CONSTANTS
    app_name = provider.naming.l2_function_app()
    
    for event in config.events:
        action = event.get("action", {})
        if action.get("type") in ("lambda", "function") and action.get("autoDeploy", True):
            function_name = action.get("functionName")
            
            if not function_name:
                logger.warning(f"Event action missing functionName: {event}")
                continue
            
            logger.info(f"Deploying Event Action function: {function_name}")
            
            # Look for function in lambda_functions/event_actions or event-actions
            action_dir = os.path.join(
                project_path,
                CONSTANTS.EVENT_ACTIONS_DIR_NAME if hasattr(CONSTANTS, 'EVENT_ACTIONS_DIR_NAME') else "lambda_functions/event_actions",
                function_name
            )
            
            if not os.path.exists(action_dir):
                # Try alternate path
                action_dir = os.path.join(project_path, "lambda_functions", "event-actions", function_name)
            
            if not os.path.exists(action_dir):
                logger.warning(f"Event Action function not found: {function_name} at {action_dir}")
                continue
            
            _deploy_function_code_via_kudu(provider, app_name, action_dir, project_path)
            
            logger.info(f"✓ Event Action function deployed: {function_name}")


def destroy_event_action_functions(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> None:
    """
    Destroy Event Action functions.
    
    Note: Individual functions are removed with the Function App.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
    """
    if provider is None:
        raise ValueError("provider is required")
    
    if config and config.events:
        for event in config.events:
            action = event.get("action", {})
            if action.get("type") in ("lambda", "function") and action.get("autoDeploy", True):
                function_name = action.get("functionName")
                if function_name:
                    logger.info(f"Event Action function {function_name} will be removed with L2 Function App")


def check_event_action_functions(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> dict:
    """
    Check which Event Action functions exist.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        
    Returns:
        Dictionary of function_name -> exists (bool)
    """
    if provider is None:
        raise ValueError("provider is required")
    
    results = {}
    
    if not config or not config.events:
        return results
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l2_function_app()
    
    try:
        functions = list(provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        ))
        function_names = [f.name.lower() for f in functions]
        
        for event in config.events:
            action = event.get("action", {})
            if action.get("type") in ("lambda", "function") and action.get("autoDeploy", True):
                fn_name = action.get("functionName", "")
                exists = any(fn_name.lower() in name for name in function_names)
                results[fn_name] = exists
                
                if exists:
                    logger.info(f"✓ Event Action function exists: {fn_name}")
                else:
                    logger.info(f"✗ Event Action function not found: {fn_name}")
                    
    except ResourceNotFoundError:
        logger.info(f"✗ L2 Function App not found")
    except AzureError as e:
        logger.error(f"Error checking Event Action functions: {e}")
    
    return results


# ==========================================
# 9. Info / Status Check
# ==========================================

def info_l2(context, provider: 'AzureProvider') -> dict:
    """
    Check status of all L2 components.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider
        
    Returns:
        Dictionary with component status
    """
    config = context.config
    
    logger.info(f"[L2] Checking Azure L2 status for {config.digital_twin_name}")
    
    status = {
        "app_service_plan": check_l2_app_service_plan(provider),
        "function_app": check_l2_function_app(provider),
        "persister_function": check_persister_function(provider),
        "processor_functions": {},
        "event_checker_function": False,
        "event_feedback_function": False,
        "logic_app_workflow": False,
        "event_action_functions": {},
    }
    
    # Check processor functions
    if config.iot_devices:
        for device in config.iot_devices:
            device_id = device.get("id", device.get("iotDeviceId", "unknown"))
            status["processor_functions"][device_id] = check_processor_function(device, provider)
    
    # Check optional components
    if config.is_optimization_enabled("useEventChecking"):
        status["event_checker_function"] = check_event_checker_function(provider)
        
        if config.is_optimization_enabled("triggerNotificationWorkflow"):
            status["logic_app_workflow"] = check_logic_app_workflow(provider)
        
        if config.is_optimization_enabled("returnFeedbackToDevice"):
            status["event_feedback_function"] = check_event_feedback_function(provider)
    
    # Check event action functions
    if config.events:
        status["event_action_functions"] = check_event_action_functions(provider, config)
    
    return status
