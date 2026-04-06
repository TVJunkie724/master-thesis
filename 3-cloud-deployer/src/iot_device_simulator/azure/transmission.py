"""
Azure IoT Device Simulator - MQTT Transmission.

This module handles communication with Azure IoT Hub,
sending test payloads using the azure-iot-device SDK.

Unlike AWS (which uses X.509 certificates), Azure uses connection strings
with SAS (Shared Access Signature) authentication.
"""

from . import globals
import json
import os
from datetime import datetime, timezone

# Lazy import to avoid issues in development environments without the SDK
IoTHubDeviceClient = None
Message = None

payload_index = 0


def load_config_for_device(device_id: str) -> dict:
    """
    Load device-specific config for standalone multi-device mode.
    
    In standalone mode, configs are stored in configs/{device_id}/config.json.
    Falls back to root config.json if device-specific config not found.
    """
    if not device_id:
        return dict(globals.config)
    
    device_config_path = f"configs/{device_id}/config.json"
    if os.path.exists(device_config_path):
        with open(device_config_path, 'r') as f:
            config_data = json.load(f)
        
        # Resolve paths relative to device config directory
        config_dir = os.path.dirname(device_config_path)
        def resolve(path):
            if os.path.isabs(path):
                return path
            return os.path.normpath(os.path.join(config_dir, path))
        
        return {
            "connection_string": config_data["connection_string"],
            "device_id": config_data["device_id"],
            "digital_twin_name": config_data.get("digital_twin_name", ""),
            "payload_path": resolve(config_data.get("payload_path", "../payloads.json"))
        }
    
    # Fallback to default config
    return dict(globals.config)


def _get_client(config=None):
    """
    Get an IoT Hub device client.
    
    Args:
        config: Optional config dict. If None, uses globals.config.
    
    Returns:
        Connected IoTHubDeviceClient instance.
    """
    global IoTHubDeviceClient, Message
    
    if IoTHubDeviceClient is None:
        from azure.iot.device import IoTHubDeviceClient as Client, Message as Msg
        IoTHubDeviceClient = Client
        Message = Msg
    
    conn_str = (config or globals.config)["connection_string"]
    client = IoTHubDeviceClient.create_from_connection_string(conn_str)
    return client


def send_mqtt(payload, device_config=None):
    """
    Send a single payload to Azure IoT Hub.
    
    Args:
        payload: Dictionary containing the telemetry data.
        device_config: Optional device-specific config. If None, auto-detects based on iotDeviceId.
    """
    # Get config - either device-specific or global
    if device_config is None:
        payload_device_id = payload.get("iotDeviceId")
        if payload_device_id and os.path.exists(f"configs/{payload_device_id}/config.json"):
            device_config = load_config_for_device(payload_device_id)
        else:
            device_config = globals.config
    
    device_id = device_config["device_id"]
    
    # Info message about device routing
    payload_device_id = payload.get("iotDeviceId")
    if payload_device_id and payload_device_id != device_id:
        print(f"INFO: Routing payload for '{payload_device_id}' via device '{device_id}'")

    client = _get_client(device_config)
    
    try:
        client.connect()
        
        # Create message with JSON payload
        message = Message(json.dumps(payload))
        message.content_type = "application/json"
        message.content_encoding = "utf-8"
        
        client.send_message(message)
        
        print(f"Message sent! Device: {device_id}, Payload: {payload}")
    finally:
        client.disconnect()


def send():
    """
    Send the next payload from the payloads.json file.
    
    Cycles through payloads sequentially, adding timestamps if missing.
    """
    global payload_index

    payloads_path = globals.config["payload_path"]

    with open(payloads_path, "r", encoding="utf-8") as f:
        payloads = json.load(f)

    if not payloads:
        print("No payloads found in payloads.json")
        return

    if payload_index >= len(payloads):
        payload_index = 0

    payload = payloads[payload_index].copy()
    payload_index += 1

    # Add timestamp if missing
    if "time" not in payload or payload["time"] == "":
        payload["time"] = datetime.now(timezone.utc).isoformat(
            timespec='milliseconds'
        ).replace('+00:00', 'Z')

    send_mqtt(payload)
