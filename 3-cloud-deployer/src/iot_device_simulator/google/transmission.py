"""
GCP IoT Device Simulator - Message transmission via Pub/Sub.

Note: GCP uses Pub/Sub, not MQTT (GCP IoT Core deprecated Jan 2023).
Uses service account credentials for authentication.
"""
import json
from datetime import datetime, timezone

# Lazy import to avoid issues in development environments without the SDK
pubsub_v1 = None
service_account = None

from . import globals

payload_index = 0


def _get_publisher():
    """
    Get a Pub/Sub publisher client.
    
    Returns:
        Configured PublisherClient instance.
    """
    global pubsub_v1, service_account
    
    if pubsub_v1 is None:
        from google.cloud import pubsub_v1 as ps
        from google.oauth2 import service_account as sa
        pubsub_v1 = ps
        service_account = sa
    
    # Load service account credentials
    credentials = service_account.Credentials.from_service_account_file(
        globals.config.service_account_key_path
    )
    
    return pubsub_v1.PublisherClient(credentials=credentials)


def send_mqtt(payload: dict):
    """
    Send a single payload to GCP Pub/Sub topic.
    
    Args:
        payload: Dictionary containing the telemetry data.
    """
    device_id = globals.config.device_id
    
    # Optional: Check if payload device ID matches configured device ID
    if payload.get("iotDeviceId") != device_id:
        print(f"WARNING: Payload iotDeviceId '{payload.get('iotDeviceId')}' "
              f"does not match configured device '{device_id}'")

    publisher = _get_publisher()
    topic_path = publisher.topic_path(globals.config.project_id, globals.config.topic_name)
    
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
