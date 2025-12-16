"""
AWS Utility Functions.

This module provides utility functions for AWS operations including:
- Console link generation for resources

Note:
    Most AWS operations are now handled by Terraform.
    This file contains runtime utilities used by layer files.
"""


# ==========================================
# Console Link Functions
# ==========================================

def link_to_iot_thing(thing_name, region: str = None):
    """Generate AWS Console link to an IoT Thing."""
    region = region or "eu-central-1"
    return f"https://{region}.console.aws.amazon.com/iot/home?region={region}#/thing/{thing_name}"
