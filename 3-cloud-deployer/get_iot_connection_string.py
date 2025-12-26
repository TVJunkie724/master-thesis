#!/usr/bin/env python3
"""
Get IoT device connection string from Azure IoT Hub.

Usage:
    python get_iot_connection_string.py <iothub_name> <device_id>
"""
import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))


def get_connection_string(iothub_name: str, device_id: str):
    """Get device connection string from IoT Hub using Azure SDK."""
    from azure.identity import ClientSecretCredential
    from azure.mgmt.iothub import IotHubClient
    from azure.mgmt.iothub.models import IotHubSkuInfo
    
    # Load credentials
    project_path = Path(__file__).parent / "upload" / "template"
    credentials_file = project_path / "config_credentials.json"
    
    with open(credentials_file) as f:
        creds = json.load(f)
    
    azure_creds = creds.get("azure", {})
    subscription_id = azure_creds.get("azure_subscription_id")
    tenant_id = azure_creds.get("azure_tenant_id")
    client_id = azure_creds.get("azure_client_id")
    client_secret = azure_creds.get("azure_client_secret")
    
    # Get IoT Hub keys using management API
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    
    iothub_client = IotHubClient(credential, subscription_id)
    
    # Get the iothubowner key
    resource_group = f"{iothub_name.replace('-iothub', '')}-rg"
    
    try:
        keys = iothub_client.iot_hub_resource.list_keys(resource_group, iothub_name)
        for key in keys:
            if key.key_name == "iothubowner":
                hub_connection_string = f"HostName={iothub_name}.azure-devices.net;SharedAccessKeyName={key.key_name};SharedAccessKey={key.primary_key}"
                print(f"IoT Hub connection: {iothub_name}.azure-devices.net")
                
                # Now get device connection string using IoT Hub service SDK
                from azure.iot.hub import IoTHubRegistryManager
                registry_manager = IoTHubRegistryManager(hub_connection_string)
                
                device = registry_manager.get_device(device_id)
                device_conn_string = f"HostName={iothub_name}.azure-devices.net;DeviceId={device_id};SharedAccessKey={device.authentication.symmetric_key.primary_key}"
                
                print(f"\nDevice: {device_id}")
                print(f"\nConnection String:")
                print(device_conn_string)
                return device_conn_string
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python get_iot_connection_string.py <iothub_name> <device_id>")
        print("Example: python get_iot_connection_string.py tf-e2e-az-iothub pressure-sensor-1")
        sys.exit(1)
    
    get_connection_string(sys.argv[1], sys.argv[2])
