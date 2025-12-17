"""
Event Checker Azure Function.

Evaluates device data against configured thresholds and triggers
remediation workflows (Logic Apps) or feedback actions.

Architecture:
    Persister → Event Checker → Logic Apps / Azure Functions

Source: src/providers/azure/azure_functions/event-checker/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func
from azure.digitaltwins.core import DigitalTwinsClient
from azure.identity import DefaultAzureCredential

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env


# DIGITAL_TWIN_INFO is lazy-loaded to allow Azure function discovery
# (module-level require_env would fail during import if env var is missing)
_digital_twin_info = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

# Optional environment variables
ADT_INSTANCE_URL = os.environ.get("ADT_INSTANCE_URL", "").strip()
LOGIC_APP_TRIGGER_URL = os.environ.get("LOGIC_APP_TRIGGER_URL", "").strip()
FEEDBACK_FUNCTION_URL = os.environ.get("FEEDBACK_FUNCTION_URL", "").strip()
FUNCTION_APP_BASE_URL = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()

USE_LOGIC_APPS = os.environ.get("USE_LOGIC_APPS", "false").lower() == "true"
USE_FEEDBACK = os.environ.get("USE_FEEDBACK", "false").lower() == "true"

# Create Blueprint for registration in main function_app.py
bp = func.Blueprint()

# ADT client (lazy initialized)
_adt_client = None


def _get_adt_client():
    """Lazy initialization of ADT client."""
    global _adt_client
    if _adt_client is None:
        if not ADT_INSTANCE_URL:
            raise ValueError("ADT_INSTANCE_URL is required for fetching ADT property values")
        credential = DefaultAzureCredential()
        _adt_client = DigitalTwinsClient(ADT_INSTANCE_URL, credential)
    return _adt_client


def fetch_value(entity_id: str, component_name: str, property_name: str):
    """
    Fetch property value from Azure Digital Twins.
    
    Equivalent to AWS TwinMaker get_property_value.
    
    Args:
        entity_id: Digital twin entity ID
        component_name: Component name
        property_name: Property to fetch
    
    Returns:
        Property value
    """
    client = _get_adt_client()
    
    # Get the digital twin
    twin = client.get_digital_twin(entity_id)
    
    # ADT stores component data in the twin properties
    # Component properties are typically nested under the component name
    if component_name in twin:
        component_data = twin[component_name]
        if property_name in component_data:
            return component_data[property_name]
    
    # Fallback: check top-level properties
    if property_name in twin:
        return twin[property_name]
    
    raise ValueError(f"Property {property_name} not found in entity {entity_id}")


def extract_const_value(string: str):
    """
    Extract typed constant value from condition string.
    
    Supports: DOUBLE(x), INTEGER(x), STRING(x)
    """
    if string.startswith("DOUBLE"):
        return float(string[7:-1])
    elif string.startswith("INTEGER"):
        return int(string[8:-1])
    elif string.startswith("STRING"):
        return string[7:-1]
    return string


def _trigger_logic_app(payload: dict) -> None:
    """Trigger Azure Logic App via HTTP POST."""
    if not LOGIC_APP_TRIGGER_URL:
        raise ValueError("LOGIC_APP_TRIGGER_URL is required")
    
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(LOGIC_APP_TRIGGER_URL, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Logic App triggered: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to trigger Logic App: {e.code}")
        raise


def _invoke_function(function_name: str, payload: dict) -> None:
    """Invoke Azure Function via HTTP POST."""
    if not FUNCTION_APP_BASE_URL:
        logging.warning(f"FUNCTION_APP_BASE_URL not set - cannot invoke {function_name}")
        return
    
    url = f"{FUNCTION_APP_BASE_URL}/api/{function_name}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Function {function_name} invoked: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to invoke {function_name}: {e.code}")
        raise


def _send_feedback(feedback_payload: dict) -> None:
    """Send feedback via HTTP POST."""
    if not FEEDBACK_FUNCTION_URL:
        raise ValueError("FEEDBACK_FUNCTION_URL is required")
    
    data = json.dumps(feedback_payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(FEEDBACK_FUNCTION_URL, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Feedback sent: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to send feedback: {e.code}")
        raise


@bp.function_name(name="event-checker")
@bp.route(route="event-checker", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def event_checker(req: func.HttpRequest) -> func.HttpResponse:
    """
    Evaluate data against configured event rules and trigger actions.
    """
    logging.info("Azure Event Checker: Checking events")
    
    try:
        event = req.get_json()
        logging.info(f"Event: {json.dumps(event)}")
        
        config_events = _get_digital_twin_info().get("config_events", [])
        logging.info(f"Checking {len(config_events)} configured events")
        
        results = []
        
        for e in config_events:
            try:
                condition = e.get("condition", "")
                parts = condition.split()
                
                if len(parts) != 3:
                    logging.error(f"Invalid condition format: {condition}")
                    continue
                
                param1, operation, param2 = parts
                
                # Extract param1 value (property or constant)
                if len(param1.split(".")) > 1:
                    p1_parts = param1.split(".")
                    param1_value = fetch_value(p1_parts[0], p1_parts[1], p1_parts[2])
                else:
                    param1_value = extract_const_value(param1)
                
                # Extract param2 value (property or constant)
                if len(param2.split(".")) > 1:
                    p2_parts = param2.split(".")
                    param2_value = fetch_value(p2_parts[0], p2_parts[1], p2_parts[2])
                else:
                    param2_value = extract_const_value(param2)
                
                # Evaluate condition
                if operation == "<":
                    result = param1_value < param2_value
                elif operation == ">":
                    result = param1_value > param2_value
                elif operation == "==":
                    result = param1_value == param2_value
                else:
                    logging.error(f"Unknown operation: {operation}")
                    continue
                
                if result:
                    action_type = e.get("action", {}).get("type")
                    
                    # Handle Logic App action
                    if action_type == "logic_app" and USE_LOGIC_APPS:
                        _trigger_logic_app({"event": e})
                        results.append({"event": condition, "action": "logic_app_triggered"})
                    
                    # Handle function/lambda action
                    elif action_type in ("lambda", "function"):
                        function_name = e.get("action", {}).get("functionName")
                        _invoke_function(function_name, {"e": e})
                        results.append({"event": condition, "action": f"function_invoked:{function_name}"})
                    
                    # Handle feedback
                    if "feedback" in e.get("action", {}) and USE_FEEDBACK:
                        feedback_config = e["action"]["feedback"]
                        feedback_payload = {
                            "detail": {
                                "digitalTwinName": DIGITAL_TWIN_INFO["config"]["digital_twin_name"],
                                "iotDeviceId": feedback_config.get("iotDeviceId"),
                                "payload": feedback_config.get("payload")
                            }
                        }
                        _send_feedback(feedback_payload)
                        results.append({"event": condition, "feedback": "sent"})
                
            except Exception as ex:
                logging.error(f"Event check failed for {e}: {ex}")
                results.append({"event": str(e), "error": str(ex)})
        
        return func.HttpResponse(
            json.dumps({"checked": len(config_events), "results": results}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Event Checker Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
