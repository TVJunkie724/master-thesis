"""
Event-Feedback Wrapper GCP Cloud Function.

Merges user-defined processing logic with the IoT Core command pipeline.
Executes user logic and sends result to IoT device.

Architecture:
    Event-Checker → Event-Feedback (user logic) → IoT Device
"""
import json
import logging
import os
import functions_framework
from google.cloud import iot_v1
from process import process  # User logic import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded environment variables
_project_id = None
_region = None
_registry_id = None
_iot_client = None


def _get_project_id():
    """Lazy load GCP project ID."""
    global _project_id
    if _project_id is None:
        value = os.environ.get("GCP_PROJECT_ID", "").strip()
        if not value:
            raise EnvironmentError("CRITICAL: GCP_PROJECT_ID is required")
        _project_id = value
    return _project_id


def _get_region():
    """Lazy load GCP IoT region."""
    global _region
    if _region is None:
        value = os.environ.get("GCP_IOT_REGION", "").strip()
        if not value:
            raise EnvironmentError("CRITICAL: GCP_IOT_REGION is required")
        _region = value
    return _region


def _get_registry_id():
    """Lazy load GCP IoT registry ID."""
    global _registry_id
    if _registry_id is None:
        value = os.environ.get("GCP_IOT_REGISTRY_ID", "").strip()
        if not value:
            raise EnvironmentError("CRITICAL: GCP_IOT_REGISTRY_ID is required")
        _registry_id = value
    return _registry_id


def _get_iot_client():
    """Lazy initialization of IoT Core client."""
    global _iot_client
    if _iot_client is None:
        _iot_client = iot_v1.DeviceManagerClient()
    return _iot_client


@functions_framework.http
def main(request):
    """Execute user processing logic and send feedback to IoT device."""
    logger.info("Event-Feedback Wrapper: Executing user logic...")
    
    try:
        event = request.get_json()
        logger.info(f"Received event: {json.dumps(event)}")
        
        detail = event["detail"]
        payload = detail["payload"]  # Extract payload for user processing
        iot_device_id = detail["iotDeviceId"]
        
        # 1. Execute User Logic
        try:
            processed_payload = process(payload)
            logger.info(f"User Logic Complete. Result: {json.dumps(processed_payload)}")
        except Exception as e:
            logger.error(f"[USER_LOGIC_ERROR] Processing failed: {e}")
            raise e
        
        # 2. Build topic and send to IoT Device via IoT Core
        topic = f"{detail['digitalTwinName']}-{iot_device_id}"
        
        client = _get_iot_client()
        device_path = client.device_path(
            _get_project_id(), 
            _get_region(), 
            _get_registry_id(), 
            iot_device_id
        )
        
        # Send command to device
        client.send_command_to_device(
            request={
                "name": device_path,
                "binary_data": json.dumps({"message": processed_payload}).encode("utf-8"),
                "subfolder": topic
            }
        )
        
        logger.info("Feedback sent to device.")
        return (
            json.dumps({"statusCode": 200, "body": "Feedback sent!"}), 
            200, 
            {"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"Event Feedback Failed: {e}")
        return (
            json.dumps({"statusCode": 500, "body": f"Error: {str(e)}"}), 
            500, 
            {"Content-Type": "application/json"}
        )
