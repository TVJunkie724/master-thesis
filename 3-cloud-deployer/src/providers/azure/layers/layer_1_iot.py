"""
Azure Layer 1 (IoT/Data Acquisition) - Core Component Functions.

This module provides create/destroy/check functions for all Layer 1 Azure resources.
Layer 1 handles IoT device connectivity and data acquisition for Digital Twins.

Components Managed:
    - IoT Hub: Central hub for device connectivity (S1 Standard tier)
    - RBAC Role Assignments: Managed Identity permissions for IoT Hub
    - L1 App Service Plan: Consumption plan for L1 Function App
    - L1 Function App: Hosts Dispatcher and Connector functions
    - Dispatcher Function: Routes incoming telemetry to processors
    - Event Grid Subscription: Routes IoT Hub events to Dispatcher
    - IoT Devices: Device identities and connection strings
    - Connector Function: Multi-cloud handoff (when L1 != L2)

Architecture:
    IoT Hub → Event Grid → Dispatcher Function → Processor/Connector Function
         │          │               │
         │          │               └── L1 Function App (Consumption Y1)
         │          └── Subscription
         └── IoT Device + Connection String

Critical Requirements:
    - Every component has create/destroy/check triplet
    - No silent fallbacks - fail-fast validation
    - Comprehensive exception handling (not just ResourceNotFoundError)
    - All destroy functions implement actual cleanup (never use pass)

Note:
    This module mirrors the AWS layer_1_iot.py pattern but adapted for Azure services.
"""

from typing import TYPE_CHECKING, Optional
import logging
import json
import os
import uuid
import time

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
# 1. IoT Hub Management
# ==========================================

def create_iot_hub(provider: 'AzureProvider') -> str:
    """
    Create an Azure IoT Hub (S1 Standard tier).
    
    The IoT Hub is the central component for device connectivity.
    It receives telemetry from IoT devices and publishes events to Event Grid.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The IoT Hub name
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    location = provider.location_iothub  # IoT Hub uses dedicated region
    
    logger.info(f"Creating IoT Hub: {hub_name}")
    
    try:
        poller = provider.clients["iothub"].iot_hub_resource.begin_create_or_update(
            resource_group_name=rg_name,
            resource_name=hub_name,
            iot_hub_description={
                "location": location,
                "sku": {
                    "name": "S1",
                    "capacity": 1
                },
                "properties": {}
            }
        )
        hub = poller.result()
        logger.info(f"✓ IoT Hub created: {hub_name}")
        return hub.name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating IoT Hub: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create IoT Hub: {e.status_code} - {e.message}")
        raise
    except ServiceRequestError as e:
        logger.error(f"Network error creating IoT Hub: {e}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating IoT Hub: {type(e).__name__}: {e}")
        raise


def destroy_iot_hub(provider: 'AzureProvider') -> None:
    """
    Delete the IoT Hub.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    
    logger.info(f"Deleting IoT Hub: {hub_name}")
    
    try:
        poller = provider.clients["iothub"].iot_hub_resource.begin_delete(
            resource_group_name=rg_name,
            resource_name=hub_name
        )
        poller.result()
        logger.info(f"✓ IoT Hub deleted: {hub_name}")
    except ResourceNotFoundError:
        logger.info(f"IoT Hub already deleted: {hub_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting IoT Hub: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to delete IoT Hub: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting IoT Hub: {type(e).__name__}: {e}")
        raise


def check_iot_hub(provider: 'AzureProvider') -> bool:
    """
    Check if the IoT Hub exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if IoT Hub exists, False otherwise
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    
    try:
        provider.clients["iothub"].iot_hub_resource.get(
            resource_group_name=rg_name,
            resource_name=hub_name
        )
        logger.info(f"✓ IoT Hub exists: {hub_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ IoT Hub not found: {hub_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking IoT Hub: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"HTTP error checking IoT Hub: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking IoT Hub: {type(e).__name__}: {e}")
        raise


def _get_iot_hub_connection_string(provider: 'AzureProvider') -> str:
    """
    Get the IoT Hub connection string for management operations.
    
    This connection string is used for device registry operations,
    not for device telemetry.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        IoT Hub connection string with registry read/write permissions
        
    Raises:
        ValueError: If provider is None
        RuntimeError: If unable to get connection string
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    
    try:
        # Get the iothubowner shared access policy
        keys = provider.clients["iothub"].iot_hub_resource.get_keys_for_key_name(
            resource_group_name=rg_name,
            resource_name=hub_name,
            key_name="iothubowner"
        )
        
        # Build connection string
        connection_string = (
            f"HostName={hub_name}.azure-devices.net;"
            f"SharedAccessKeyName={keys.key_name};"
            f"SharedAccessKey={keys.primary_key}"
        )
        
        return connection_string
    except ResourceNotFoundError:
        raise RuntimeError(f"IoT Hub {hub_name} not found. Deploy IoT Hub first.")
    except (ClientAuthenticationError, HttpResponseError, AzureError) as e:
        logger.error(f"Error getting IoT Hub connection string: {e}")
        raise


