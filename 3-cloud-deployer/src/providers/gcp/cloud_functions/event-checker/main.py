"""
Event Checker GCP Cloud Function.

Checks events against configured rules and triggers Cloud Workflows
or other actions when conditions are met.

Source: src/providers/gcp/cloud_functions/event-checker/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import requests
import functions_framework
from google.cloud import firestore

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None

def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

# Optional - Cloud Workflow trigger URL
WORKFLOW_TRIGGER_URL = os.environ.get("WORKFLOW_TRIGGER_URL", "")
FEEDBACK_FUNCTION_URL = os.environ.get("FEEDBACK_FUNCTION_URL", "")


def _extract_condition_context(event: dict, condition: dict) -> dict:
    """
    Extract runtime context from GCP-style structured condition.
    
    GCP conditions use: {"field": "temperature", "operator": ">", "value": 30}
    Unlike AWS/Azure which use: "entity.component.temperature > DOUBLE(30)"
    
    Returns:
        dict with actual_value, threshold, and condition string
    """
    field = condition.get("field", "")
    operator = condition.get("operator", "")
    value = condition.get("value")
    
    # Get actual value from event
    actual_value = event.get(field)
    
    # Build human-readable condition string
    condition_str = f"{field} {operator} {value}"
    
    return {
        "actual_value": actual_value,
        "threshold": value,
        "condition": condition_str
    }


def _evaluate_condition(event: dict, condition: dict) -> bool:
    """
    Evaluate a condition against an event.
    
    Supports operators: >, <, >=, <=, ==, !=
    """
    field = condition.get("field")
    operator = condition.get("operator")
    value = condition.get("value")
    
    if not field or not operator:
        return False
    
    event_value = event.get(field)
    if event_value is None:
        return False
    
    try:
        if operator == ">":
            return event_value > value
        elif operator == "<":
            return event_value < value
        elif operator == ">=":
            return event_value >= value
        elif operator == "<=":
            return event_value <= value
        elif operator == "==":
            return event_value == value
        elif operator == "!=":
            return event_value != value
        else:
            print(f"Unknown operator: {operator}")
            return False
    except Exception as e:
        print(f"Condition evaluation error: {e}")
        return False


def _trigger_action(event: dict, action: dict, condition: dict = None) -> None:
    """Execute the configured action with enriched context."""
    action_type = action.get("type", "")
    
    if action_type == "workflow":
        # Trigger Cloud Workflow
        if not WORKFLOW_TRIGGER_URL:
            raise ConfigurationError("WORKFLOW_TRIGGER_URL is required for 'workflow' actions")
            
        print(f"Triggering Cloud Workflow: {WORKFLOW_TRIGGER_URL}")
        requests.post(
            WORKFLOW_TRIGGER_URL,
            json={"event": event, "action": action},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
    
    elif action_type == "function":
        # Invoke another Cloud Function
        function_url = action.get("functionUrl", "")
        if function_url:
            print(f"Invoking function: {function_url}")
            requests.post(
                function_url,
                json={"event": event, "action": action},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
    
    elif action_type == "feedback":
        if not FEEDBACK_FUNCTION_URL:
            raise ConfigurationError("FEEDBACK_FUNCTION_URL is required for 'feedback' actions")

        # Extract context for enriched feedback
        context = _extract_condition_context(event, condition) if condition else {}
        
        # Send feedback to device
        feedback_payload = {
            "detail": {
                "digitalTwinName": _get_digital_twin_info()["config"]["digital_twin_name"],
                "iotDeviceId": event.get("iotDeviceId"),
                "payload": {
                    "message": action.get("payload", {}),
                    "actual_value": context.get("actual_value"),
                    "threshold": context.get("threshold"),
                    "condition": context.get("condition")
                }
            }
        }
        print(f"Sending feedback via: {FEEDBACK_FUNCTION_URL}")
        requests.post(
            FEEDBACK_FUNCTION_URL,
            json=feedback_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )


@functions_framework.http
def main(request):
    """
    Check events against rules and trigger actions.
    """
    print("Hello from Event Checker!")
    
    try:
        event = request.get_json()
        print("Event: " + json.dumps(event))
        
        # Get event rules from DIGITAL_TWIN_INFO
        event_rules = _get_digital_twin_info().get("config_events", [])
        
        triggered_count = 0
        for rule in event_rules:
            condition = rule.get("condition", {})
            action = rule.get("action", {})
            
            if _evaluate_condition(event, condition):
                print(f"Rule triggered: {condition}")
                _trigger_action(event, action, condition)  # Pass condition for context extraction
                triggered_count += 1
        
        return (json.dumps({"status": "checked", "triggered": triggered_count}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Event Checker Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})

