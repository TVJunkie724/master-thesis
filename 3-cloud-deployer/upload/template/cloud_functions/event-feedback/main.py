"""
Event Feedback Google Cloud Function.

Sends commands to IoT devices via Google Cloud IoT Core.
GCP equivalent of AWS event-feedback using boto3.client('iot-data').publish().
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
PROJECT_ID = _require_env("GCP_PROJECT_ID")
REGION = _require_env("GCP_IOT_REGION")
REGISTRY_ID = _require_env("GCP_IOT_REGISTRY_ID")

# IoT client (lazy initialized)
_iot_client = None


def _get_iot_client():
    """Lazy initialization of IoT Core client."""
    global _iot_client
    if _iot_client is None:
        _iot_client = iot_v1.DeviceManagerClient()
    return _iot_client


@functions_framework.http
def main(request):
    """Send feedback message to IoT device via IoT Core command."""
    event = request.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    try:
        detail = event["detail"]
        payload = detail["payload"]
        iot_device_id = detail["iotDeviceId"]
        
        topic = f"{detail['digitalTwinName']}-{iot_device_id}"
        
        # Send command to device via IoT Core (GCP equivalent of IoT Core publish)
        client = _get_iot_client()
        device_path = client.device_path(PROJECT_ID, REGION, REGISTRY_ID, iot_device_id)
        
        # Send command
        client.send_command_to_device(
            request={
                "name": device_path,
                "binary_data": json.dumps({"message": payload}).encode("utf-8"),
                "subfolder": topic
            }
        )
    except Exception as e:
        logger.error(f"Event Feedback Failed: {e}")
        return (json.dumps({"statusCode": 500, "body": f"Error: {str(e)}"}), 500, {"Content-Type": "application/json"})
    
    return (json.dumps({"statusCode": 200, "body": "Feedback sent!"}), 200, {"Content-Type": "application/json"})
