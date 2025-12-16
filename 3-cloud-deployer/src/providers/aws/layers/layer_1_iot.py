"""
Layer 1 (IoT) SDK-Managed Resources for AWS.

This module provides SDK-managed resource checks for Layer 1.

Note:
    Infrastructure checks (IAM roles, Lambda functions, IoT Rules) are 
    handled by Terraform state list. This file only checks SDK-managed
    dynamic resources like IoT Things (device registrations).
"""

from typing import TYPE_CHECKING
from logger import logger
from botocore.exceptions import ClientError

import src.providers.aws.util_aws as util_aws

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import DeploymentContext


def _links():
    return util_aws


# ==========================================
# SDK-Managed Resource Checks
# ==========================================

def check_iot_thing(iot_device, provider: 'AWSProvider') -> bool:
    """Check if IoT Thing (device) is registered."""
    thing_name = provider.naming.iot_thing(iot_device.get('name', 'unknown'))
    client = provider.clients["iot"]

    try:
        client.describe_thing(thingName=thing_name)
        logger.info(f"✅ IoT Thing {thing_name} exists: {_links().link_to_iot_thing(thing_name, region=provider.region)}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ IoT Thing {thing_name} missing")
            return False
        else:
            raise


def info_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> dict:
    """
    Check status of SDK-managed L1 resources.
    
    Note: Infrastructure (IAM, Lambda, IoT Rules) is checked via Terraform state.
    This only checks IoT Things (device registrations).
    """
    logger.info(f"[L1] Checking SDK-managed resources for {context.config.digital_twin_name}")
    
    devices_status = {}
    if context.config.iot_devices:
        for device in context.config.iot_devices:
            device_id = device.get('id', device.get('name', 'unknown'))
            devices_status[device_id] = check_iot_thing(device, provider)
    
    return {
        "layer": "1",
        "provider": "aws",
        "devices": devices_status
    }
