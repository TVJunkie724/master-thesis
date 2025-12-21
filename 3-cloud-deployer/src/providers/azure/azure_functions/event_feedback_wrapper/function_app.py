"""
Event-Feedback Wrapper Azure Function.

Merges user-defined processing logic with the IoT Hub C2D feedback pipeline.
Executes user logic and sends result to IoT device.

Architecture:
    Event-Checker → Event-Feedback (user logic) → IoT Device
"""
import json
import logging
import os

import azure.functions as func
from azure.iot.hub import IoTHubRegistryManager
from process import process  # User logic import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded environment variables
_iot_hub_connection_string = None
_registry_manager = None


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


app = func.FunctionApp()


@app.function_name(name="event-feedback")
@app.route(route="event-feedback", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Execute user processing logic and send feedback to IoT device."""
    logger.info("Event-Feedback Wrapper: Executing user logic...")
    
    try:
        event = req.get_json()
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
