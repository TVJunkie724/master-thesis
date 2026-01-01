"""
Layer 4 (TwinMaker) SDK-Managed Resources for AWS.

This module provides SDK-managed resource checks for Layer 4.

Note:
    Infrastructure checks (IAM roles, S3 buckets, workspaces) are 
    handled by Terraform state list. This file only checks SDK-managed
    dynamic resources like TwinMaker entities.
"""

from typing import TYPE_CHECKING
from logger import logger
import src.providers.aws.util_aws as util_aws
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import DeploymentContext


def _links():
    return util_aws


# ==========================================
# SDK-Managed Resource Checks
# ==========================================

def check_twinmaker_entity(entity_id: str, provider: 'AWSProvider') -> bool:
    """Check if TwinMaker entity exists."""
    workspace_id = provider.naming.twinmaker_workspace()
    client = provider.clients["twinmaker"]

    try:
        client.get_entity(workspaceId=workspace_id, entityId=entity_id)
        logger.info(f"✅ TwinMaker Entity exists: {entity_id}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ TwinMaker Entity missing: {entity_id}")
            return False
        else:
            raise


def info_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> dict:
    """
    Check status of SDK-managed L4 resources.
    
    Note: Infrastructure (workspace, IAM, S3) is checked via Terraform state.
    This checks TwinMaker entities created via SDK from hierarchy.
    """
    logger.info(f"[L4] Checking SDK-managed resources for {context.config.digital_twin_name}")
    
    def get_entity_ids(nodes: list) -> list:
        """Recursively extract entity IDs from hierarchy."""
        ids = []
        for node in nodes:
            if node.get("type") == "entity":
                ids.append(node.get("id", "unknown"))
                ids.extend(get_entity_ids(node.get("children", [])))
        return ids
    
    entities_status = {}
    hierarchy = context.config.hierarchy
    if hierarchy and isinstance(hierarchy, list):
        for entity_id in get_entity_ids(hierarchy):
            entities_status[entity_id] = check_twinmaker_entity(entity_id, provider)
    
    return {
        "layer": "4",
        "provider": "aws",
        "entities": entities_status
    }


# ==========================================
# Force Delete (Cleanup when Terraform fails)
# ==========================================

def force_delete_twinmaker_workspace(provider: 'AWSProvider') -> dict:
    """
    Force delete TwinMaker workspace with all entities and component types.
    
    Use when Terraform destroy fails because the workspace contains resources.
    AWS requires deletion in this order: entities → component types → workspace.
    
    Args:
        provider: Initialized AWSProvider with clients
        
    Returns:
        Dictionary with deletion status and counts
        
    Raises:
        ClientError: If AWS API call fails
    """
    client = provider.clients["twinmaker"]
    workspace_id = provider.naming.twinmaker_workspace()
    
    result = {
        "workspace_id": workspace_id,
        "entities_deleted": 0,
        "component_types_deleted": 0,
        "status": "pending"
    }
    
    logger.info(f"[TwinMaker Force Delete] Starting deletion of workspace: {workspace_id}")
    
    # Step 1: Check if workspace exists
    try:
        client.get_workspace(workspaceId=workspace_id)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"  Workspace does not exist: {workspace_id}")
            result["status"] = "not_found"
            return result
        raise
    
    # Step 2: Delete all entities (recursive for hierarchical entities)
    logger.info("  [1/3] Deleting entities...")
    try:
        paginator = client.get_paginator('list_entities')
        for page in paginator.paginate(workspaceId=workspace_id):
            for entity in page.get('entitySummaries', []):
                entity_id = entity['entityId']
                try:
                    client.delete_entity(
                        workspaceId=workspace_id,
                        entityId=entity_id,
                        isRecursive=True
                    )
                    result["entities_deleted"] += 1
                    logger.info(f"    Deleted entity: {entity_id}")
                except ClientError as e:
                    # Entity might already be deleted if it was a child
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        logger.warning(f"    Failed to delete entity {entity_id}: {e}")
    except ClientError as e:
        logger.warning(f"  Error listing entities: {e}")
    
    # Step 3: Delete all component types (skip AWS built-ins)
    logger.info("  [2/3] Deleting component types...")
    try:
        paginator = client.get_paginator('list_component_types')
        for page in paginator.paginate(workspaceId=workspace_id):
            for ct in page.get('componentTypeSummaries', []):
                ct_id = ct['componentTypeId']
                # Skip AWS built-in component types
                if ct_id.startswith('com.amazon.'):
                    continue
                try:
                    client.delete_component_type(
                        workspaceId=workspace_id,
                        componentTypeId=ct_id
                    )
                    result["component_types_deleted"] += 1
                    logger.info(f"    Deleted component type: {ct_id}")
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        logger.warning(f"    Failed to delete component type {ct_id}: {e}")
    except ClientError as e:
        logger.warning(f"  Error listing component types: {e}")
    
    # Step 4: Delete workspace
    logger.info("  [3/3] Deleting workspace...")
    try:
        client.delete_workspace(workspaceId=workspace_id)
        result["status"] = "deleted"
        logger.info(f"  ✓ Workspace deleted: {workspace_id}")
    except ClientError as e:
        result["status"] = f"error: {e.response['Error']['Message']}"
        logger.error(f"  ✗ Failed to delete workspace: {e}")
    
    logger.info(f"[TwinMaker Force Delete] Complete. Entities: {result['entities_deleted']}, "
                f"Component Types: {result['component_types_deleted']}")
    
    return result

