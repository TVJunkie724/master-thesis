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

def _sanitize_for_dtmi(name: str) -> str:
    """
    Sanitize a name for use in DTMI identifiers.
    
    DTMI path segments must be: letters, digits, underscores only.
    Cannot start with digit, cannot end with underscore.
    
    Args:
        name: The name to sanitize (e.g., twin_name, node_id, device_id)
        
    Returns:
        DTMI-safe string with hyphens replaced by underscores
    """
    return name.replace("-", "_")


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
    adt_name = provider.naming.digital_twins_instance()
    
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

def upload_dtdl_models(provider: 'AzureProvider', config, project_path: str) -> None:
    """
    Upload DTDL models, twins, and relationships from azure_hierarchy.json.
    
    This function is called by azure_deployer.py after Terraform creates
    the ADT instance. It uses pre-structured DTDL from the hierarchy file.
    
    Args:
        provider: Initialized AzureProvider with clients and naming
        config: Project configuration with hierarchy containing models/twins/relationships
        project_path: Path to project directory (unused, kept for API consistency)
        
    Raises:
        ValueError: If provider or config is None, or hierarchy is not a dict
        ClientAuthenticationError: If permission denied
        HttpResponseError: If model upload fails
    """
    # PRESERVED: Validation
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    hierarchy = config.hierarchy
    if not isinstance(hierarchy, dict):
        raise ValueError("Azure hierarchy must be dict with 'models', 'twins', 'relationships'")
    
    # PRESERVED: Client fallback
    client = _get_adt_data_client(provider)
    if not client:
        logger.warning("ADT instance not accessible, skipping DTDL upload")
        return
    
    # Step 1: Upload models (already valid DTDL v3 from azure_hierarchy.json)
    models = hierarchy.get("models", [])
    if models:
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
    else:
        logger.info("No DTDL models to upload (empty hierarchy)")
        return
    
    # Step 2: Create twins from hierarchy (use pre-defined $dtId and $metadata.$model)
    twins = hierarchy.get("twins", [])
    if twins:
        logger.info(f"Creating {len(twins)} Digital Twins...")
        for twin in twins:
            twin_id = twin.get("$dtId", "unknown")
            try:
                client.upsert_digital_twin(twin_id, twin)
                logger.info(f"  ✓ Twin: {twin_id}")
            except HttpResponseError as e:
                logger.warning(f"  ✗ Could not create twin {twin_id}: {e.message}")
            except AzureError as e:
                logger.warning(f"  ✗ Could not create twin {twin_id}: {e}")
    
    # Step 3: Create relationships from hierarchy
    relationships = hierarchy.get("relationships", [])
    if relationships:
        logger.info(f"Creating {len(relationships)} relationships...")
        for rel in relationships:
            source_id = rel.get("$dtId", "unknown")
            rel_id = rel.get("$relationshipId", "unknown")
            try:
                client.upsert_relationship(
                    source_id, rel_id,
                    {
                        "$targetId": rel.get("$targetId"),
                        "$relationshipName": rel.get("$relationshipName")
                    }
                )
                logger.info(f"  ✓ Relationship: {rel_id}")
            except HttpResponseError as e:
                logger.warning(f"  ✗ Could not create relationship {rel_id}: {e.message}")
            except AzureError as e:
                logger.warning(f"  ✗ Could not create relationship {rel_id}: {e}")
    
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
    
    logger.info(f"[L4] Checking SDK-managed resources for {config.digital_twin_name}")
    
    adt_url = get_adt_instance_url(provider)
    
    status = {
        "layer": "4",
        "provider": "azure",
        "adt_url": adt_url,
        "models": {},
        "twins": {}
    }
    
    if adt_url:
        hierarchy = config.hierarchy
        if isinstance(hierarchy, dict):
            # Check models from hierarchy
            for model in hierarchy.get("models", []):
                model_id = model.get("@id", "unknown")
                status["models"][model_id] = check_model(model_id, provider)
            
            # Check twins from hierarchy
            for twin in hierarchy.get("twins", []):
                twin_id = twin.get("$dtId", "unknown")
                status["twins"][twin_id] = check_twin(twin_id, provider)
    
    return status

