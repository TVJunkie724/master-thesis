#!/usr/bin/env python3
"""
Register IoT device and send test message.

Usage:
    python send_azure_iot_test_message.py
"""
import sys
import os
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))


def main():
    """Register device if needed and send test message."""
    from azure.identity import ClientSecretCredential
    from azure.mgmt.iothub import IotHubClient
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.device import IoTHubDeviceClient, Message
    
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
    
    # Configuration
    iothub_name = "tf-e2e-az-iothub"
    device_id = "pressure-sensor-1"
    resource_group = "tf-e2e-az-rg"
    
    print(f"[IOT] IoT Hub: {iothub_name}")
    print(f"[IOT] Device ID: {device_id}")
    
    # Get IoT Hub connection string
    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    iothub_client = IotHubClient(credential, subscription_id)
    
    keys = iothub_client.iot_hub_resource.list_keys(resource_group, iothub_name)
    hub_conn_string = None
    for key in keys:
        if key.key_name == "iothubowner":
            hub_conn_string = f"HostName={iothub_name}.azure-devices.net;SharedAccessKeyName={key.key_name};SharedAccessKey={key.primary_key}"
            break
    
    if not hub_conn_string:
        print("[ERROR] Could not get IoT Hub connection string")
        return
    
    print(f"[IOT] Got IoT Hub connection string")
    
    # Get or create device
    registry_manager = IoTHubRegistryManager(hub_conn_string)
    
    try:
        device = registry_manager.get_device(device_id)
        print(f"[IOT] Device '{device_id}' exists")
    except Exception:
        print(f"[IOT] Creating device '{device_id}'...")
        from azure.iot.hub.models import Device
        device = Device(device_id=device_id)
        device = registry_manager.create_device_with_sas(device_id, "", "", "")
        print(f"[IOT] Device created")
    
    # Get device connection string
    device = registry_manager.get_device(device_id)
    device_conn_string = f"HostName={iothub_name}.azure-devices.net;DeviceId={device_id};SharedAccessKey={device.authentication.symmetric_key.primary_key}"
    
    print(f"[IOT] Device connection string obtained")
    
    # Send test message
    print(f"\n[IOT] Connecting to IoT Hub...")
    device_client = IoTHubDeviceClient.create_from_connection_string(device_conn_string)
    
    payload = {
        "iotDeviceId": device_id,
        "temperature": 42.5,
        "pressure": 1013.25,
        "humidity": 65.0,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    message = Message(json.dumps(payload))
    message.content_type = "application/json"
    message.content_encoding = "utf-8"
    
    print(f"[IOT] Sending message: {json.dumps(payload, indent=2)}")
    device_client.connect()
    device_client.send_message(message)
    device_client.disconnect()
    
    print("\n[IOT] ✓ Message sent successfully!")
    print("\n[IOT] Check Azure resources:")
    print("  1. IoT Hub -> Messages to cloud: Check 'Messages used today'")
    print("  2. Function App tf-e2e-az-l1-functions -> dispatcher -> Monitor")
    print("  3. Cosmos DB -> Data Explorer -> hot-storage -> Items")


if __name__ == "__main__":
    main()
