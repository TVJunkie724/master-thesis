"""
Layer 4 (Azure Digital Twins) Component Implementations for Azure.

This module contains ALL ADT implementations that are
deployed by the L4 adapter.

Components Managed:
- ADT Instance: Azure Digital Twins service instance
- DTDL Models: Digital Twin Definition Language models
- Twins: Digital twin instances with properties
- Relationships: Connections between twins
- L4 Function App: Contains ADT Updater (single-cloud)
- Event Grid Subscription: IoT Hub → ADT Updater

Architecture:
    ┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │   IoT Hub   │ ──► │   Event Grid    │ ──► │   ADT Updater   │
    └─────────────┘     │   Subscription  │     │   (Function)    │
                        └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │ Azure Digital   │
                                                │     Twins       │
                                                └─────────────────┘

Architecture Note:
    Azure ADT is PUSH-BASED (unlike AWS TwinMaker which is pull-based).
    Data must be actively pushed to ADT via:
    - Single-cloud: Event Grid → ADT Updater function
    - Multi-cloud: HTTP → ADT Pusher (in L0 Glue layer)

Authentication:
    - Single-cloud: Managed Identity with Azure Digital Twins Data Owner role
    - Multi-cloud: X-Inter-Cloud-Token header for ADT Pusher
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any
import logging
import json
import os

from azure.core.exceptions import (
    ResourceNotFoundError,
    HttpResponseError,
    ClientAuthenticationError,
    AzureError
)

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
# ADT Instance Management
# ==========================================

def create_adt_instance(provider: 'AzureProvider') -> str:
    """
    Create an Azure Digital Twins instance.
    
    The ADT instance is the core service for digital twin management.
    It stores DTDL models, twin instances, and relationships.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The ADT instance host name (URL endpoint)
        
    Raises:
        ValueError: If provider is None
        HttpResponseError: If creation fails
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    adt_name = provider.naming.digital_twins_instance()
    location = provider.location
    
    # Skip if already exists
    if check_adt_instance(provider):
        logger.info(f"✓ ADT Instance already exists (skipping): {adt_name}")
        # Retrieve existing host name
        existing = provider.clients["digitaltwins_mgmt"].digital_twins.get(
            resource_group_name=rg_name,
            resource_name=adt_name
        )
        return f"https://{existing.host_name}"
    
    logger.info(f"Creating ADT Instance: {adt_name}")
    
    try:
        # Create ADT instance
        poller = provider.clients["digitaltwins_mgmt"].digital_twins.begin_create_or_update(
            resource_group_name=rg_name,
            resource_name=adt_name,
            digital_twins_create={"location": location}
        )
        
        result = poller.result()
        host_name = result.host_name
        
        logger.info(f"✓ ADT Instance created: {adt_name}")
        logger.info(f"  Endpoint: https://{host_name}")
        
        # Grant Managed Identity access to ADT
        _grant_managed_identity_access(provider, adt_name)
        
        return f"https://{host_name}"
        
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating ADT Instance: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create ADT Instance: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating ADT Instance: {type(e).__name__}: {e}")
        raise


