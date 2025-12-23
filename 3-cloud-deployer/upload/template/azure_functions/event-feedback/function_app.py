"""
High Temperature Callback 2 Azure Function.

Event action with IoT Hub feedback capability.
Azure equivalent of AWS high-temperature-callback-2 using boto3.client('iot-data').publish().
"""
import json
import logging
import os

import azure.functions as func
from azure.iot.hub import IoTHubRegistryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy-initialized globals (populated on first request, not at module load)
_registry_manager = None

app = func.FunctionApp()


def _get_registry_manager():
    """Lazy initialization of IoT Hub Registry Manager."""
    global _registry_manager
    if _registry_manager is None:
        connection_string = os.environ.get("IOT_HUB_CONNECTION_STRING", "")
        if connection_string:
            _registry_manager = IoTHubRegistryManager(connection_string)
    return _registry_manager


@app.function_name(name="high-temperature-callback-2")
@app.route(route="high-temperature-callback-2", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handle high temperature callback with MQTT feedback."""
    event = req.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    # Callback logic 2
    detail = event.get("detail", {})
    if "action" in detail and "feedback" in detail["action"]:
        feedback = detail["action"]["feedback"]
        payload = feedback.get("payload", {})
        if feedback.get("type") == "mqtt":
            iot_id = feedback.get("iotDeviceId", "unknown")
            topic = f"dt-feedback-{iot_id}"  # Simplified topic logic
            
            # Only attempt IoT Hub if registry manager is available
            registry_manager = _get_registry_manager()
            if registry_manager:
                registry_manager.send_c2d_message(
                    iot_id,
                    json.dumps(payload),
                    properties={"topic": topic}
                )
            else:
                logger.warning("IoT Hub connection not configured, skipping device message")
    
    return func.HttpResponse(
        json.dumps({"statusCode": 200, "body": "Callback 2 executed"}),
        status_code=200,
        mimetype="application/json"
    )
