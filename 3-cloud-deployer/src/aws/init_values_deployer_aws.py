"""
AWS Init Values Deployer - Posts Initial Values to IoT Core.

This module handles posting initial property values to IoT Core for devices
that have initValue defined in their configuration.

Migration Status:
    - Supports both legacy (globals-based) and new (provider-based) calling patterns.
"""

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from logger import logger

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider


def _get_legacy_context():
    """Get clients and config from globals for legacy compatibility."""
    import globals
    import aws.globals_aws as globals_aws
    
    return {
        "iot_data_client": globals_aws.aws_iot_data_client,
        "topic": globals.config["digital_twin_name"] + "/iot-data",
        "iot_devices": globals.config_iot_devices,
    }


def post_init_values_to_iot_core(
    provider: Optional['AWSProvider'] = None,
    iot_devices: list = None,
    topic: str = None
) -> None:
    """Post initial values to IoT Core for all configured devices.
    
    Args:
        provider: Optional AWSProvider. If None, uses globals.
        iot_devices: List of IoT device configs. If None, reads from globals.
        topic: IoT topic to publish to. If None, reads from globals.
    """
    if provider:
        iot_data_client = provider.clients["iot_data"]
        if topic is None:
            topic = f"{provider.naming.twin_name}/iot-data"
    else:
        ctx = _get_legacy_context()
        iot_data_client = ctx["iot_data_client"]
        topic = ctx["topic"]
    
    if iot_devices is None:
        import globals
        iot_devices = globals.config_iot_devices
    
    for iot_device in iot_devices:
        # Check for initValue in properties
        has_init = any("initValue" in prop for prop in iot_device.get("properties", []))
        if not has_init:
            continue
        
        payload = {
            "iotDeviceId": iot_device["id"],
            "time": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        }
        
        for prop in iot_device.get("properties", []):
            payload[prop["name"]] = prop.get("initValue", None)
        
        iot_data_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload).encode("utf-8")
        )
        logger.info(f"Posted init values for IoT device id: {iot_device['id']}")


def deploy(provider: Optional['AWSProvider'] = None, **kwargs) -> None:
    """Deploy initial values."""
    post_init_values_to_iot_core(provider, **kwargs)


def destroy(provider: Optional['AWSProvider'] = None) -> None:
    """No-op for destroy - init values are transient."""
    pass


def info(provider: Optional['AWSProvider'] = None) -> None:
    """No-op for info - init values are transient."""
    pass