def _grant_managed_identity_access(provider: 'AzureProvider', adt_name: str) -> None:
    """
    Grant the Managed Identity 'Azure Digital Twins Data Owner' role on the ADT instance.
    
    This allows the Function App (with the managed identity) to read and write ADT data.
    
    Args:
        provider: Azure Provider instance
        adt_name: Name of the ADT instance
    """
    from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
    import uuid
    
    rg_name = provider.naming.resource_group()
    identity_id = get_managed_identity_id(provider)
    
    if not identity_id:
        logger.warning("Managed Identity not found - skipping RBAC assignment")
        return
    
    # Get identity principal ID
    identity_name = provider.naming.managed_identity()
    try:
        identity = provider.clients["msi"].user_assigned_identities.get(
            resource_group_name=rg_name,
            resource_name=identity_name
        )
        principal_id = identity.principal_id
    except Exception as e:
        logger.warning(f"Could not get identity principal ID: {e}")
        return
    
    # Azure Digital Twins Data Owner role definition ID
    # This is a built-in role: bcd981a7-7f74-457b-83e1-cceb9e632ffe
    adt_data_owner_role = "bcd981a7-7f74-457b-83e1-cceb9e632ffe"
    
    # Build scope for the ADT instance
    scope = f"/subscriptions/{provider.subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.DigitalTwins/digitalTwinsInstances/{adt_name}"
    
    # Create role assignment
    role_assignment_name = str(uuid.uuid4())
    
    try:
        provider.clients["authorization"].role_assignments.create(
            scope=scope,
            role_assignment_name=role_assignment_name,
            parameters={
                "properties": {
                    "role_definition_id": f"/subscriptions/{provider.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/{adt_data_owner_role}",
                    "principal_id": principal_id,
                    "principal_type": "ServicePrincipal"
                }
            }
        )
        logger.info(f"  ✓ Granted 'Azure Digital Twins Data Owner' role to Managed Identity")
    except HttpResponseError as e:
        if "RoleAssignmentExists" in str(e):
            logger.info(f"  Role assignment already exists")
        else:
            logger.warning(f"  Could not create role assignment: {e}")


def destroy_adt_instance(provider: 'AzureProvider') -> None:
    """
    Delete the Azure Digital Twins instance.
    
    This will delete all models, twins, and relationships within the instance.
    
    Args:
        provider: Azure Provider instance
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    adt_name = provider.naming.digital_twins_instance()
    
    logger.info(f"Deleting ADT Instance: {adt_name}")
    
    try:
        poller = provider.clients["digitaltwins_mgmt"].digital_twins.begin_delete(
            resource_group_name=rg_name,
            resource_name=adt_name
        )
        poller.result()
        logger.info(f"✓ ADT Instance deleted: {adt_name}")
    except ResourceNotFoundError:
        logger.info(f"ADT Instance already deleted: {adt_name}")
    except HttpResponseError as e:
        logger.error(f"Failed to delete ADT Instance: {e.status_code} - {e.message}")
        raise


def check_adt_instance(provider: 'AzureProvider') -> bool:
    """
    Check if the Azure Digital Twins instance exists.
    
    Args:
        provider: Azure Provider instance
        
    Returns:
        True if ADT instance exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    adt_name = provider.naming.digital_twins_instance()
    
    try:
        result = provider.clients["digitaltwins_mgmt"].digital_twins.get(
            resource_group_name=rg_name,
            resource_name=adt_name
        )
        logger.info(f"✓ ADT Instance exists: {adt_name}")
        logger.info(f"  Endpoint: https://{result.host_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ ADT Instance not found: {adt_name}")
        return False


def get_adt_instance_url(provider: 'AzureProvider') -> Optional[str]:
    """
    Get the Azure Digital Twins instance endpoint URL.
    
    Args:
        provider: Azure Provider instance
        
    Returns:
        The ADT instance URL or None if not found
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    adt_name = provider.naming.digital_twins_instance()
    
    try:
        result = provider.clients["digitaltwins_mgmt"].digital_twins.get(
            resource_group_name=rg_name,
            resource_name=adt_name
        )
        return f"https://{result.host_name}"
    except ResourceNotFoundError:
        return None


# ==========================================
# DTDL Model Management
# ==========================================

def upload_adt_models(
    provider: 'AzureProvider',
    models: List[Dict[str, Any]]
) -> None:
    """
    Upload DTDL models to the Azure Digital Twins instance.
    
    Models define the schema for digital twins (properties, components, relationships).
    
    Args:
        provider: Azure Provider instance
        models: List of DTDL model definitions (JSON objects)
        
    Raises:
        ValueError: If provider or models is None/empty
        HttpResponseError: If upload fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not models:
        raise ValueError("models is required and cannot be empty")
    
    adt_url = get_adt_instance_url(provider)
    if not adt_url:
        raise ValueError("ADT Instance not found - deploy L4 first")
    
    logger.info(f"Uploading {len(models)} DTDL models to ADT")
    
    # Create ADT data client
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    
    credential = DefaultAzureCredential()
    adt_client = DigitalTwinsClient(adt_url, credential)
    
    try:
        # Upload all models at once (handles dependencies)
        adt_client.create_models(models)
        logger.info(f"✓ Uploaded {len(models)} DTDL models")
    except HttpResponseError as e:
        if "ModelAlreadyExists" in str(e):
            logger.info(f"  Models already exist (skipping)")
        else:
            logger.error(f"Failed to upload models: {e}")
            raise


