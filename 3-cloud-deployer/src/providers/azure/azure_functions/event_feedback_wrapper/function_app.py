"""
Event-Feedback Wrapper Azure Function.

Calls user-defined event-feedback function via HTTP and sends result to IoT device.

Architecture:
    Event-Checker → Event-Feedback Wrapper → HTTP → User Function → Wrapper → IoT Device
"""
import json
import logging
import os

import azure.functions as func
from azure.iot.hub import IoTHubRegistryManager
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded environment variables
_iot_hub_connection_string = None
_registry_manager = None
_event_feedback_function_url = None


def _get_iot_hub_connection_string():
    """Lazy load IoT Hub connection string."""
    global _iot_hub_connection_string
    if _iot_hub_connection_string is None:
        value = os.environ.get("IOT_HUB_CONNECTION_STRING", "").strip()
        if not value:
            raise EnvironmentError("CRITICAL: IOT_HUB_CONNECTION_STRING is required")
        _iot_hub_connection_string = value
    return _iot_hub_connection_string


def _get_registry_manager():
    """Lazy initialization of IoT Hub Registry Manager."""
    global _registry_manager
    if _registry_manager is None:
        _registry_manager = IoTHubRegistryManager(_get_iot_hub_connection_string())
    return _registry_manager


def _get_event_feedback_function_url():
    """Lazy load event feedback function URL."""
    global _event_feedback_function_url
    if _event_feedback_function_url is None:
        _event_feedback_function_url = os.environ.get("EVENT_FEEDBACK_FUNCTION_URL", "").strip()
    return _event_feedback_function_url


bp = func.Blueprint()


@bp.function_name(name="event-feedback")
@bp.route(route="event-feedback", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Execute user processing logic and send feedback to IoT device."""
    logger.info("Event-Feedback Wrapper: Executing user logic...")
    
    try:
        event = req.get_json()
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
                data = json.dumps(payload).encode("utf-8")
                headers = {"Content-Type": "application/json"}
                req_feedback = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req_feedback, timeout=30) as response:
                    processed_payload = json.loads(response.read().decode("utf-8"))
                logger.info(f"User Logic Complete. Result: {json.dumps(processed_payload)}")
            except Exception as e:
                logger.error(f"[USER_LOGIC_ERROR] Processing failed: {e}")
                raise e
        
        # 2. Build topic and send to IoT Device via C2D
        topic = f"{detail['digitalTwinName']}-{iot_device_id}"
        
        registry_manager = _get_registry_manager()
        registry_manager.send_c2d_message(
            iot_device_id,
            json.dumps({"message": processed_payload}),
            properties={"topic": topic}
        )
        
        logger.info("Feedback sent to device.")
        return func.HttpResponse(
            json.dumps({"statusCode": 200, "body": "Feedback sent!"}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Event Feedback Failed: {e}")
        return func.HttpResponse(
            json.dumps({"statusCode": 500, "body": f"Error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
