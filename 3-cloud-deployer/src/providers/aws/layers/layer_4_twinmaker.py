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
    This checks TwinMaker entities created via SDK.
    """
    logger.info(f"[L4] Checking SDK-managed resources for {context.config.digital_twin_name}")
    
    entities_status = {}
    if context.config.iot_devices:
        for device in context.config.iot_devices:
            entity_id = device.get('id', device.get('name', 'unknown'))
            entities_status[entity_id] = check_twinmaker_entity(entity_id, provider)
    
    return {
        "layer": "4",
        "provider": "aws",
        "entities": entities_status
    }
