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


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

# Optional - Cloud Workflow trigger URL
WORKFLOW_TRIGGER_URL = os.environ.get("WORKFLOW_TRIGGER_URL", "")
FEEDBACK_FUNCTION_URL = os.environ.get("FEEDBACK_FUNCTION_URL", "")


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


def _trigger_action(event: dict, action: dict) -> None:
    """Execute the configured action."""
    action_type = action.get("type", "")
    
    if action_type == "workflow":
        # Trigger Cloud Workflow
        if WORKFLOW_TRIGGER_URL:
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
        # Send feedback to device
        if FEEDBACK_FUNCTION_URL:
            feedback_payload = {
                "detail": {
                    "digitalTwinName": DIGITAL_TWIN_INFO["config"]["digital_twin_name"],
                    "iotDeviceId": event.get("iotDeviceId"),
                    "payload": action.get("payload", {})
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
        event_rules = DIGITAL_TWIN_INFO.get("config_events", [])
        
        triggered_count = 0
        for rule in event_rules:
            condition = rule.get("condition", {})
            action = rule.get("action", {})
            
            if _evaluate_condition(event, condition):
                print(f"Rule triggered: {condition}")
                _trigger_action(event, action)
                triggered_count += 1
        
        return (json.dumps({"status": "checked", "triggered": triggered_count}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Event Checker Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
