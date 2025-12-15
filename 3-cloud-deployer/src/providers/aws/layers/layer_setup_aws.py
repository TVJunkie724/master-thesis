"""
AWS Setup Layer - Resource Grouping via Tags.

This module creates the foundational AWS Resource Group that logically
groups all digital twin resources based on tags.

Resources managed:
- AWS Resource Group: Query-based grouping of tagged resources

Unlike Azure where Resource Groups are containers, AWS Resource Groups
are views over resources that share common tags. We create the Resource
Group first, then all subsequent layer deployments tag their resources
with the `DigitalTwin` tag.

Deployment Order:
    1. Create Resource Group (tag-based query)

Note:
    The Resource Group uses a TAG_FILTERS query to find all resources
    with the tag DigitalTwin={twin_name}.
"""

from typing import TYPE_CHECKING
import logging

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider

logger = logging.getLogger(__name__)


# ==========================================
# Resource Group Management
# ==========================================

def create_resource_group(provider: 'AWSProvider') -> str:
    """
    Create an AWS Resource Group with a tag-based query.
    
    The Resource Group automatically includes all AWS resources that have
    the tag DigitalTwin={twin_name}. This provides a centralized view
    of all resources belonging to this digital twin.
    
    Args:
        provider: AWS Provider instance with initialized clients
    
    Returns:
        The Resource Group name
    
    Raises:
        ValueError: If provider is None
        ClientError: If creation fails (except for AlreadyExists)
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    twin_name = provider.naming.twin_name
    rg_client = provider.clients["resource-groups"]
    
    logger.info(f"Creating Resource Group: {rg_name}")
    
    try:
        # Create Resource Group with tag-based query
        rg_client.create_group(
            Name=rg_name,
            Description=f"All resources for digital twin: {twin_name}",
            ResourceQuery={
                "Type": "TAG_FILTERS_1_0",
                "Query": f'{{"ResourceTypeFilters":["AWS::AllSupported"],"TagFilters":[{{"Key":"DigitalTwin","Values":["{twin_name}"]}}]}}'
            },
            Tags=provider.naming.get_common_tags("Setup")
        )
        
        logger.info(f"✓ Resource Group created: {rg_name}")
        return rg_name
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "BadRequestException" and "already exists" in str(e):
            logger.info(f"✓ Resource Group already exists: {rg_name}")
            return rg_name
        logger.error(f"Failed to create Resource Group: {error_code} - {e}")
        raise


def destroy_resource_group(provider: 'AWSProvider') -> None:
    """
    Delete the AWS Resource Group.
    
    Note:
        Deleting the Resource Group does NOT delete the resources within it.
        Resources must be deleted separately via their respective layer destroy functions.
    
    Args:
        provider: AWS Provider instance
    
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    rg_client = provider.clients["resource-groups"]
    
    logger.info(f"Deleting Resource Group: {rg_name}")
    
    try:
        rg_client.delete_group(GroupName=rg_name)
        logger.info(f"✓ Resource Group deleted: {rg_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            logger.info(f"Resource Group already deleted: {rg_name}")
        else:
            raise


def check_resource_group(provider: 'AWSProvider') -> bool:
    """
    Check if the Resource Group exists.
    
    Args:
        provider: AWS Provider instance
    
    Returns:
        True if the Resource Group exists, False otherwise
    
    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")
    
    rg_name = provider.naming.resource_group()
    rg_client = provider.clients["resource-groups"]
    
    try:
        rg_client.get_group(GroupName=rg_name)
        logger.info(f"✓ Resource Group exists: {rg_name}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            logger.info(f"✗ Resource Group not found: {rg_name}")
            return False
        raise
