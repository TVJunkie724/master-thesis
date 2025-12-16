"""
Layer 4 (Azure Digital Twins) SDK Operations for Azure.

This module provides:
1. Post-Terraform SDK operations (DTDL model upload, twin creation)
2. SDK-managed resource checks (twins, relationships)

Components Managed:
- DTDL Models: Digital Twin Definition Language model schemas
- Digital Twins: Individual twin instances representing IoT devices
- Relationships: Connections between twins in the hierarchy

Architecture:
    config_hierarchy.json → DTDL Models → Digital Twins → Relationships
         │                      │              │             │
         │                      │              │             └── Parent-child links
         │                      │              └── One per IoT device
         │                      └── Interface definitions
         └── Hierarchy config from project

Note:
    Infrastructure (ADT instance, Function App, App Service Plan) is 
    handled by Terraform. This file handles SDK-managed dynamic resources.
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any
import logging
import json

from azure.core.exceptions import (
    ResourceNotFoundError,
    ClientAuthenticationError,
    HttpResponseError,
    AzureError
)

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def get_adt_instance_url(provider: 'AzureProvider') -> Optional[str]:
    """
    Get the Azure Digital Twins instance endpoint URL.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        The ADT instance URL (https://...) or None if not found
        
    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    adt_name = provider.naming.adt_instance()
    
    try:
        instance = provider.clients["digitaltwins"].digital_twins.get(
            resource_group_name=rg_name,
            resource_name=adt_name
        )
        return f"https://{instance.host_name}"
    except ResourceNotFoundError:
        logger.info(f"✗ ADT instance not found: {adt_name}")
        return None
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED getting ADT instance: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error getting ADT instance: {type(e).__name__}: {e}")
        raise


def _get_adt_data_client(provider: 'AzureProvider'):
    """
    Get the DigitalTwinsClient for data plane operations.
    
    Args:
        provider: Initialized AzureProvider
        
    Returns:
        DigitalTwinsClient or None if ADT instance not found
        
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    
    adt_url = get_adt_instance_url(provider)
    if not adt_url:
        return None
    
    credential = DefaultAzureCredential()
    return DigitalTwinsClient(adt_url, credential)


# ==========================================
# SDK-Managed Resource Checks
# ==========================================

def check_twin(twin_id: str, provider: 'AzureProvider') -> bool:
    """
    Check if a Digital Twin exists in Azure Digital Twins.
    
    Args:
        twin_id: ID of the twin to check
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if twin exists, False otherwise. Never raises for not found.
        
    Raises:
        ValueError: If twin_id or provider is None
        ClientAuthenticationError: If permission denied
    """
    if twin_id is None:
        raise ValueError("twin_id is required")
    if provider is None:
        raise ValueError("provider is required")
    
    client = _get_adt_data_client(provider)
    if not client:
        logger.info(f"✗ ADT instance not accessible")
        return False
    
    try:
        client.get_digital_twin(twin_id)
        logger.info(f"✓ Digital Twin exists: {twin_id}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ Digital Twin not found: {twin_id}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking twin {twin_id}: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking twin {twin_id}: {type(e).__name__}: {e}")
        raise


def check_model(model_id: str, provider: 'AzureProvider') -> bool:
    """
    Check if a DTDL model exists in Azure Digital Twins.
    
    Args:
        model_id: DTDL model ID (e.g., dtmi:example:Room;1)
        provider: Initialized AzureProvider with clients and naming
        
    Returns:
        True if model exists, False otherwise. Never raises for not found.
        
    Raises:
        ValueError: If model_id or provider is None
        ClientAuthenticationError: If permission denied
    """
    if model_id is None:
        raise ValueError("model_id is required")
    if provider is None:
        raise ValueError("provider is required")
    
    client = _get_adt_data_client(provider)
    if not client:
        logger.info(f"✗ ADT instance not accessible")
        return False
    
    try:
        client.get_model(model_id)
        logger.info(f"✓ DTDL Model exists: {model_id}")
        return True
    except ResourceNotFoundError:
        logger.info(f"✗ DTDL Model not found: {model_id}")
        return False
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED checking model {model_id}: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error checking model {model_id}: {type(e).__name__}: {e}")
        raise


# ==========================================
# Post-Terraform SDK Operations
# ==========================================

def _convert_hierarchy_to_dtdl(hierarchy: dict, twin_name: str) -> List[Dict[str, Any]]:
    """
    Convert config_hierarchy.json to DTDL model definitions.
    
    Creates DTDL Interface models from the project hierarchy config.
    Each node in the hierarchy becomes a model with a parent relationship.
    
    Args:
        hierarchy: Hierarchy config dict from config_hierarchy.json
        twin_name: Digital twin name for model ID prefixes
        
    Returns:
        List of DTDL model definitions ready for upload
    """
    models = []
    
    # Create a base model for all entities
    base_model = {
        "@id": f"dtmi:{twin_name}:BaseEntity;1",
        "@type": "Interface",
        "displayName": "Base Entity",
        "@context": "dtmi:dtdl:context;2",
        "contents": [
            {
                "@type": "Property",
                "name": "name",
                "schema": "string"
            },
            {
                "@type": "Property",
                "name": "description",
                "schema": "string"
            }
        ]
    }
    models.append(base_model)
    
    def process_node(node: dict, parent_id: Optional[str] = None):
        """Recursively process hierarchy nodes into DTDL models."""
        node_id = node.get("id", "unknown")
        model_id = f"dtmi:{twin_name}:{node_id};1"
        
        model = {
            "@id": model_id,
            "@type": "Interface",
            "displayName": node.get("name", node_id),
            "@context": "dtmi:dtdl:context;2",
            "extends": f"dtmi:{twin_name}:BaseEntity;1",
            "contents": []
        }
        
        # Add relationship to parent if exists
        if parent_id:
            model["contents"].append({
                "@type": "Relationship",
                "name": "isPartOf",
                "target": parent_id
            })
        
        models.append(model)
        
        # Process children recursively
        for child in node.get("children", []):
            process_node(child, model_id)
        
        # Process devices as leaf nodes with telemetry
        for device in node.get("devices", []):
            device_id = device.get("id", "unknown")
            device_model_id = f"dtmi:{twin_name}:{device_id};1"
            
            device_model = {
                "@id": device_model_id,
                "@type": "Interface",
                "displayName": device.get("name", device_id),
                "@context": "dtmi:dtdl:context;2",
                "extends": f"dtmi:{twin_name}:BaseEntity;1",
                "contents": [
                    {
                        "@type": "Relationship",
                        "name": "isPartOf",
                        "target": model_id
                    },
                    {
                        "@type": "Telemetry",
                        "name": "telemetry",
                        "schema": "double"
                    }
                ]
            }
            models.append(device_model)
    
    # Process root node if hierarchy exists
    if hierarchy:
        process_node(hierarchy)
    
    return models


def upload_dtdl_models(provider: 'AzureProvider', config, project_path: str) -> None:
    """
    Upload DTDL models and create Digital Twins (post-Terraform).
    
    This function is called by Terraform azure_deployer.py after
    infrastructure is created. It performs three operations:
    1. Converts hierarchy config to DTDL model definitions
    2. Uploads DTDL models to Azure Digital Twins
    3. Creates Digital Twin instances for each IoT device
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration with hierarchy and iot_devices
        project_path: Path to project directory (unused, kept for API consistency)
        
    Raises:
        ValueError: If provider or config is None
        ClientAuthenticationError: If permission denied
        HttpResponseError: If model upload fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    client = _get_adt_data_client(provider)
    if not client:
        logger.warning("ADT instance not accessible, skipping DTDL upload")
        return
    
    twin_name = config.digital_twin_name
    
    # Step 1: Convert hierarchy to DTDL models
    hierarchy = config.hierarchy or {}
    models = _convert_hierarchy_to_dtdl(hierarchy, twin_name)
    
    if not models:
        logger.info("No DTDL models to upload (empty hierarchy)")
        return
    
    # Step 2: Upload models to ADT
    logger.info(f"Uploading {len(models)} DTDL models...")
    
    try:
        created_models = client.create_models(models)
        model_count = len(list(created_models))
        logger.info(f"✓ Uploaded {model_count} DTDL models")
    except HttpResponseError as e:
        if "already exists" in str(e).lower() or "ModelIdAlreadyExists" in str(e):
            logger.info("✓ DTDL models already exist (skipping)")
        else:
            logger.error(f"HTTP error uploading DTDL models: {e.status_code} - {e.message}")
            raise
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED uploading DTDL models: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error uploading DTDL models: {type(e).__name__}: {e}")
        raise
    
    # Step 3: Create twins from IoT devices
    if config.iot_devices:
        logger.info(f"Creating {len(config.iot_devices)} Digital Twins...")
        for device in config.iot_devices:
            device_id = device.get("id", device.get("name", "unknown"))
            model_id = f"dtmi:{twin_name}:{device_id};1"
            
            try:
                twin = {
                    "$metadata": {"$model": model_id},
                    "name": device.get("name", device_id),
                    "description": f"Digital Twin for IoT device {device_id}"
                }
                client.upsert_digital_twin(device_id, twin)
                logger.info(f"  ✓ Digital Twin created/updated: {device_id}")
            except HttpResponseError as e:
                logger.warning(f"  ✗ Could not create twin {device_id}: {e.message}")
            except AzureError as e:
                logger.warning(f"  ✗ Could not create twin {device_id}: {e}")
    
    logger.info("✓ DTDL model upload complete")


# ==========================================
# Status Check Function (Used by API)
# ==========================================

def info_l4(context, provider: 'AzureProvider') -> Dict[str, Any]:
    """
    Check status of Layer 4 SDK-managed resources.
    
    Checks DTDL models and Digital Twins created via SDK after Terraform deployment.
    
    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider instance
        
    Returns:
        Dictionary with status of SDK-managed L4 resources
        
    Raises:
        ValueError: If context or provider is None
    """
    if context is None:
        raise ValueError("context is required")
    if provider is None:
        raise ValueError("provider is required")
    
    config = context.config if hasattr(context, 'config') else context
    twin_name = config.digital_twin_name
    
    logger.info(f"[L4] Checking SDK-managed resources for {twin_name}")
    
    adt_url = get_adt_instance_url(provider)
    
    status = {
        "layer": "4",
        "provider": "azure",
        "adt_url": adt_url,
        "models": {},
        "twins": {}
    }
    
    if adt_url:
        # Check base model
        base_model_id = f"dtmi:{twin_name}:BaseEntity;1"
        status["models"][base_model_id] = check_model(base_model_id, provider)
        
        # Check twins for each IoT device
        if config.iot_devices:
            for device in config.iot_devices:
                device_id = device.get("id", device.get("name", "unknown"))
                status["twins"][device_id] = check_twin(device_id, provider)
    
    return status

