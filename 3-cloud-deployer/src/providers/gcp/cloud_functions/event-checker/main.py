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
import traceback
import requests
import functions_framework

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
    from _shared.inter_cloud import get_access_token_headers, get_id_token_headers, validate_https_url
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.env_utils import require_env
    from _shared.inter_cloud import get_access_token_headers, get_id_token_headers, validate_https_url


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


def _extract_const_value(string: str):
    """
    Parse typed constant values from condition strings.
    
    Formats: DOUBLE(30), INTEGER(10), STRING(hello)
    """
    if string.startswith("DOUBLE"):
        return float(string[7:-1])
    elif string.startswith("INTEGER"):
        return int(string[8:-1])
    elif string.startswith("STRING"):
        return string[7:-1]
    return string


def _fetch_value_from_event(event: dict, property_name: str):
    """
    Extract property value from incoming event data.
    
    This makes the event-checker provider-agnostic - no L4 query needed.
    The incoming event already contains the telemetry values.
    
    Args:
        event: Incoming telemetry event dict
        property_name: Property name to extract (e.g., "temperature")
    
    Returns:
        Property value from event, or None if not found
    """
    if property_name in event:
        return event[property_name]
    
    # Check nested telemetry object (some formats nest values)
    telemetry = event.get("telemetry", {})
    if property_name in telemetry:
        return telemetry[property_name]
    
    return None


def _parse_string_condition(condition_str: str) -> dict:
    """
    Parse AWS/Azure-style string condition into structured format.
    
    Input: "testEntityId.component.temperature > DOUBLE(30)"
    Output: {"field": "temperature", "operator": ">", "value": 30}
    """
    parts = condition_str.split()
    if len(parts) != 3:
        return {}
    
    param1, operator, param2 = parts
    
    # Extract field name from dotted path (last segment)
    if "." in param1:
        field = param1.split(".")[-1]
    else:
        field = param1
    
    # Parse the comparison value
    value = _extract_const_value(param2)
    
    return {
        "field": field,
        "operator": operator,
        "value": value,
        "raw_condition": condition_str
    }


def _extract_condition_context(event: dict, condition: dict) -> dict:
    """
    Extract runtime context from condition for feedback enrichment.
    
    Returns:
        dict with actual_value, threshold, and condition string
    """
    field = condition.get("field", "")
    operator = condition.get("operator", "")
    value = condition.get("value")
    
    # Get actual value from event
    actual_value = _fetch_value_from_event(event, field)
    
    # Use raw condition string if available, otherwise build one
    condition_str = condition.get("raw_condition") or f"{field} {operator} {value}"
    
    return {
        "actual_value": actual_value,
        "threshold": value,
        "condition": condition_str
    }


def _evaluate_condition(event: dict, condition) -> bool:
    """
    Evaluate a condition against an event.
    
    Handles both:
    - String conditions: "entity.field > DOUBLE(30)"
    - Dict conditions: {"field": "temperature", "operator": ">", "value": 30}
    
    Supports operators: >, <, >=, <=, ==, !=
    """
    # Parse string conditions into dict format
    if isinstance(condition, str):
        condition = _parse_string_condition(condition)
    
    if not isinstance(condition, dict):
        print(f"Invalid condition type: {type(condition)}")
        return False
    
    field = condition.get("field")
    operator = condition.get("operator")
    value = condition.get("value")
    
    if not field or not operator:
        return False
    
    event_value = _fetch_value_from_event(event, field)
    if event_value is None:
        print(f"Property '{field}' not found in event, skipping")
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


def _build_workflow_payload(event: dict, action: dict) -> dict:
    """
    Build Cloud Workflow execution payload with function URLs.
    
    Constructs the payload expected by google_cloud_workflow.yaml:
    - FunctionA_URL: URL of the first Cloud Function to invoke
    - FunctionB_URL: URL of the second Cloud Function to invoke
    - InputData: The event and action data
    
    Args:
        event: The incoming telemetry event
        action: The action configuration from config_events.json
    
    Returns:
        dict ready to pass to Workflows API as argument
    """
    twin_info = _get_digital_twin_info()
    twin_name = twin_info["config"]["digital_twin_name"]
    func_a = action.get("functionName")
    func_b = action.get("functionNameB")
    
    # Get base URL from environment
    base_url = os.environ.get("GCP_FUNCTION_BASE_URL", "")
    
    payload = {"InputData": {"event": event, "action": action}}
    if func_a and base_url:
        payload["FunctionA_URL"] = f"{base_url}/{twin_name}-event-action-{func_a}"
    if func_b and base_url:
        payload["FunctionB_URL"] = f"{base_url}/{twin_name}-event-action-{func_b}"
    
    return payload


