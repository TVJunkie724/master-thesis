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


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
IOT_HUB_CONNECTION_STRING = _require_env("IOT_HUB_CONNECTION_STRING")

_registry_manager = None

app = func.FunctionApp()


def _get_registry_manager():
    """Lazy initialization of IoT Hub Registry Manager."""
    global _registry_manager
    if _registry_manager is None:
        _registry_manager = IoTHubRegistryManager(IOT_HUB_CONNECTION_STRING)
    return _registry_manager


@app.function_name(name="high-temperature-callback-2")
@app.route(route="high-temperature-callback-2", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handle high temperature callback with MQTT feedback."""
    event = req.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    # Callback logic 2
    detail = event["detail"]
    if "action" in detail and "feedback" in detail["action"]:
        feedback = detail["action"]["feedback"]
        payload = feedback["payload"]
        if feedback["type"] == "mqtt":
            iot_id = feedback.get("iotDeviceId", "unknown")
            topic = f"dt-feedback-{iot_id}"  # Simplified topic logic
            
            # Publish via IoT Hub C2D (Azure equivalent of IoT Core publish)
            registry_manager = _get_registry_manager()
            registry_manager.send_c2d_message(
                iot_id,
                json.dumps(payload),
                properties={"topic": topic}
            )
    
    return func.HttpResponse(
        json.dumps({"statusCode": 200, "body": "Callback 2 executed"}),
        status_code=200,
        mimetype="application/json"
    )