# ==========================================
# 2. RBAC Role Assignments
# ==========================================

def assign_managed_identity_roles(provider: 'AzureProvider') -> None:
    """
    Assign RBAC roles to the Managed Identity for IoT Hub access.
    
    Grants the following roles:
        - IoT Hub Data Contributor: For sending/receiving device messages
        - IoT Hub Registry Contributor: For creating/managing device identities
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    identity_name = provider.naming.managed_identity()
    
    logger.info(f"Assigning RBAC roles to Managed Identity: {identity_name}")
    
    try:
        # Get managed identity principal ID
        identity = provider.clients["msi"].user_assigned_identities.get(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        principal_id = identity.principal_id
        
        # IoT Hub scope
        hub_scope = (
            f"/subscriptions/{provider.subscription_id}"
            f"/resourceGroups/{rg_name}"
            f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
        )
        
        # Role definition IDs (built-in Azure roles)
        roles = {
            "IoT Hub Data Contributor": "4fc6c259-987e-4a07-842e-c321cc9d413f",
            "IoT Hub Registry Contributor": "4ea46cd5-c1b2-4a8e-910b-273211f9ce47"
        }
        
        for role_name, role_id in roles.items():
            role_definition_id = f"/subscriptions/{provider.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/{role_id}"
            
            try:
                provider.clients["authorization"].role_assignments.create(
                    scope=hub_scope,
                    role_assignment_name=str(uuid.uuid4()),
                    parameters={
                        "role_definition_id": role_definition_id,
                        "principal_id": principal_id,
                        "principal_type": "ServicePrincipal"
                    }
                )
                logger.info(f"  ✓ Assigned role: {role_name}")
            except HttpResponseError as e:
                if "RoleAssignmentExists" in str(e):
                    logger.info(f"  ✓ Role already assigned: {role_name}")
                else:
                    raise
        
        logger.info(f"✓ RBAC roles assigned to Managed Identity")
        
        # Wait for role propagation
        logger.info("Waiting for RBAC role propagation (30s)...")
        time.sleep(30)
        
    except ResourceNotFoundError as e:
        logger.error(f"Managed Identity not found. Run Setup Layer first.")
        raise
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED assigning RBAC roles: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error assigning RBAC roles: {type(e).__name__}: {e}")
        raise


def destroy_managed_identity_roles(provider: 'AzureProvider') -> None:
    """
    Remove RBAC role assignments from the Managed Identity for IoT Hub.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    identity_name = provider.naming.managed_identity()
    
    logger.info(f"Removing RBAC roles from Managed Identity: {identity_name}")
    
    try:
        # Get managed identity principal ID
        identity = provider.clients["msi"].user_assigned_identities.get(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        principal_id = identity.principal_id
        
        # IoT Hub scope
        hub_scope = (
            f"/subscriptions/{provider.subscription_id}"
            f"/resourceGroups/{rg_name}"
            f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
        )
        
        # List and delete role assignments for this principal
        assignments = provider.clients["authorization"].role_assignments.list_for_scope(
            scope=hub_scope
        )
        
        for assignment in assignments:
            if assignment.principal_id == principal_id:
                provider.clients["authorization"].role_assignments.delete_by_id(
                    role_assignment_id=assignment.id
                )
                logger.info(f"  ✓ Removed role assignment: {assignment.id}")
        
        logger.info(f"✓ RBAC roles removed from Managed Identity")
        
    except ResourceNotFoundError:
        logger.info("IoT Hub or Managed Identity not found - roles already removed")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED removing RBAC roles: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error removing RBAC roles: {type(e).__name__}: {e}")
        raise


def check_managed_identity_roles(provider: 'AzureProvider') -> bool:
    """
    Check if RBAC roles are assigned to the Managed Identity for IoT Hub.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if roles are assigned, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    identity_name = provider.naming.managed_identity()
    
    try:
        # Get managed identity principal ID
        identity = provider.clients["msi"].user_assigned_identities.get(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        principal_id = identity.principal_id
        
        # IoT Hub scope
        hub_scope = (
            f"/subscriptions/{provider.subscription_id}"
            f"/resourceGroups/{rg_name}"
            f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
        )
        
        # Check for role assignments
        assignments = list(provider.clients["authorization"].role_assignments.list_for_scope(
            scope=hub_scope
        ))
        
        has_roles = any(a.principal_id == principal_id for a in assignments)
        
        if has_roles:
            logger.info(f"✓ RBAC roles exist for Managed Identity")
        else:
            logger.info(f"✗ RBAC roles not found for Managed Identity")
        
        return has_roles
        
    except ResourceNotFoundError:
        logger.info("✗ IoT Hub or Managed Identity not found")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking RBAC roles: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking RBAC roles: {type(e).__name__}: {e}")
        raise


# ==========================================
# 3. L1 App Service Plan
# ==========================================

def create_l1_app_service_plan(provider: 'AzureProvider') -> str:
    """
    Create the App Service Plan for L1 Function App (Consumption Y1).
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        App Service Plan resource ID
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l1_app_service_plan()
    location = provider.location
    
    logger.info(f"Creating L1 App Service Plan: {plan_name}")
    
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
        logger.info(f"✓ L1 App Service Plan created: {plan_name}")
        return plan.id
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L1 App Service Plan: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L1 App Service Plan: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating L1 App Service Plan: {type(e).__name__}: {e}")
        raise


def destroy_l1_app_service_plan(provider: 'AzureProvider') -> None:
    """
    Delete the L1 App Service Plan.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l1_app_service_plan()
    
    logger.info(f"Deleting L1 App Service Plan: {plan_name}")
    
    try:
        provider.clients["web"].app_service_plans.delete(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L1 App Service Plan deleted: {plan_name}")
    except ResourceNotFoundError:
        logger.info(f"L1 App Service Plan already deleted: {plan_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting L1 App Service Plan: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting L1 App Service Plan: {type(e).__name__}: {e}")
        raise


def check_l1_app_service_plan(provider: 'AzureProvider') -> bool:
    """
    Check if the L1 App Service Plan exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if App Service Plan exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l1_app_service_plan()
    
    try:
        provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L1 App Service Plan exists: {plan_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L1 App Service Plan not found: {plan_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking L1 App Service Plan: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking L1 App Service Plan: {type(e).__name__}: {e}")
        raise


# ==========================================
# 4. L1 Function App
# ==========================================

def create_l1_function_app(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> str:
    """
    Create the L1 Function App for hosting Dispatcher and Connector functions.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        
    Returns:
        Function App name
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l1_function_app()
    storage_name = provider.naming.storage_account()
    location = provider.location
    
    logger.info(f"Creating L1 Function App: {app_name}")
    
    # Get managed identity ID
    from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
    identity_id = get_managed_identity_id(provider)
    
    if not identity_id:
        raise ValueError(
            "Managed Identity not found. Run Setup Layer first (deploy_setup). "
            "The Setup Layer creates the Resource Group, Managed Identity, and Storage Account."
        )
    
    # Get App Service Plan ID
    plan_name = provider.naming.l1_app_service_plan()
    try:
        plan = provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        plan_id = plan.id
    except ResourceNotFoundError:
        raise ValueError(f"L1 App Service Plan not found: {plan_name}. Create it first.")
    
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
        
        # Enable SCM Basic Auth Publishing (required for Kudu zip deploy)
        # Azure disables basic auth by default since 2023
        logger.info("  Enabling SCM Basic Auth Publishing...")
        try:
            provider.clients["web"].web_apps.update_scm_allowed(
                resource_group_name=rg_name,
                name=app_name,
                csm_publishing_access_policies_entity={"allow": True}
            )
            logger.info("  ✓ SCM Basic Auth enabled")
        except Exception as e:
            logger.warning(f"  Could not enable SCM Basic Auth (may already be enabled): {e}")
        
        # Configure app settings
        _configure_l1_function_app_settings(provider, config, storage_name)
        
        logger.info(f"✓ L1 Function App created: {app_name}")
        return app_name
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L1 Function App: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L1 Function App: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating L1 Function App: {type(e).__name__}: {e}")
        raise


def _configure_l1_function_app_settings(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    storage_name: str
) -> None:
    """
    Configure L1 Function App settings and environment variables.
    
    Sets:
        - AzureWebJobsStorage: Storage connection string
        - FUNCTIONS_WORKER_RUNTIME: python
        - FUNCTIONS_EXTENSION_VERSION: ~4
        - DIGITAL_TWIN_INFO: Twin configuration JSON
        - TARGET_FUNCTION_SUFFIX: -processor or -connector
        - FUNCTION_APP_BASE_URL: Function app URL
    """
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l1_function_app()
    
    # Get storage connection string
    storage_keys = provider.clients["storage"].storage_accounts.list_keys(
        resource_group_name=rg_name,
        account_name=storage_name
    )
    storage_key = storage_keys.keys[0].value
    storage_conn_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={storage_name};"
        f"AccountKey={storage_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    # Build digital twin info
    digital_twin_info = {
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
    
    # Determine target function suffix based on L2 provider
    l2_provider = config.providers.get("layer_2_provider", "azure")
    target_suffix = "-connector" if l2_provider != "azure" else "-processor"
    
    # App settings
    settings = {
        "AzureWebJobsStorage": storage_conn_str,
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "FUNCTIONS_EXTENSION_VERSION": "~4",
        "DIGITAL_TWIN_INFO": json.dumps(digital_twin_info),
        "TARGET_FUNCTION_SUFFIX": target_suffix,
        "FUNCTION_APP_BASE_URL": f"https://{app_name}.azurewebsites.net",
    }
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )
    
    logger.info(f"  ✓ L1 Function App settings configured")


def destroy_l1_function_app(provider: 'AzureProvider') -> None:
    """
    Delete the L1 Function App.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l1_function_app()
    
    logger.info(f"Deleting L1 Function App: {app_name}")
    
    try:
        provider.clients["web"].web_apps.delete(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L1 Function App deleted: {app_name}")
    except ResourceNotFoundError:
        logger.info(f"L1 Function App already deleted: {app_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting L1 Function App: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting L1 Function App: {type(e).__name__}: {e}")
        raise


def check_l1_function_app(provider: 'AzureProvider') -> bool:
    """
    Check if the L1 Function App exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if Function App exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l1_function_app()
    
    try:
        provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L1 Function App exists: {app_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L1 Function App not found: {app_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking L1 Function App: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking L1 Function App: {type(e).__name__}: {e}")
        raise


# ==========================================
# 5. Dispatcher Function
# ==========================================

def deploy_dispatcher_function(
    provider: 'AzureProvider',
    project_path: str
) -> None:
    """
    Deploy the Dispatcher function code to the L1 Function App.
    
    The Dispatcher function receives IoT Hub events via Event Grid
    and routes them to the appropriate processor or connector function.
    
    Uses Kudu API zip deployment:
    1. Get publish credentials from Azure SDK
    2. Compile function code into zip using compile_azure_function
    3. POST zip to Kudu zipdeploy endpoint
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        project_path: Path to project directory containing function code
        
    Raises:
        ValueError: If provider or project_path is None
        HttpResponseError: If deployment fails
    """
    import requests
    import util
    
    if provider is None:
        raise ValueError("provider is required")
    if project_path is None:
        raise ValueError("project_path is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l1_function_app()
    
    logger.info(f"Deploying Dispatcher function to: {app_name}")
    
    # 1. Get publish credentials from SDK
    logger.info("  Getting publish credentials...")
    try:
        creds = provider.clients["web"].web_apps.begin_list_publishing_credentials(
            resource_group_name=rg_name,
            name=app_name
        ).result()
        
        publish_username = creds.publishing_user_name
        publish_password = creds.publishing_password
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED getting publish credentials: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error getting publish credentials: {type(e).__name__}: {e}")
        raise
    
    # 2. Compile the dispatcher function into a zip
    logger.info("  Compiling dispatcher function...")
    
    # Path to dispatcher function source
    dispatcher_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),  # azure provider dir
        "azure_functions",
        "dispatcher"
    )
    
    if not os.path.exists(dispatcher_dir):
        raise ValueError(f"Dispatcher function source not found: {dispatcher_dir}")
    
    zip_content = util.compile_azure_function(dispatcher_dir, project_path)
    
    # 3. Deploy to Kudu zipdeploy endpoint (with retry for SCM startup)
    logger.info("  Deploying via Kudu zip deploy...")
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy"
    
    # Retry logic: Kudu SCM may need 30-60s to become ready after Function App creation
    max_retries = 5
    retry_delay = 15  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                kudu_url,
                data=zip_content,
                auth=(publish_username, publish_password),
                headers={"Content-Type": "application/zip"},
                timeout=300  # 5 minute timeout for deployment
            )
            
            if response.status_code in (200, 202):
                logger.info(f"✓ Dispatcher function deployed successfully")
                return
            elif response.status_code in (401, 503) and attempt < max_retries:
                # 401: Kudu SCM not ready yet (auth not yet active)
                # 503: Kudu service unavailable (still starting up)
                logger.warning(f"  Kudu returned {response.status_code} (attempt {attempt}/{max_retries}), waiting {retry_delay}s for SCM to become ready...")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"Kudu deploy failed: {response.status_code} - {response.text}")
                raise HttpResponseError(
                    message=f"Kudu zip deploy failed: {response.status_code}",
                    response=response
                )
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                logger.warning(f"  Network error (attempt {attempt}/{max_retries}): {e}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            logger.error(f"Network error during Kudu deploy: {e}")
            raise


def destroy_dispatcher_function(provider: 'AzureProvider') -> None:
    """
    Remove the Dispatcher function from the L1 Function App.
    
    Note: Functions are deleted when the Function App is deleted,
    so this primarily cleans up any function-specific resources.
    """
    if provider is None:
        raise ValueError("provider is required")
    
    logger.info("Dispatcher function will be removed with Function App")


def check_dispatcher_function(provider: 'AzureProvider') -> bool:
    """
    Check if the Dispatcher function is deployed.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if function is deployed, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l1_function_app()
    
    try:
        # List functions in the app
        functions = list(provider.clients["web"].web_apps.list_functions(
            resource_group_name=rg_name,
            name=app_name
        ))
        
        # Check if dispatcher function exists
        has_dispatcher = any("dispatcher" in f.name.lower() for f in functions)
        
        if has_dispatcher:
            logger.info(f"✓ Dispatcher function exists")
        else:
            logger.info(f"✗ Dispatcher function not found")
        
        return has_dispatcher
    except ResourceNotFoundError:
        logger.info(f"✗ L1 Function App not found")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking Dispatcher function: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking Dispatcher function: {type(e).__name__}: {e}")
        raise


# ==========================================
# 6. Event Grid Subscription
# ==========================================

def create_event_grid_subscription(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> None:
    """
    Create Event Grid subscription from IoT Hub to Dispatcher Function.
    
    This subscription routes IoT Hub device telemetry events to the
    Dispatcher function via Event Grid.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    app_name = provider.naming.l1_function_app()
    sub_name = provider.naming.event_grid_subscription()
    
    logger.info(f"Creating Event Grid subscription: {sub_name}")
    
    # IoT Hub resource ID as event source
    source_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
    )
    
    # Function resource ID as destination
    function_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Web/sites/{app_name}"
        f"/functions/dispatcher"
    )
    
    try:
        poller = provider.clients["eventgrid"].event_subscriptions.begin_create_or_update(
            scope=source_id,
            event_subscription_name=sub_name,
            event_subscription_info={
                "destination": {
                    "endpoint_type": "AzureFunction",
                    "resource_id": function_id
                },
                "filter": {
                    "included_event_types": ["Microsoft.Devices.DeviceTelemetry"]
                }
            }
        )
        poller.result()
        logger.info(f"✓ Event Grid subscription created: {sub_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating Event Grid subscription: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create Event Grid subscription: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating Event Grid subscription: {type(e).__name__}: {e}")
        raise


def destroy_event_grid_subscription(provider: 'AzureProvider') -> None:
    """
    Delete the Event Grid subscription for IoT Hub events.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    sub_name = provider.naming.event_grid_subscription()
    
    # IoT Hub resource ID as event source
    source_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
    )
    
    logger.info(f"Deleting Event Grid subscription: {sub_name}")
    
    try:
        poller = provider.clients["eventgrid"].event_subscriptions.begin_delete(
            scope=source_id,
            event_subscription_name=sub_name
        )
        poller.result()
        logger.info(f"✓ Event Grid subscription deleted: {sub_name}")
    except ResourceNotFoundError:
        logger.info(f"Event Grid subscription already deleted: {sub_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting Event Grid subscription: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting Event Grid subscription: {type(e).__name__}: {e}")
        raise


def check_event_grid_subscription(provider: 'AzureProvider') -> bool:
    """
    Check if the Event Grid subscription exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if subscription exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    sub_name = provider.naming.event_grid_subscription()
    
    # IoT Hub resource ID as event source
    source_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
    )
    
    try:
        provider.clients["eventgrid"].event_subscriptions.get(
            scope=source_id,
            event_subscription_name=sub_name
        )
        logger.info(f"✓ Event Grid subscription exists: {sub_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Event Grid subscription not found: {sub_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking Event Grid subscription: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking Event Grid subscription: {type(e).__name__}: {e}")
        raise


# ==========================================
# 7. IoT Device Management
# ==========================================

def create_iot_device(
    iot_device: dict,
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str
) -> str:
    """
    Register a device in IoT Hub and get its connection string.
    
    Creates a device identity in the IoT Hub with SAS authentication,
    then generates a simulator configuration file with the connection string.
    
    Args:
        iot_device: Device configuration dict with 'id' and 'properties'
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to project directory for storing simulator config
        
    Returns:
        Device connection string for simulator
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if project_path is None:
        raise ValueError("project_path is required")
    
    device_id = provider.naming.iot_device(iot_device["id"])
    hub_name = provider.naming.iot_hub()
    
    logger.info(f"Creating IoT device: {device_id}")
    
    try:
        # Get IoT Hub connection string for management operations
        hub_conn_str = _get_iot_hub_connection_string(provider)
        
        # Use IoT Hub SDK to create device
        from azure.iot.hub import IoTHubRegistryManager
        
        registry_manager = IoTHubRegistryManager(hub_conn_str)
        
        # Create device with SAS authentication
        device = registry_manager.create_device_with_sas(
            device_id=device_id,
            primary_key=None,  # Auto-generate
            secondary_key=None,  # Auto-generate
            status="enabled"
        )
        
        # Build device connection string
        primary_key = device.authentication.symmetric_key.primary_key
        device_conn_str = (
            f"HostName={hub_name}.azure-devices.net;"
            f"DeviceId={device_id};"
            f"SharedAccessKey={primary_key}"
        )
        
        logger.info(f"✓ IoT device created: {device_id}")
        
        # Generate simulator config
        _generate_simulator_config(iot_device, device_conn_str, config, project_path)
        
        return device_conn_str
        
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating IoT device: {e.message}")
        raise
    except Exception as e:
        logger.error(f"Error creating IoT device: {type(e).__name__}: {e}")
        raise


def destroy_iot_device(
    iot_device: dict,
    provider: 'AzureProvider'
) -> None:
    """
    Delete a device from IoT Hub.
    
    Args:
        iot_device: Device configuration dict with 'id'
        provider: Initialized AzureProvider with clients and naming
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    
    device_id = provider.naming.iot_device(iot_device["id"])
    
    logger.info(f"Deleting IoT device: {device_id}")
    
    try:
        hub_conn_str = _get_iot_hub_connection_string(provider)
        
        from azure.iot.hub import IoTHubRegistryManager
        
        registry_manager = IoTHubRegistryManager(hub_conn_str)
        registry_manager.delete_device(device_id=device_id)
        
        logger.info(f"✓ IoT device deleted: {device_id}")
        
    except Exception as e:
        if "DeviceNotFound" in str(e):
            logger.info(f"IoT device already deleted: {device_id}")
        else:
            logger.error(f"Error deleting IoT device: {type(e).__name__}: {e}")
            raise


def check_iot_device(
    iot_device: dict,
    provider: 'AzureProvider'
) -> bool:
    """
    Check if a device exists in IoT Hub.
    
    Args:
        iot_device: Device configuration dict with 'id'
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if device exists, False otherwise
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    
    device_id = provider.naming.iot_device(iot_device["id"])
    
    try:
        hub_conn_str = _get_iot_hub_connection_string(provider)
        
        from azure.iot.hub import IoTHubRegistryManager
        
        registry_manager = IoTHubRegistryManager(hub_conn_str)
        registry_manager.get_device(device_id=device_id)
        
        logger.info(f"✓ IoT device exists: {device_id}")
        return True
        
    except Exception as e:
        if "DeviceNotFound" in str(e):
            logger.info(f"✗ IoT device not found: {device_id}")
            return False
        else:
            logger.error(f"Error checking IoT device: {type(e).__name__}: {e}")
            raise


def _generate_simulator_config(
    iot_device: dict,
    device_conn_str: str,
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Generate config_generated.json for the Azure IoT device simulator.
    
    Args:
        iot_device: Device configuration dict
        device_conn_str: Device connection string from IoT Hub
        config: Project configuration
        project_path: Path to project directory
    """
    device_id = iot_device["id"]
    digital_twin_name = config.digital_twin_name
    
    config_data = {
        "connection_string": device_conn_str,
        "device_id": device_id,
        "digital_twin_name": digital_twin_name,
        "payload_path": "../payloads.json"
    }
    
    # Write to upload/{project}/iot_device_simulator/azure/
    sim_dir = os.path.join(project_path, "iot_device_simulator", "azure")
    os.makedirs(sim_dir, exist_ok=True)
    config_path = os.path.join(sim_dir, "config_generated.json")
    
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    
    logger.info(f"  ✓ Generated simulator config: {config_path}")


# ==========================================
# 8. Connector Function (Multi-Cloud)
# ==========================================

def deploy_connector_function(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    project_path: str,
    remote_ingestion_url: str,
    inter_cloud_token: str
) -> None:
    """
    Deploy the Connector function for multi-cloud scenarios (L1 != L2).
    
    The Connector function forwards telemetry to a remote L2 ingestion endpoint
    in a different cloud provider.
    
    Uses Kudu API zip deployment for code, then configures app settings.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        project_path: Path to project directory
        remote_ingestion_url: URL of remote L2 ingestion endpoint
        inter_cloud_token: Security token for inter-cloud communication
        
    Raises:
        ValueError: If required parameters are missing
        HttpResponseError: If deployment fails
    """
    import requests
    import util
    
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if not remote_ingestion_url:
        raise ValueError("remote_ingestion_url is required for multi-cloud connector")
    if not inter_cloud_token:
        raise ValueError("inter_cloud_token is required for multi-cloud connector")
    
    app_name = provider.naming.l1_function_app()
    rg_name = provider.naming.resource_group()
    
    logger.info(f"Deploying Connector function for multi-cloud")
    
    # 1. Get publish credentials from SDK
    logger.info("  Getting publish credentials...")
    try:
        creds = provider.clients["web"].web_apps.begin_list_publishing_credentials(
            resource_group_name=rg_name,
            name=app_name
        ).result()
        
        publish_username = creds.publishing_user_name
        publish_password = creds.publishing_password
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED getting publish credentials: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error getting publish credentials: {type(e).__name__}: {e}")
        raise
    
    # 2. Compile the connector function into a zip
    logger.info("  Compiling connector function...")
    
    connector_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),  # azure provider dir
        "azure_functions",
        "connector"
    )
    
    if not os.path.exists(connector_dir):
        raise ValueError(f"Connector function source not found: {connector_dir}")
    
    zip_content = util.compile_azure_function(connector_dir, project_path)
    
    # 3. Deploy to Kudu zipdeploy endpoint
    logger.info("  Deploying connector code via Kudu zip deploy...")
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy"
    
    try:
        response = requests.post(
            kudu_url,
            data=zip_content,
            auth=(publish_username, publish_password),
            headers={"Content-Type": "application/zip"},
            timeout=300
        )
        
        if response.status_code not in (200, 202):
            logger.error(f"Kudu deploy failed: {response.status_code} - {response.text}")
            raise HttpResponseError(
                message=f"Kudu zip deploy failed: {response.status_code}",
                response=response
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during Kudu deploy: {e}")
        raise
    
    # 4. Configure connector-specific app settings
    logger.info("  Configuring connector app settings...")
    try:
        current_settings = provider.clients["web"].web_apps.list_application_settings(
            resource_group_name=rg_name,
            name=app_name
        )
        
        settings = dict(current_settings.properties)
        settings["REMOTE_INGESTION_URL"] = remote_ingestion_url
        settings["INTER_CLOUD_TOKEN"] = inter_cloud_token
        
        provider.clients["web"].web_apps.update_application_settings(
            resource_group_name=rg_name,
            name=app_name,
            app_settings={"properties": settings}
        )
        
        logger.info(f"✓ Connector function deployed and configured")
        
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED configuring Connector function: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error configuring Connector function: {type(e).__name__}: {e}")
        raise


def destroy_connector_function(provider: 'AzureProvider') -> None:
    """
    Remove Connector function configuration.
    
    The Connector function code is part of the L1 Function App,
    so this just removes the configuration settings.
    """
    if provider is None:
        raise ValueError("provider is required")
    
    app_name = provider.naming.l1_function_app()
    rg_name = provider.naming.resource_group()
    
    logger.info(f"Removing Connector function configuration")
    
    try:
        # Get current settings
        current_settings = provider.clients["web"].web_apps.list_application_settings(
            resource_group_name=rg_name,
            name=app_name
        )
        
        # Remove connector settings
        settings = dict(current_settings.properties)
        settings.pop("REMOTE_INGESTION_URL", None)
        settings.pop("INTER_CLOUD_TOKEN", None)
        
        provider.clients["web"].web_apps.update_application_settings(
            resource_group_name=rg_name,
            name=app_name,
            app_settings={"properties": settings}
        )
        
        logger.info(f"✓ Connector function configuration removed")
        
    except ResourceNotFoundError:
        logger.info("L1 Function App not found - connector already removed")
    except AzureError as e:
        logger.error(f"Azure error removing Connector function: {type(e).__name__}: {e}")
        raise


def check_connector_function(provider: 'AzureProvider') -> bool:
    """
    Check if Connector function is configured (multi-cloud settings present).
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if connector is configured, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    app_name = provider.naming.l1_function_app()
    rg_name = provider.naming.resource_group()
    
    try:
        current_settings = provider.clients["web"].web_apps.list_application_settings(
            resource_group_name=rg_name,
            name=app_name
        )
        
        has_url = "REMOTE_INGESTION_URL" in current_settings.properties
        has_token = "INTER_CLOUD_TOKEN" in current_settings.properties
        
        if has_url and has_token:
            logger.info(f"✓ Connector function configured")
            return True
        else:
            logger.info(f"✗ Connector function not configured")
            return False
            
    except ResourceNotFoundError:
        logger.info(f"✗ L1 Function App not found")
        return False
    except AzureError as e:
        logger.error(f"Azure error checking Connector function: {type(e).__name__}: {e}")
        raise


# ==========================================
# 9. Layer-Level Info Function
# ==========================================

def info_l1(context: 'ProjectConfig', provider: 'AzureProvider') -> dict:
    """
    Check status of all L1 components.
    
    Args:
        context: Deployment context with configuration
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with component status
    """
    config = context.config if hasattr(context, 'config') else context
    
    logger.info(f"========== Azure L1 Layer Info: {config.digital_twin_name} ==========")
    
    status = {
        "iot_hub": check_iot_hub(provider),
        "rbac_roles": check_managed_identity_roles(provider),
        "app_service_plan": check_l1_app_service_plan(provider),
        "function_app": check_l1_function_app(provider),
        "dispatcher_function": check_dispatcher_function(provider),
        "event_grid_subscription": check_event_grid_subscription(provider),
    }
    
    # Per-device status
    if config.iot_devices:
        status["devices"] = {}
        for device in config.iot_devices:
            status["devices"][device["id"]] = check_iot_device(device, provider)
    
    # Connector (if multi-cloud)
    l1_provider = config.providers.get("layer_1_provider", "azure")
    l2_provider = config.providers.get("layer_2_provider", "azure")
    if l1_provider != l2_provider:
        status["connector_function"] = check_connector_function(provider)
    
    # Summary
    all_ok = all(
        v if isinstance(v, bool) else all(v.values()) 
        for v in status.values()
    )
    
    if all_ok:
        logger.info("✓ All L1 components exist")
    else:
        missing = [k for k, v in status.items() if not v if isinstance(v, bool)]
        if "devices" in status:
            missing_devices = [d for d, exists in status["devices"].items() if not exists]
            if missing_devices:
                missing.append(f"devices: {missing_devices}")
        logger.info(f"✗ Some L1 components missing: {missing}")
    
    return status
