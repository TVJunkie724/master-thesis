"""
Azure IoT Device Simulator - MQTT Transmission.

This module handles communication with Azure IoT Hub,
sending test payloads using the azure-iot-device SDK.

Unlike AWS (which uses X.509 certificates), Azure uses connection strings
with SAS (Shared Access Signature) authentication.
"""

from . import globals
import json
from datetime import datetime, timezone

# Lazy import to avoid issues in development environments without the SDK
IoTHubDeviceClient = None
Message = None

payload_index = 0


def _get_client():
    """
    Get an IoT Hub device client.
    
    Returns:
        Connected IoTHubDeviceClient instance.
    """
    global IoTHubDeviceClient, Message
    
    if IoTHubDeviceClient is None:
        from azure.iot.device import IoTHubDeviceClient as Client, Message as Msg
        IoTHubDeviceClient = Client
        Message = Msg
    
    client = IoTHubDeviceClient.create_from_connection_string(
        globals.config["connection_string"]
    )
    return client


def send_mqtt(payload):
    """
    Send a single payload to Azure IoT Hub.
    
    Args:
        payload: Dictionary containing the telemetry data.
    """
    device_id = globals.config["device_id"]
    
    # Optional: Check if payload device ID matches configured device ID
    if payload.get("iotDeviceId") != device_id:
        print(f"WARNING: Payload iotDeviceId '{payload.get('iotDeviceId')}' "
              f"does not match configured device '{device_id}'")

    client = _get_client()
    
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
