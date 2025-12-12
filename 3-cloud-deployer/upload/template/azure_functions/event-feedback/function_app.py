"""
Event Feedback Azure Function.

Sends Cloud-to-Device (C2D) messages to IoT devices via Azure IoT Hub.
Azure equivalent of AWS event-feedback using boto3.client('iot-data').publish().
"""
import json
import logging
import os

import azure.functions as func
from azure.iot.hub import IoTHubRegistryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
IOT_HUB_CONNECTION_STRING = _require_env("IOT_HUB_CONNECTION_STRING")

# Registry manager (lazy initialized)
_registry_manager = None

app = func.FunctionApp()


def _get_registry_manager():
    """Lazy initialization of IoT Hub Registry Manager."""
    global _registry_manager
    if _registry_manager is None:
        _registry_manager = IoTHubRegistryManager(IOT_HUB_CONNECTION_STRING)
    return _registry_manager


@app.function_name(name="event-feedback")
@app.route(route="event-feedback", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Send feedback message to IoT device via IoT Hub C2D."""
    event = req.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    try:
        detail = event["detail"]
        payload = detail["payload"]
        iot_device_id = detail["iotDeviceId"]
        
        topic = f"{detail['digitalTwinName']}-{iot_device_id}"
        
        # Publish feedback to IoT Hub (Azure equivalent of IoT Core publish)
        registry_manager = _get_registry_manager()
        registry_manager.send_c2d_message(
            iot_device_id,
            json.dumps({"message": payload}),
            properties={"topic": topic}
        )
    except Exception as e:
        logger.error(f"Event Feedback Failed: {e}")
        return func.HttpResponse(
            json.dumps({"statusCode": 500, "body": f"Error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
    
    return func.HttpResponse(
        json.dumps({"statusCode": 200, "body": "Feedback sent!"}),
        status_code=200,
        mimetype="application/json"
    )
