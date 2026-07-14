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
import time

from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)


# ==========================================
# Helper Functions
# ==========================================

def _wait_for_iothub_active(provider: 'AzureProvider', timeout: int = 180, poll_interval: int = 10) -> None:
    """
    Wait for IoT Hub to reach Active state.
    
    Azure IoT Hub can take 1-2 minutes to transition from Creating to Active.
    Terraform returns as soon as the resource is created, but SDK operations
    (like list_keys) require the hub to be Active.
    
    Args:
        provider: Initialized AzureProvider
        timeout: Maximum seconds to wait (default 180 = 3 minutes)
        poll_interval: Seconds between status checks (default 10)
        
    Raises:
        TimeoutError: If IoT Hub doesn't reach Active state within timeout
    """
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    
    start_time = time.time()
    
    while True:
        try:
            hub = provider.clients["iothub"].iot_hub_resource.get(
                resource_group_name=rg_name,
                resource_name=hub_name
            )
            
            state = hub.properties.state if hub.properties else None
            
            if state == "Active":
                logger.info(f"✓ IoT Hub {hub_name} is Active")
                return
            
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"IoT Hub {hub_name} did not reach Active state within {timeout}s. "
                    f"Current state: {state}"
                )
            
            logger.info(f"  Waiting for IoT Hub {hub_name} to become Active (current: {state}, {int(elapsed)}s elapsed)...")
            time.sleep(poll_interval)
            
        except ResourceNotFoundError:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"IoT Hub {hub_name} not found within {timeout}s")
            logger.info(f"  Waiting for IoT Hub {hub_name} to be created...")
            time.sleep(poll_interval)


def _get_iot_hub_connection_string(provider: 'AzureProvider') -> str:
    """Get the IoT Hub connection string for management operations."""
    rg_name = provider.naming.resource_group()
    hub_name = provider.naming.iot_hub()
    
    # Wait for IoT Hub to reach Active state before querying keys
    # This fixes race condition where Terraform returns before hub is fully ready
    _wait_for_iothub_active(provider)
    
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


def _is_not_found_error(exception: Exception) -> bool:
    """Check if exception indicates a 404/NotFound error."""
    error_str = str(exception).lower()
    return "not found" in error_str or "devicenotfound" in error_str or "404" in error_str


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
        if _is_not_found_error(e):
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
            if _is_not_found_error(e):
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
        "payload_path": "../payloads.json",
        "credential_class": "azure_iot_hub_device_identity",
        "credential_contract_version": 1,
    }
    
    # Write to upload/{project}/iot_device_simulator/azure/{device_id}/
    project_dir = Path(project_path)
    sim_dir = project_dir / "iot_device_simulator" / "azure" / device_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    config_path = sim_dir / "config_generated.json"
    
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    config_path.chmod(0o600)
    
    logger.info(f"  ✓ Generated simulator config: {config_path}")
