"""
IoT Device Simulator - MQTT Transmission.

This module handles MQTT communication with AWS IoT Core,
sending test payloads from the configured payloads.json file.

Migration Status:
    - Uses globals for device certificates and endpoint config.
    - This is a standalone utility - no migration needed.
"""

import globals
import os
import json
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from datetime import datetime, timezone


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
            "endpoint": config_data["endpoint"],
            "topic": config_data["topic"],
            "device_id": config_data["device_id"],
            "cert_path": resolve(config_data["cert_path"]),
            "key_path": resolve(config_data["key_path"]),
            "root_ca_path": resolve(config_data["root_ca_path"]),
            "payload_path": resolve(config_data.get("payload_path", "../payloads.json"))
        }
    
    # Fallback to default config
    return dict(globals.config)


def send_mqtt(payload, device_config=None):
    """Send a single payload via MQTT.
    
    Args:
        payload: The payload dict to send
        device_config: Optional device-specific config. If None, uses globals.config.
    """
    # Get config - either device-specific or global
    if device_config is None:
        # Check if payload has iotDeviceId and we're in standalone mode
        payload_device_id = payload.get("iotDeviceId")
        if payload_device_id and os.path.exists(f"configs/{payload_device_id}/config.json"):
            device_config = load_config_for_device(payload_device_id)
        else:
            device_config = globals.config
    
    iot_device_id = device_config["device_id"]
    
    # Info message about device routing
    payload_device_id = payload.get("iotDeviceId")
    if payload_device_id and payload_device_id != iot_device_id:
        print(f"INFO: Routing payload for '{payload_device_id}' via device '{iot_device_id}'")

    client = AWSIoTMQTTClient(iot_device_id)
    client.configureEndpoint(device_config["endpoint"], 8883)
    client.configureCredentials(device_config["root_ca_path"], device_config["key_path"], device_config["cert_path"])

    topic = device_config["topic"]

    client.connect()
    client.publish(topic, json.dumps(payload), 1)
    client.disconnect()

    print(f"Message sent! Topic: {topic}, Payload: {payload}")


def send():
  global payload_index

  payloads_path = globals.config["payload_path"]

  with open(payloads_path, "r", encoding="utf-8") as f:
    payloads = json.load(f)

  if payload_index >= len(payloads):
    payload_index = 0

  payload = payloads[payload_index]
  payload_index += 1

  if "time" not in payload or payload["time"] == "":
    payload["time"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

  send_mqtt(payload)