def delete_adt_models(
    provider: 'AzureProvider',
    model_ids: List[str]
) -> None:
    """
    Delete DTDL models from the Azure Digital Twins instance.
    
    Models must be deleted in reverse dependency order.
    
    Args:
        provider: Azure Provider instance
        model_ids: List of model IDs to delete (in reverse order)
    """
    if provider is None:
        raise ValueError("provider is required")
    if not model_ids:
        return
    
    adt_url = get_adt_instance_url(provider)
    if not adt_url:
        logger.info("ADT Instance not found - models already deleted")
        return
    
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    
    credential = DefaultAzureCredential()
    adt_client = DigitalTwinsClient(adt_url, credential)
    
    for model_id in reversed(model_ids):
        try:
            adt_client.delete_model(model_id)
            logger.info(f"✓ Deleted model: {model_id}")
        except ResourceNotFoundError:
            logger.info(f"  Model already deleted: {model_id}")
        except HttpResponseError as e:
            logger.warning(f"  Could not delete model {model_id}: {e}")


# ==========================================
# Twin Instance Management
# ==========================================

def create_adt_twin(
    provider: 'AzureProvider',
    twin_id: str,
    model_id: str,
    properties: Optional[Dict[str, Any]] = None
) -> None:
    """
    Create a digital twin instance.
    
    Args:
        provider: Azure Provider instance
        twin_id: Unique ID for the twin
        model_id: DTDL model ID for the twin type
        properties: Initial property values
    """
    if provider is None:
        raise ValueError("provider is required")
    if not twin_id:
        raise ValueError("twin_id is required")
    if not model_id:
        raise ValueError("model_id is required")
    
    adt_url = get_adt_instance_url(provider)
    if not adt_url:
        raise ValueError("ADT Instance not found - deploy L4 first")
    
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    
    credential = DefaultAzureCredential()
    adt_client = DigitalTwinsClient(adt_url, credential)
    
    # Build twin definition
    twin_data = {
        "$metadata": {"$model": model_id},
        "$dtId": twin_id
    }
    if properties:
        twin_data.update(properties)
    
    try:
        adt_client.upsert_digital_twin(twin_id, twin_data)
        logger.info(f"✓ Created twin: {twin_id}")
    except HttpResponseError as e:
        logger.error(f"Failed to create twin {twin_id}: {e}")
        raise


def destroy_adt_twin(provider: 'AzureProvider', twin_id: str) -> None:
    """
    Delete a digital twin instance.
    
    Args:
        provider: Azure Provider instance
        twin_id: ID of the twin to delete
    """
    if provider is None:
        raise ValueError("provider is required")
    if not twin_id:
        raise ValueError("twin_id is required")
    
    adt_url = get_adt_instance_url(provider)
    if not adt_url:
        return
    
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    
    credential = DefaultAzureCredential()
    adt_client = DigitalTwinsClient(adt_url, credential)
    
    try:
        # First delete all relationships
        relationships = adt_client.list_relationships(twin_id)
        for rel in relationships:
            adt_client.delete_relationship(twin_id, rel["$relationshipId"])
        
        # Then delete the twin
        adt_client.delete_digital_twin(twin_id)
        logger.info(f"✓ Deleted twin: {twin_id}")
    except ResourceNotFoundError:
        logger.info(f"  Twin already deleted: {twin_id}")


