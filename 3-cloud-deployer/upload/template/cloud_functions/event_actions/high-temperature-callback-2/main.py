"""
High Temperature Callback 2 Google Cloud Function.

Event action with IoT Core command feedback capability.
GCP equivalent of AWS high-temperature-callback-2 using boto3.client('iot-data').publish().
"""
import json
import logging
import os
import functions_framework
from google.cloud import iot_v1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))
PROJECT_ID = _require_env("GCP_PROJECT_ID")
REGION = _require_env("GCP_IOT_REGION")
REGISTRY_ID = _require_env("GCP_IOT_REGISTRY_ID")

_iot_client = None


def _get_iot_client():
    """Lazy initialization of IoT Core client."""
    global _iot_client
    if _iot_client is None:
        _iot_client = iot_v1.DeviceManagerClient()
    return _iot_client


@functions_framework.http
def main(request):
    """Handle high temperature callback with IoT Core command feedback."""
    event = request.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    # Callback logic 2
    detail = event["detail"]
    if "action" in detail and "feedback" in detail["action"]:
        feedback = detail["action"]["feedback"]
        payload = feedback["payload"]
        if feedback["type"] == "mqtt":
            iot_id = feedback.get("iotDeviceId", "unknown")
            topic = f"dt-feedback-{iot_id}"  # Simplified topic logic
            
            # Send command via IoT Core (GCP equivalent of IoT Core publish)
            client = _get_iot_client()
            device_path = client.device_path(PROJECT_ID, REGION, REGISTRY_ID, iot_id)
            
            client.send_command_to_device(
                request={
                    "name": device_path,
                    "binary_data": json.dumps(payload).encode("utf-8"),
                    "subfolder": topic
                }
            )
    
    return (json.dumps({"statusCode": 200, "body": "Callback 2 executed"}), 200, {"Content-Type": "application/json"})
