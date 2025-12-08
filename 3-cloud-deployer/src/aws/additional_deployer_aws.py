"""
AWS Additional Deployer - TwinMaker Hierarchy Management.

This module handles TwinMaker entity hierarchy creation and destruction.

Migration Status:
    - Supports both legacy (globals-based) and new (provider-based) calling patterns.
    - Provider parameter is optional for backward compatibility.
"""

import warnings
import time
from typing import TYPE_CHECKING, Optional
from logger import logger
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider


def _get_provider_and_config():
    """Get provider and config from globals for legacy compatibility."""
    import globals
    import aws.globals_aws as globals_aws
    
    # Return a dict with the clients and config needed
    return {
        "twinmaker_client": globals_aws.aws_twinmaker_client,
        "workspace_name": globals_aws.twinmaker_workspace_name(),
        "hierarchy": globals.config_hierarchy,
        "digital_twin_name": globals.config.get("digital_twin_name", ""),
    }


def create_twinmaker_hierarchy(provider: Optional['AWSProvider'] = None, hierarchy: list = None) -> None:
    """Create TwinMaker entity hierarchy.
    
    Args:
        provider: Optional AWSProvider instance. If None, uses globals.
        hierarchy: Optional hierarchy config. If None, reads from globals.
    """
    import util
    
    if hierarchy is None:
        import globals
        hierarchy = globals.config_hierarchy
    
    for entity in hierarchy:
        if provider:
            # New pattern - would need util_aws migration too
            import aws.util_aws as util_aws
            util_aws.create_twinmaker_entity(entity)
        else:
            util.create_twinmaker_entity(entity)


def destroy_twinmaker_hierarchy(provider: Optional['AWSProvider'] = None, hierarchy: list = None) -> None:
    """Destroy TwinMaker entity hierarchy.
    
    Args:
        provider: Optional AWSProvider instance. If None, uses globals.
        hierarchy: Optional hierarchy config. If None, reads from globals.
    """
    if provider:
        twinmaker_client = provider.clients["twinmaker"]
        workspace_name = provider.naming.twinmaker_workspace()
    else:
        ctx = _get_provider_and_config()
        twinmaker_client = ctx["twinmaker_client"]
        workspace_name = ctx["workspace_name"]
    
    if hierarchy is None:
        import globals
        hierarchy = globals.config_hierarchy
    
    deleting_entities = []
    
    for entity in hierarchy:
        try:
            twinmaker_client.delete_entity(
                workspaceId=workspace_name,
                entityId=entity["id"],
                isRecursive=True
            )
            deleting_entities.append(entity)
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
    
    # Wait for deletion to complete
    for entity in deleting_entities:
        while True:
            try:
                twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["id"])
                time.sleep(2)
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    break
                else:
                    raise
        
        logger.info(f"Deleted IoT TwinMaker Entity: {entity['id']}")


def info_twinmaker_hierarchy(
    provider: Optional['AWSProvider'] = None,
    hierarchy: list = None,
    parent: dict = None
) -> None:
    """Print status of TwinMaker entity hierarchy.
    
    Args:
        provider: Optional AWSProvider instance. If None, uses globals.
        hierarchy: Optional hierarchy config. If None, reads from globals.  
        parent: Parent entity info for nested calls.
    """
    import util
    
    if provider:
        twinmaker_client = provider.clients["twinmaker"]
        workspace_name = provider.naming.twinmaker_workspace()
        digital_twin_name = provider.naming.twin_name
    else:
        ctx = _get_provider_and_config()
        twinmaker_client = ctx["twinmaker_client"]
        workspace_name = ctx["workspace_name"]
        digital_twin_name = ctx["digital_twin_name"]
    
    if hierarchy is None:
        import globals
        hierarchy = globals.config_hierarchy
    
    for entry in hierarchy:
        if entry["type"] == "entity":
            try:
                response = twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entry["id"])
                logger.info(f"✅ IoT TwinMaker Entity exists: {util.link_to_twinmaker_entity(workspace_name, entry['id'])}")
                
                if parent is not None and parent.get("entityId") != response.get("parentEntityId"):
                    logger.info(f"❌ IoT TwinMaker Entity {entry['id']} is missing parent: {parent.get('entityId')}")
                
                if "children" in entry:
                    info_twinmaker_hierarchy(provider, entry["children"], response)
                    
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.info(f"❌ IoT TwinMaker Entity missing: {entry['id']}")
                else:
                    raise
        
        elif entry["type"] == "component":
            if parent is None:
                continue
            
            if entry["name"] not in parent.get("components", {}):
                logger.info(f"❌ IoT TwinMaker Entity {parent.get('entityId')} is missing component: {entry['name']}")
                continue
            
            logger.info(f"✅ IoT TwinMaker Component exists: {util.link_to_twinmaker_component(workspace_name, parent.get('entityId'), entry['name'])}")
            
            component_info = parent["components"][entry["name"]]
            
            if "componentTypeId" in entry:
                entry_component_type_id = entry["componentTypeId"]
            else:
                entry_component_type_id = f"{digital_twin_name}-{entry['iotDeviceId']}"
            
            if component_info["componentTypeId"] != entry_component_type_id:
                logger.info(f"❌ IoT TwinMaker Component {entry['name']} has the wrong component type: {component_info['componentTypeId']} (expected: {entry_component_type_id})")