# ==========================================
# Relationship Management
# ==========================================

def create_adt_relationship(
    provider: 'AzureProvider',
    source_twin_id: str,
    target_twin_id: str,
    relationship_name: str,
    relationship_id: Optional[str] = None
) -> None:
    """
    Create a relationship between two twins.
    
    Args:
        provider: Azure Provider instance
        source_twin_id: ID of the source twin
        target_twin_id: ID of the target twin
        relationship_name: Name of the relationship type (from DTDL model)
        relationship_id: Optional unique ID for the relationship
    """
    if provider is None:
        raise ValueError("provider is required")
    if not source_twin_id:
        raise ValueError("source_twin_id is required")
    if not target_twin_id:
        raise ValueError("target_twin_id is required")
    if not relationship_name:
        raise ValueError("relationship_name is required")
    
    adt_url = get_adt_instance_url(provider)
    if not adt_url:
        raise ValueError("ADT Instance not found")
    
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    import uuid
    
    credential = DefaultAzureCredential()
    adt_client = DigitalTwinsClient(adt_url, credential)
    
    rel_id = relationship_id or str(uuid.uuid4())
    
    relationship = {
        "$relationshipId": rel_id,
        "$sourceId": source_twin_id,
        "$targetId": target_twin_id,
        "$relationshipName": relationship_name
    }
    
    try:
        adt_client.upsert_relationship(source_twin_id, rel_id, relationship)
        logger.info(f"✓ Created relationship: {source_twin_id} --{relationship_name}--> {target_twin_id}")
    except HttpResponseError as e:
        logger.error(f"Failed to create relationship: {e}")
        raise


# ==========================================
# L4 Function App Management
# ==========================================

