"""
Layer 1 (IoT) SDK-Managed Resources for Azure.

This module provides:
1. SDK-managed resource checks (IoT device registrations)
2. Post-Terraform SDK operations (device registration)

Note:
    Infrastructure checks (IoT Hub, Function App, Event Grid) are 
    handled by Terraform state list. This file only handles SDK-managed
    dynamic resources.
"""

from typing import TYPE_CHECKING
import logging

from azure.core.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def _get_iot_hub_connection_string(provider: 'AzureProvider') -> str:
    """Get the IoT Hub connection string for management operations."""
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    
    try:
        keys = provider.clients["iothub"].iot_hub_resource.list_keys(
            resource_group_name=rg_name,
            resource_name=hub_name
        )
        
        for key in keys:
            if key.key_name == "iothubowner":
                return (
                    f"HostName={hub_name}.azure-devices.net;"
                    f"SharedAccessKeyName={key.key_name};"
                    f"SharedAccessKey={key.primary_key}"
                )
        
        raise RuntimeError("iothubowner key not found")
        
    except Exception as e:
        logger.error(f"Error getting IoT Hub connection string: {e}")
        raise


# ==========================================
# SDK-Managed Resource Checks
# ==========================================

def check_iot_device(iot_device: dict, provider: 'AzureProvider') -> bool:
    """
    Check if a device exists in IoT Hub.
    
    Args:
        iot_device: Device configuration dict with 'id'
        provider: Initialized AzureProvider
        
    Returns:
        True if device exists, False otherwise
    """
    if iot_device is None:
        raise ValueError("iot_device is required")
    if provider is None:
        raise ValueError("provider is required")
    
    device_id = provider.naming.iot_device(iot_device["id"])
    
    try:
        hub_conn_str = _get_iot_hub_connection_string(provider)
        
        from azure.iot.hub import IoTHubRegistryManager
        
        registry_manager = IoTHubRegistryManager(hub_conn_str)
        registry_manager.get_device(device_id=device_id)
        
        logger.info(f"✓ IoT device exists: {device_id}")
        return True
        
    except Exception as e:
        if "DeviceNotFound" in str(e):
            logger.info(f"✗ IoT device not found: {device_id}")
            return False
        else:
            logger.error(f"Error checking IoT device: {type(e).__name__}: {e}")
            raise


def info_l1(context, provider: 'AzureProvider') -> dict:
    """
    Check status of SDK-managed L1 resources.
    
    Note: Infrastructure (IoT Hub, Function App) is checked via Terraform state.
    This only checks IoT device registrations.
    """
    config = context.config if hasattr(context, 'config') else context
    
    logger.info(f"[L1] Checking SDK-managed resources for {config.digital_twin_name}")
    
    devices_status = {}
    if config.iot_devices:
        for device in config.iot_devices:
            device_id = device["id"]
            devices_status[device_id] = check_iot_device(device, provider)
    
    return {
        "layer": "1",
        "provider": "azure",
        "devices": devices_status
    }


# ==========================================
# Post-Terraform SDK Operations
# ==========================================

def register_iot_devices(provider: 'AzureProvider', config, project_path: str) -> None:
    """
    Register IoT devices in Azure IoT Hub (post-Terraform).
    
    This function is called by Terraform azure_deployer.py after
    infrastructure is created to register IoT devices via SDK.
    Also generates config_generated.json for the simulator.
    """
    import json
    import os
    from pathlib import Path
    
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    
    if not config.iot_devices:
        logger.info("No IoT devices configured")
        return
    
    hub_conn_str = _get_iot_hub_connection_string(provider)
    hub_name = provider.naming.iot_hub()
    
    from azure.iot.hub import IoTHubRegistryManager
    registry_manager = IoTHubRegistryManager(hub_conn_str)
    
    for device in config.iot_devices:
        device_id = provider.naming.iot_device(device["id"])
        
        try:
            # Try to get existing device
            existing_device = registry_manager.get_device(device_id=device_id)
            logger.info(f"✓ IoT device already exists: {device_id}")
            primary_key = existing_device.authentication.symmetric_key.primary_key
        except Exception as e:
            if "DeviceNotFound" in str(e):
                try:
                    # Create new device with auto-generated keys
                    new_device = registry_manager.create_device_with_sas(
                        device_id=device_id,
                        primary_key=None,
                        secondary_key=None,
                        status="enabled"
                    )
                    logger.info(f"✓ IoT device registered: {device_id}")
                    primary_key = new_device.authentication.symmetric_key.primary_key
                except Exception as create_e:
                    logger.error(f"Failed to register device {device_id}: {create_e}")
                    raise
            else:
                raise
        
        # Build device connection string
        device_conn_str = (
            f"HostName={hub_name}.azure-devices.net;"
            f"DeviceId={device_id};"
            f"SharedAccessKey={primary_key}"
        )
        
        # Generate simulator config
        _generate_azure_simulator_config(
            device, device_conn_str, config.digital_twin_name, project_path
        )


def _generate_azure_simulator_config(
    iot_device: dict,
    device_conn_str: str,
    digital_twin_name: str,
    project_path: str
) -> None:
    """
    Generate config_generated.json for the Azure IoT device simulator.
    
    Note: Unlike GCP which uses Terraform's local_file resource, Azure config
    generation MUST be done via SDK because the device_conn_str (connection
    string) is only available AFTER registering the device in IoT Hub. The
    connection string contains device-specific credentials created during
    registration and cannot be known at Terraform plan time.
    
    Args:
        iot_device: Device configuration dict
        device_conn_str: Device connection string from IoT Hub
        digital_twin_name: Name of the digital twin
        project_path: Path to project directory
    """
    import json
    import os
    from pathlib import Path
    
    device_id = iot_device["id"]
    
    config_data = {
        "connection_string": device_conn_str,
        "device_id": device_id,
        "digital_twin_name": digital_twin_name,
        "payload_path": "../payloads.json"
    }
    
    # Write to upload/{project}/iot_device_simulator/azure/
    project_dir = Path(project_path)
    sim_dir = project_dir / "iot_device_simulator" / "azure"
    sim_dir.mkdir(parents=True, exist_ok=True)
    config_path = sim_dir / "config_generated.json"
    
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    
    logger.info(f"  ✓ Generated simulator config: {config_path}")