def _trigger_action(event: dict, action: dict, condition = None) -> None:
    """
    Execute the configured action with enriched context.
    
    Handles both GCP-native and AWS-style action types:
    - "workflow" / "step_function": Triggers Cloud Workflow
    - "function" / "lambda": Invokes a Cloud Function
    - "feedback": Sends feedback to IoT device
    """
    action_type = action.get("type", "")
    
    # Normalize condition to dict for context extraction
    if isinstance(condition, str):
        condition = _parse_string_condition(condition)
    
    # Handle workflow/step_function
    if action_type in ("workflow", "step_function"):
        if not WORKFLOW_TRIGGER_URL:
            print("WORKFLOW_TRIGGER_URL not configured, skipping workflow trigger")
            return
            
        print(f"Triggering Cloud Workflow: {WORKFLOW_TRIGGER_URL}")
        try:
            # Workflows API requires OAuth2 access tokens, not ID tokens
            workflow_payload = _build_workflow_payload(event, action)
            validate_https_url(WORKFLOW_TRIGGER_URL)
            resp = requests.post(
                WORKFLOW_TRIGGER_URL,
                json={"argument": json.dumps(workflow_payload)},
                headers=get_access_token_headers(),
                timeout=30
            )
            print(f"Workflow trigger response: {resp.status_code}")
            if resp.status_code >= 400:
                print(f"Workflow error response: {resp.text[:500]}")
        except Exception as e:
            print(f"Workflow trigger failed: {e}")
    
    # Handle function/lambda
    elif action_type in ("function", "lambda"):
        # Get function URL - either direct URL or construct from name
        function_url = action.get("functionUrl", "")
        
        if not function_url:
            # Construct URL from functionName if provided
            function_name = action.get("functionName", "")
            if function_name:
                twin_info = _get_digital_twin_info()
                twin_name = twin_info["config"]["digital_twin_name"]
                
                # Get base URL from environment
                base_url = os.environ.get("GCP_FUNCTION_BASE_URL", "")
                if base_url:
                    function_url = f"{base_url}/{twin_name}-event-action-{function_name}"
        
        if function_url:
            print(f"Invoking function: {function_url}")
            try:
                resp = requests.post(
                    function_url,
                    json={"event": event, "action": action},
                    headers=get_id_token_headers(function_url),
                    timeout=30
                )
                print(f"Function invocation response: {resp.status_code}")
            except Exception as e:
                print(f"Function invocation failed: {e}")
        else:
            print("No function URL available, skipping function invocation")
    
    elif action_type == "feedback":
        if not FEEDBACK_FUNCTION_URL:
            print("FEEDBACK_FUNCTION_URL not configured, skipping feedback")
            return

        # Extract context for enriched feedback
        context = _extract_condition_context(event, condition) if condition else {}
        
        # Send feedback to device
        feedback_payload = {
            "detail": {
                "digitalTwinName": _get_digital_twin_info()["config"]["digital_twin_name"],
                "iotDeviceId": event.get("device_id") or event.get("iotDeviceId"),
                "payload": {
                    "message": action.get("payload", {}),
                    "actual_value": context.get("actual_value"),
                    "threshold": context.get("threshold"),
                    "condition": context.get("condition")
                }
            }
        }
        print(f"Sending feedback via: {FEEDBACK_FUNCTION_URL}")
        try:
            resp = requests.post(
                FEEDBACK_FUNCTION_URL,
                json=feedback_payload,
                headers=get_id_token_headers(FEEDBACK_FUNCTION_URL),
                timeout=30
            )
            print(f"Feedback response: {resp.status_code}")
        except Exception as e:
            print(f"Feedback failed: {e}")
    
    else:
        print(f"Unknown action type: {action_type}")
    
    # Handle embedded feedback in action (AWS-style)
    if "feedback" in action and action_type != "feedback":
        feedback_config = action["feedback"]
        if FEEDBACK_FUNCTION_URL:
            context = _extract_condition_context(event, condition) if condition else {}
            feedback_payload = {
                "detail": {
                    "digitalTwinName": _get_digital_twin_info()["config"]["digital_twin_name"],
                    "iotDeviceId": feedback_config.get("iotDeviceId") or feedback_config.get("device_id"),
                    "payload": {
                        "message": feedback_config.get("payload", ""),
                        "actual_value": context.get("actual_value"),
                        "threshold": context.get("threshold"),
                        "condition": context.get("condition")
                    }
                }
            }
            print(f"Sending embedded feedback via: {FEEDBACK_FUNCTION_URL}")
            try:
                requests.post(
                    FEEDBACK_FUNCTION_URL,
                    json=feedback_payload,
                    headers=get_id_token_headers(FEEDBACK_FUNCTION_URL),
                    timeout=30
                )
            except Exception as e:
                print(f"Embedded feedback failed: {e}")


@functions_framework.http
def main(request):
    """
    Check events against rules and trigger actions.
    """
    print("Hello from Event Checker!")
    
    try:
        event = request.get_json()
        print("Event received")
        
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
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