def create_l4_app_service_plan(provider: 'AzureProvider') -> str:
    """
    Create Y1 Consumption App Service Plan for L4 functions.
    
    Args:
        provider: Azure Provider instance
        
    Returns:
        Full resource ID of the App Service Plan
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l4_app_service_plan()
    location = provider.location
    
    # Skip if already exists
    if check_l4_app_service_plan(provider):
        logger.info(f"✓ L4 App Service Plan already exists (skipping): {plan_name}")
        return f"/subscriptions/{provider.subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Web/serverfarms/{plan_name}"
    
    logger.info(f"Creating L4 App Service Plan: {plan_name}")
    
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
        logger.info(f"✓ L4 App Service Plan created: {plan_name}")
        return plan_id
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L4 App Service Plan: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L4 App Service Plan: {e.status_code} - {e.message}")
        raise


def destroy_l4_app_service_plan(provider: 'AzureProvider') -> None:
    """Delete the L4 App Service Plan."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l4_app_service_plan()
    
    logger.info(f"Deleting L4 App Service Plan: {plan_name}")
    
    try:
        provider.clients["web"].app_service_plans.delete(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L4 App Service Plan deleted: {plan_name}")
    except ResourceNotFoundError:
        logger.info(f"L4 App Service Plan already deleted: {plan_name}")


def check_l4_app_service_plan(provider: 'AzureProvider') -> bool:
    """Check if L4 App Service Plan exists."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.l4_app_service_plan()
    
    try:
        provider.clients["web"].app_service_plans.get(
            resource_group_name=rg_name,
            name=plan_name
        )
        logger.info(f"✓ L4 App Service Plan exists: {plan_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L4 App Service Plan not found: {plan_name}")
        return False


def create_l4_function_app(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    adt_instance_url: str
) -> str:
    """
    Create the L4 Function App for ADT Updater.
    
    Args:
        provider: Azure Provider instance
        config: Project configuration
        adt_instance_url: URL of the ADT instance
        
    Returns:
        Function App name
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if not adt_instance_url:
        raise ValueError("adt_instance_url is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l4_function_app()
    storage_name = provider.naming.storage_account()
    location = provider.location
    
    # Skip if already exists
    if check_l4_function_app(provider):
        logger.info(f"✓ L4 Function App already exists (skipping): {app_name}")
        return app_name
    
    logger.info(f"Creating L4 Function App: {app_name}")
    
    # Get managed identity ID
    from src.providers.azure.layers.layer_setup_azure import get_managed_identity_id
    identity_id = get_managed_identity_id(provider)
    
    if not identity_id:
        raise ValueError(
            "Managed Identity not found. Run Setup Layer first."
        )
    
    # Create App Service Plan first
    plan_id = create_l4_app_service_plan(provider)
    
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
            "reserved": True,
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
        poller.result()
        
        # Configure app settings
        _configure_l4_function_app_settings(provider, config, storage_name, adt_instance_url)
        
        # Deploy function code
        _deploy_l4_functions(provider)
        
        logger.info(f"✓ L4 Function App created: {app_name}")
        return app_name
        
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating L4 Function App: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create L4 Function App: {e.status_code} - {e.message}")
        raise


def _configure_l4_function_app_settings(
    provider: 'AzureProvider',
    config: 'ProjectConfig',
    storage_name: str,
    adt_instance_url: str
) -> None:
    """Configure L4 Function App settings and environment variables."""
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l4_function_app()
    
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
        "ADT_INSTANCE_URL": adt_instance_url,
        "DIGITAL_TWIN_INFO": json.dumps(twin_info),
    }
    
    provider.clients["web"].web_apps.update_application_settings(
        resource_group_name=rg_name,
        name=app_name,
        app_settings={"properties": settings}
    )
    
    logger.info(f"  ✓ L4 Function App settings configured")


def _deploy_l4_functions(provider: 'AzureProvider') -> None:
    """Deploy L4 function code via Kudu zip deploy."""
    import requests
    import zipfile
    import io
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l4_function_app()
    
    logger.info("  Deploying L4 function code...")
    
    # Get publish credentials
    try:
        creds = provider.clients["web"].web_apps.begin_list_publishing_credentials(
            resource_group_name=rg_name,
            name=app_name
        ).result()
        
        publish_username = creds.publishing_user_name
        publish_password = creds.publishing_password
    except Exception as e:
        logger.error(f"Failed to get publish credentials: {e}")
        raise
    
    # Build zip with L4 functions
    azure_functions_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "azure_functions"
    )
    
    # L4 functions to include
    l4_functions = ["adt-updater"]
    
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
        for func_name in l4_functions:
            func_dir = os.path.join(azure_functions_dir, func_name)
            if os.path.exists(func_dir):
                for root, dirs, files in os.walk(func_dir):
                    for file in files:
                        if file.endswith('.py') or file == 'function.json':
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, azure_functions_dir)
                            zf.write(file_path, rel_path)
        
        # Add host.json if present
        for extra_file in ['host.json', 'requirements.txt']:
            extra_path = os.path.join(azure_functions_dir, extra_file)
            if os.path.exists(extra_path):
                zf.write(extra_path, extra_file)
    
    zip_content = zip_buffer.getvalue()
    
    # Deploy to Kudu using shared helper with retry
    from src.providers.azure.layers.deployment_helpers import deploy_to_kudu
    deploy_to_kudu(
        app_name=app_name,
        zip_content=zip_content,
        publish_username=publish_username,
        publish_password=publish_password
    )
    logger.info(f"  ✓ L4 function code deployed")


