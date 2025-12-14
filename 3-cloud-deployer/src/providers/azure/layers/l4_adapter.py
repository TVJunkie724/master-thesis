"""
Azure Layer 4 (Twin Management) Adapter.

This module provides context-based wrappers around the Layer 4
deployment functions, passing provider and config explicitly.

The adapter is the entry point called by the deployer strategy
and orchestrates the deployment of all L4 components.

Deployment Order:
    1. ADT Instance (Azure Digital Twins service)
    2. DTDL Models (from config_hierarchy.json / azure_hierarchy.json)
    3. Digital Twins (instances from hierarchy)
    4. Relationships (between twins)
    5. L4 App Service Plan
    6. L4 Function App (contains ADT Updater)
    7. Event Grid Subscription (IoT Hub → ADT Updater) [single-cloud only]

Pre-flight Check:
    L4 requires L3 Hot to be deployed first for the Hot Reader endpoint
    that ADT may need to read from.

Architecture Note:
    Azure ADT is PUSH-BASED (unlike AWS TwinMaker which is pull-based).
    - Single-cloud: IoT Hub → Event Grid → ADT Updater → ADT
    - Multi-cloud: Remote Persister → ADT Pusher (L0) → ADT
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import os
import json
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AzureProvider


def _check_l3_deployed(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Verify that L3 Hot is deployed before deploying L4.
    
    L4 depends on L3 for:
    - Cosmos DB for hot storage queries
    - Hot Reader endpoints for data access
    
    Uses info_l3 to check all L3 Hot components.
    
    Raises:
        RuntimeError: If L3 Hot is not fully deployed
    """
    from .l3_adapter import info_l3
    
    l3_status = info_l3(context, provider)
    
    # Check if L3 Hot components are deployed
    hot_storage = l3_status.get("hot_storage", {})
    
    # Verify core components exist
    cosmos_exists = hot_storage.get("cosmos_account", {}).get("exists", False)
    container_exists = hot_storage.get("hot_container", {}).get("exists", False)
    
    if cosmos_exists and container_exists:
        logger.info("[L4] ✓ Pre-flight check: L3 Hot is deployed")
        return
    else:
        missing = []
        if not cosmos_exists:
            missing.append("Cosmos DB Account")
        if not container_exists:
            missing.append("Hot Container")
        raise RuntimeError(
            f"[L4] Pre-flight check FAILED: L3 Hot is NOT fully deployed. "
            f"Missing: {', '.join(missing)}. Run deploy_l3_hot first."
        )


