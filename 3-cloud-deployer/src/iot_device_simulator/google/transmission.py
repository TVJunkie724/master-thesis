"""
GCP IoT Device Simulator - Message transmission via Pub/Sub.

Note: GCP uses Pub/Sub, not MQTT (GCP IoT Core deprecated Jan 2023).
Uses service account credentials for authentication.
"""
import json
import os
from datetime import datetime, timezone

# Lazy import to avoid issues in development environments without the SDK
pubsub_v1 = None
service_account = None

from . import globals

payload_index = 0


def load_config_for_device(device_id: str) -> dict:
    """
    Load device-specific config for standalone multi-device mode.
    
    In standalone mode, configs are stored in configs/{device_id}/config.json.
    Falls back to root config.json if device-specific config not found.
    """
    if not device_id:
        return {
            "project_id": globals.config.project_id,
            "topic_name": globals.config.topic_name,
            "device_id": globals.config.device_id,
            "service_account_key_path": globals.config.service_account_key_path,
            "payload_path": globals.config.payload_path
        }
    
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
            "project_id": config_data["project_id"],
            "topic_name": config_data["topic_name"],
            "device_id": config_data["device_id"],
            "service_account_key_path": resolve(config_data.get("service_account_key_path", "../service_account.json")),
            "payload_path": resolve(config_data.get("payload_path", "../payloads.json"))
        }
    
    # Fallback to global config
    return {
        "project_id": globals.config.project_id,
        "topic_name": globals.config.topic_name,
        "device_id": globals.config.device_id,
        "service_account_key_path": globals.config.service_account_key_path,
        "payload_path": globals.config.payload_path
    }


def _get_publisher(config=None):
    """
    Get a Pub/Sub publisher client.
    
    Args:
        config: Optional config dict. If None, uses globals.config.
    
    Returns:
        Configured PublisherClient instance.
    """
    global pubsub_v1, service_account
    
    if pubsub_v1 is None:
        from google.cloud import pubsub_v1 as ps
        from google.oauth2 import service_account as sa
        pubsub_v1 = ps
        service_account = sa
    
    # Get service account key path from config or globals
    if config:
        sa_key_path = config["service_account_key_path"]
    else:
        sa_key_path = globals.config.service_account_key_path
    
    credentials = service_account.Credentials.from_service_account_file(sa_key_path)
    return pubsub_v1.PublisherClient(credentials=credentials)


def send_mqtt(payload: dict, device_config=None):
    """
    Send a single payload to GCP Pub/Sub topic.
    
    Args:
        payload: Dictionary containing the telemetry data.
        device_config: Optional device-specific config. If None, auto-detects based on iotDeviceId.
    """
    # Get config - either device-specific or global
    if device_config is None:
        payload_device_id = payload.get("iotDeviceId")
        if payload_device_id and os.path.exists(f"configs/{payload_device_id}/config.json"):
            device_config = load_config_for_device(payload_device_id)
    
    if device_config:
        device_id = device_config["device_id"]
        project_id = device_config["project_id"]
        topic_name = device_config["topic_name"]
    else:
        device_id = globals.config.device_id
        project_id = globals.config.project_id
        topic_name = globals.config.topic_name
        device_config = None  # Will use globals in _get_publisher
    
    # Info message about device routing
    payload_device_id = payload.get("iotDeviceId")
    if payload_device_id and payload_device_id != device_id:
        print(f"INFO: Routing payload for '{payload_device_id}' via device '{device_id}'")

    publisher = _get_publisher(device_config)
    topic_path = publisher.topic_path(project_id, topic_name)
    
    # Publish message
    message_data = json.dumps(payload).encode('utf-8')
    future = publisher.publish(topic_path, message_data)
    message_id = future.result()  # Wait for publish to complete
    
    print(f"Message sent! Topic: {topic_path}, Message ID: {message_id}, Payload: {payload}")


def send():
    """
    Send the next payload from the payloads.json file.
    
    Cycles through payloads sequentially, adding timestamps if missing.
    """
    global payload_index

    with open(globals.config.payload_path, "r", encoding="utf-8") as f:
        payloads = json.load(f)

    if payload_index >= len(payloads):
        payload_index = 0

    payload = payloads[payload_index]
    payload_index += 1

    if "time" not in payload or payload["time"] == "":
        payload["time"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    send_mqtt(payload)