def destroy_l4_function_app(provider: 'AzureProvider') -> None:
    """Delete the L4 Function App."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l4_function_app()
    
    logger.info(f"Deleting L4 Function App: {app_name}")
    
    try:
        provider.clients["web"].web_apps.delete(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L4 Function App deleted: {app_name}")
    except ResourceNotFoundError:
        logger.info(f"L4 Function App already deleted: {app_name}")


def check_l4_function_app(provider: 'AzureProvider') -> bool:
    """Check if L4 Function App exists."""
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.l4_function_app()
    
    try:
        provider.clients["web"].web_apps.get(
            resource_group_name=rg_name,
            name=app_name
        )
        logger.info(f"✓ L4 Function App exists: {app_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ L4 Function App not found: {app_name}")
        return False


# ==========================================
# ADT Event Grid Subscription (Single-Cloud)
# ==========================================

def create_adt_event_grid_subscription(
    provider: 'AzureProvider',
    config: 'ProjectConfig'
) -> None:
    """
    Create Event Grid subscription from IoT Hub to ADT Updater Function.
    
    This subscription routes IoT Hub device telemetry events to the
    ADT Updater function via Event Grid. Only used in single-cloud
    scenarios where both IoT Hub and ADT are on Azure.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration
        
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
    hub_name = provider.naming.iot_hub()
    app_name = provider.naming.l4_function_app()
    sub_name = provider.naming.adt_event_grid_subscription()
    
    logger.info(f"Creating ADT Event Grid subscription: {sub_name}")
    
    # IoT Hub resource ID as event source
    source_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
    )
    
    # Function resource ID as destination (ADT Updater)
    function_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Web/sites/{app_name}"
        f"/functions/adt-updater"
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
        logger.info(f"✓ ADT Event Grid subscription created: {sub_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED creating ADT Event Grid subscription: {e.message}")
        raise
    except HttpResponseError as e:
        logger.error(f"Failed to create ADT Event Grid subscription: {e.status_code} - {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error creating ADT Event Grid subscription: {type(e).__name__}: {e}")
        raise


def destroy_adt_event_grid_subscription(provider: 'AzureProvider') -> None:
    """
    Delete the ADT Event Grid subscription.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    sub_name = provider.naming.adt_event_grid_subscription()
    
    # IoT Hub resource ID as event source
    source_id = (
        f"/subscriptions/{provider.subscription_id}"
        f"/resourceGroups/{rg_name}"
        f"/providers/Microsoft.Devices/IotHubs/{hub_name}"
    )
    
    logger.info(f"Deleting ADT Event Grid subscription: {sub_name}")
    
    try:
        poller = provider.clients["eventgrid"].event_subscriptions.begin_delete(
            scope=source_id,
            event_subscription_name=sub_name
        )
        poller.result()
        logger.info(f"✓ ADT Event Grid subscription deleted: {sub_name}")
    except ResourceNotFoundError:
        logger.info(f"ADT Event Grid subscription already deleted: {sub_name}")
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED deleting ADT Event Grid subscription: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error deleting ADT Event Grid subscription: {type(e).__name__}: {e}")
        raise


def check_adt_event_grid_subscription(provider: 'AzureProvider') -> bool:
    """
    Check if the ADT Event Grid subscription exists.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if subscription exists, False otherwise
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    sub_name = provider.naming.adt_event_grid_subscription()
    
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
        logger.info(f"✓ ADT Event Grid subscription exists: {sub_name}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ ADT Event Grid subscription not found: {sub_name}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking ADT Event Grid subscription: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking ADT Event Grid subscription: {type(e).__name__}: {e}")
        raise


# ==========================================
# Info / Status Checks
# ==========================================

def info_l4(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Get status information for all L4 components.
    
    Args:
        context: Deployment context with configuration
        provider: Azure Provider instance
    
    Returns:
        Dictionary with component status
    """
    status = {
        "adt_instance": check_adt_instance(provider),
        "app_service_plan": check_l4_app_service_plan(provider),
        "function_app": check_l4_function_app(provider),
    }
    
    return status

