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

# Lazy-initialized globals (populated on first request, not at module load)
_config = {}
_iot_client = None


def _get_config():
    """Lazy initialization of config from environment variables."""
    global _config
    if not _config:
        _config = {
            "digital_twin_info": json.loads(os.environ.get("DIGITAL_TWIN_INFO", "{}")),
            "project_id": os.environ.get("GCP_PROJECT_ID", ""),
            "region": os.environ.get("GCP_IOT_REGION", ""),
            "registry_id": os.environ.get("GCP_IOT_REGISTRY_ID", ""),
        }
    return _config


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
    
    # Get config lazily
    config = _get_config()
    
    # Callback logic 2
    detail = event.get("detail", {})
    if "action" in detail and "feedback" in detail["action"]:
        feedback = detail["action"]["feedback"]
        payload = feedback.get("payload", {})
        if feedback.get("type") == "mqtt":
            iot_id = feedback.get("iotDeviceId", "unknown")
            topic = f"dt-feedback-{iot_id}"  # Simplified topic logic
            
            # Only attempt IoT Core if config is present
            if config["project_id"] and config["region"] and config["registry_id"]:
                client = _get_iot_client()
                device_path = client.device_path(
                    config["project_id"], 
                    config["region"], 
                    config["registry_id"], 
                    iot_id
                )
                
                client.send_command_to_device(
                    request={
                        "name": device_path,
                        "binary_data": json.dumps(payload).encode("utf-8"),
                        "subfolder": topic
                    }
                )
            else:
                logger.warning("IoT Core config not set, skipping device command")
    
    return (json.dumps({"statusCode": 200, "body": "Callback 2 executed"}), 200, {"Content-Type": "application/json"})
