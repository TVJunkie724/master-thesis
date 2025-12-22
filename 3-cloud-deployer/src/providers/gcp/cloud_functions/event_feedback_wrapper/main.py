"""
Event-Feedback Wrapper GCP Cloud Function.

Calls user-defined event-feedback function via HTTP and sends result to IoT device.

Architecture:
    Event-Checker → Event-Feedback Wrapper → HTTP → User Function → Wrapper → IoT Device
"""
import json
import logging
import os
import functions_framework
import requests
from google.cloud import iot_v1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded environment variables
_project_id = None
_region = None
_registry_id = None
_iot_client = None
_event_feedback_function_url = None


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


def _get_event_feedback_function_url():
    """Lazy load event feedback function URL."""
    global _event_feedback_function_url
    if _event_feedback_function_url is None:
        _event_feedback_function_url = os.environ.get("EVENT_FEEDBACK_FUNCTION_URL", "").strip()
    return _event_feedback_function_url


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
        
        # 1. Call User Event-Feedback Function via HTTP
        url = _get_event_feedback_function_url()
        if not url or not url.startswith("http"):
            logger.warning("EVENT_FEEDBACK_FUNCTION_URL not set - using passthrough")
            processed_payload = payload
        else:
            try:
                logger.info(f"Calling user event-feedback function at {url}")
                response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
                response.raise_for_status()
                processed_payload = response.json()
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