def _save_adt_url_to_inter_cloud(project_path: str, adt_url: str) -> None:
    """
    Save ADT Instance URL to config_inter_cloud.json for L0 ADT Pusher.
    
    This allows L0 (deployed separately) to get the ADT URL.
    
    Args:
        project_path: Path to project root
        adt_url: The ADT instance URL
    """
    inter_cloud_path = os.path.join(project_path, "config_inter_cloud.json")
    
    # Load existing config or create new
    if os.path.exists(inter_cloud_path):
        with open(inter_cloud_path, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Add ADT URL
    if "azure" not in config:
        config["azure"] = {}
    config["azure"]["l4_adt_instance_url"] = adt_url
    
    # Save back
    with open(inter_cloud_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"  ✓ Saved ADT URL to config_inter_cloud.json")


def _load_hierarchy_config(project_path: str) -> Optional[Dict[str, Any]]:
    """
    Load hierarchy configuration for DTDL model generation.
    
    Tries azure_hierarchy.json first, then falls back to config_hierarchy.json.
    
    Args:
        project_path: Path to project root
        
    Returns:
        Hierarchy config dict or None if not found
    """
    # Try Azure-specific hierarchy first
    azure_path = os.path.join(project_path, "azure_hierarchy.json")
    if os.path.exists(azure_path):
        with open(azure_path, 'r') as f:
            logger.info(f"  Loading hierarchy from azure_hierarchy.json")
            return json.load(f)
    
    # Fall back to general hierarchy
    general_path = os.path.join(project_path, "config_hierarchy.json")
    if os.path.exists(general_path):
        with open(general_path, 'r') as f:
            logger.info(f"  Loading hierarchy from config_hierarchy.json")
            return json.load(f)
    
    logger.warning("  No hierarchy configuration found (azure_hierarchy.json or config_hierarchy.json)")
    return None


def _update_adt_pusher_url(
    context: 'DeploymentContext',
    provider: 'AzureProvider',
    adt_url: str
) -> None:
    """
    Update the L0 ADT Pusher function with the ADT URL.
    
    This is called during L4 deployment to update the ADT Pusher
    (deployed in L0 for multi-cloud scenarios) with the actual ADT URL.
    
    Only updates if:
    - L2 provider != L4 provider (multi-cloud boundary exists)
    - L4 provider is Azure
    - L0 Glue Function App exists
    
    Args:
        context: Deployment context
        provider: Azure Provider instance
        adt_url: The ADT instance URL
    """
    from .layer_0_glue import check_glue_function_app, update_adt_pusher_url
    
    # Check if multi-cloud L2→L4 boundary exists
    l2_provider = context.config.providers["layer_2_provider"].lower()
    l4_provider = context.config.providers["layer_4_provider"].lower()
    
    if l2_provider == l4_provider:
        logger.info("[L4] Single-cloud: No ADT Pusher to update")
        return
    
    if l4_provider != "azure":
        logger.info("[L4] L4 is not Azure: No ADT Pusher to update")
        return
    
    # Check if L0 Glue Function App exists
    if not check_glue_function_app(provider):
        logger.info("[L4] L0 Glue Function App not deployed: ADT Pusher update skipped")
        return
    
    # Update ADT Pusher with the ADT URL
    update_adt_pusher_url(provider, adt_url)
    logger.info("[L4] ✓ Updated L0 ADT Pusher with ADT URL")

def deploy_l4(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Deploy Layer 4 Twin Management components.
    
    Components deployed:
        - ADT Instance (Azure Digital Twins service)
        - DTDL Models (from hierarchy config)
        - Digital Twins (instances)
        - Relationships (between twins)
        - L4 Function App (contains ADT Updater)
        - Event Grid Subscription (single-cloud only)
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AzureProvider instance
        
    Raises:
        RuntimeError: If L3 is not deployed
        ValueError: If required parameters are missing
    """
    from .layer_4_adt import (
        create_adt_instance,
        create_l4_function_app,
    )
    
    logger.info(f"[L4] Deploying Layer 4 Twin Management for {context.config.digital_twin_name}")
    context.set_active_layer("4")
    
    # Pre-flight check
    if not _check_l3_deployed(context, provider):
        raise RuntimeError(
            "L4 requires L3 Hot to be deployed first. "
            "Please deploy L3 before deploying L4."
        )
    
    project_path = str(context.project_path.parent.parent)
    
    # 1. Create ADT Instance
    adt_url = create_adt_instance(provider)
    
    # 2. Save ADT URL for multi-cloud L0 ADT Pusher
    _save_adt_url_to_inter_cloud(project_path, adt_url)
    
    # 3. Update L0 ADT Pusher with ADT URL (if deployed for multi-cloud)
    _update_adt_pusher_url(context, provider, adt_url)
    
    # 4. Load and upload DTDL models (if hierarchy config exists)
    hierarchy = _load_hierarchy_config(project_path)
    if hierarchy:
        _deploy_models_and_twins(provider, hierarchy)
    
    # 5. Create L4 Function App with ADT Updater
    create_l4_function_app(provider, context.config, adt_url)
    
    # 6. Create Event Grid subscription (single-cloud only)
    _setup_event_grid_subscription(context, provider)
    
    logger.info(f"[L4] Layer 4 Twin Management deployment complete")


def _deploy_models_and_twins(
    provider: 'AzureProvider',
    hierarchy: Dict[str, Any]
) -> None:
    """
    Deploy DTDL models and create twins from hierarchy config.
    
    Args:
        provider: Azure Provider instance
        hierarchy: Hierarchy configuration
    """
    from .layer_4_adt import upload_adt_models, create_adt_twin
    
    # Convert hierarchy to DTDL models
    models = _hierarchy_to_dtdl_models(hierarchy)
    
    if models:
        upload_adt_models(provider, models)
        
        # Create twin instances
        _create_twins_from_hierarchy(provider, hierarchy)


def _hierarchy_to_dtdl_models(hierarchy: Dict[str, Any]) -> list:
    """
    Convert hierarchy config to DTDL model definitions.
    
    This translates the project's hierarchy format to Azure Digital Twins
    Definition Language (DTDL) v2 models.
    
    Args:
        hierarchy: Hierarchy configuration
        
    Returns:
        List of DTDL model definitions
    """
    models = []
    
    # Base namespace for models
    namespace = "dtmi:com:twin2clouds"
    
    # Get twin types from hierarchy
    twin_types = hierarchy.get("twin_types", {})
    
    for type_name, type_config in twin_types.items():
        model_id = f"{namespace}:{type_name};1"
        
        # Build DTDL model
        model = {
            "@id": model_id,
            "@type": "Interface",
            "@context": "dtmi:dtdl:context;2",
            "displayName": type_config.get("display_name", type_name),
            "contents": []
        }
        
        # Add properties
        properties = type_config.get("properties", {})
        for prop_name, prop_config in properties.items():
            prop_type = prop_config.get("type", "string")
            dtdl_type = _map_to_dtdl_type(prop_type)
            
            model["contents"].append({
                "@type": "Property",
                "name": prop_name,
                "schema": dtdl_type,
                "writable": True
            })
        
        # Add relationships
        relationships = type_config.get("relationships", [])
        for rel in relationships:
            rel_name = rel.get("name", "contains")
            target_type = rel.get("target_type")
            
            rel_def = {
                "@type": "Relationship",
                "name": rel_name
            }
            
            if target_type:
                rel_def["target"] = f"{namespace}:{target_type};1"
            
            model["contents"].append(rel_def)
        
        models.append(model)
    
    logger.info(f"  Generated {len(models)} DTDL models from hierarchy")
    return models


def _map_to_dtdl_type(type_str: str) -> str:
    """Map common type names to DTDL types."""
    type_map = {
        "string": "string",
        "str": "string",
        "int": "integer",
        "integer": "integer",
        "float": "double",
        "double": "double",
        "number": "double",
        "bool": "boolean",
        "boolean": "boolean",
        "date": "date",
        "datetime": "dateTime",
        "time": "time",
    }
    return type_map.get(type_str.lower(), "string")


def _create_twins_from_hierarchy(
    provider: 'AzureProvider',
    hierarchy: Dict[str, Any]
) -> None:
    """
    Create twin instances from hierarchy config.
    
    Args:
        provider: Azure Provider instance
        hierarchy: Hierarchy configuration
    """
    from .layer_4_adt import create_adt_twin, create_adt_relationship
    
    namespace = "dtmi:com:twin2clouds"
    
    # Get twin instances from hierarchy
    twins = hierarchy.get("twins", [])
    
    for twin in twins:
        twin_id = twin.get("id")
        twin_type = twin.get("type")
        properties = twin.get("properties", {})
        
        if twin_id and twin_type:
            model_id = f"{namespace}:{twin_type};1"
            create_adt_twin(provider, twin_id, model_id, properties)
    
    # Create relationships
    relationships = hierarchy.get("relationships", [])
    for rel in relationships:
        source = rel.get("source")
        target = rel.get("target")
        name = rel.get("name", "contains")
        
        if source and target:
            create_adt_relationship(provider, source, target, name)


def _setup_event_grid_subscription(
    context: 'DeploymentContext',
    provider: 'AzureProvider'
) -> None:
    """
    Set up Event Grid subscription from IoT Hub to ADT Updater.
    
    This is only needed for single-cloud deployments where IoT Hub
    and ADT are both on Azure.
    
    Args:
        context: Deployment context
        provider: Azure Provider instance
    """
    from .layer_4_adt import create_adt_event_grid_subscription
    
    # Check if this is single-cloud (L1 and L4 both Azure)
    l1_provider = context.config.providers["layer_1_provider"]
    l4_provider = context.config.providers["layer_4_provider"]
    
    if l1_provider != "azure" or l4_provider != "azure":
        logger.info("[L4] Multi-cloud configuration: Skipping Event Grid subscription")
        logger.info("[L4] (ADT Pusher in L0 will handle remote data)")
        return
    
    logger.info("[L4] Single-cloud configuration: Creating Event Grid subscription")
    create_adt_event_grid_subscription(provider, context.config)
    logger.info("[L4] ✓ Event Grid subscription created")


def destroy_l4(context: 'DeploymentContext', provider: 'AzureProvider') -> None:
    """
    Destroy Layer 4 Twin Management components.
    
    Destroys in reverse order of creation.
    
    Args:
        context: Deployment context
        provider: Initialized AzureProvider instance
    """
    from .layer_4_adt import (
        destroy_l4_function_app,
        destroy_l4_app_service_plan,
        destroy_adt_instance,
        destroy_adt_event_grid_subscription,
    )
    
    logger.info(f"[L4] Destroying Layer 4 Twin Management for {context.config.digital_twin_name}")
    context.set_active_layer("4")
    
    # Destroy in reverse order
    # 1. Event Grid subscription (only exists for single-cloud)
    l1_provider = context.config.providers["layer_1_provider"]
    l4_provider = context.config.providers["layer_4_provider"]
    if l1_provider == "azure" and l4_provider == "azure":
        destroy_adt_event_grid_subscription(provider)
    
    # 2. L4 Function App
    destroy_l4_function_app(provider)
    
    # 3. L4 App Service Plan
    destroy_l4_app_service_plan(provider)
    
    # 4. ADT Instance (includes all models, twins, relationships)
    destroy_adt_instance(provider)
    
    logger.info(f"[L4] Layer 4 Twin Management destruction complete")


def info_l4(context: 'DeploymentContext', provider: 'AzureProvider') -> dict:
    """
    Check status of Layer 4 (Twin Management) components.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of all L4 components
    """
    from .layer_4_adt import (
        check_adt_instance,
        check_l4_app_service_plan,
        check_l4_function_app,
        get_adt_instance_url,
    )
    
    logger.info(f"[L4] Checking Layer 4 components for {context.config.digital_twin_name}")
    
    status = {
        "layer": "4",
        "provider": "azure",
        "components": {
            "adt_instance": {
                "exists": check_adt_instance(provider),
                "url": get_adt_instance_url(provider)
            },
            "l4_app_service_plan": {
                "exists": check_l4_app_service_plan(provider)
            },
            "l4_function_app": {
                "exists": check_l4_function_app(provider)
            }
        }
    }
    
    return status
