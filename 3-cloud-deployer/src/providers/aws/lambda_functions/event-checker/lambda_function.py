import os
import sys
import json
import traceback
import boto3

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

# Optional environment variables (only used if features enabled)

LAMBDA_CHAIN_STEP_FUNCTION_ARN = os.environ.get("LAMBDA_CHAIN_STEP_FUNCTION_ARN", "")
EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN = os.environ.get("EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN", "")

USE_STEP_FUNCTIONS = os.environ.get("USE_STEP_FUNCTIONS", "false").lower() == "true"
USE_FEEDBACK = os.environ.get("USE_FEEDBACK", "false").lower() == "true"

lambda_client = boto3.client("lambda")
stepfunctions_client = boto3.client("stepfunctions")


def fetch_value_from_event(event, property_name):
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


def extract_const_value(string):
    if string.startswith("DOUBLE"):
        return float(string[7:-1])
    elif string.startswith("INTEGER"):
        return int(string[8:-1])
    elif string.startswith("STRING"):
        return string[7:-1]
    return string


def _build_step_function_payload(event_rule: dict) -> dict:
    """
    Build Step Function execution payload with Lambda ARNs.
    
    Constructs the payload expected by aws_step_function.json:
    - LambdaAArn: ARN of the first Lambda to invoke
    - LambdaBArn: ARN of the second Lambda to invoke  
    - InputData: The original event rule data
    
    Args:
        event_rule: The matched event rule from config_events.json
    
    Returns:
        dict ready to pass to stepfunctions.start_execution(input=...)
    """
    action = event_rule.get("action", {})
    func_a = action.get("functionName")
    func_b = action.get("functionNameB")
    
    # Get AWS region from Lambda context
    region = os.environ.get("AWS_REGION", "eu-central-1")
    
    # Extract account ID from Step Function ARN to avoid STS call
    # Format: arn:aws:states:region:account:stateMachine:name
    account_id = LAMBDA_CHAIN_STEP_FUNCTION_ARN.split(":")[4]
    
    twin_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"]
    
    payload = {"InputData": event_rule}
    if func_a:
        payload["LambdaAArn"] = f"arn:aws:lambda:{region}:{account_id}:function:{twin_name}-{func_a}"
    if func_b:
        payload["LambdaBArn"] = f"arn:aws:lambda:{region}:{account_id}:function:{twin_name}-{func_b}"
    
    return payload


def lambda_handler(event, context):
    print("Hello from Event-Checker!")
    print("Event received")
    print("Events: " + json.dumps(DIGITAL_TWIN_INFO["config_events"]))

    for e in DIGITAL_TWIN_INFO["config_events"]:
        try:
            condition = e["condition"]
            param1 = condition.split()[0]
            operation = condition.split()[1]
            param2 = condition.split()[2]

            # Extract property name from condition (format: entityId.componentId.propertyName)
            if len(param1.split(".")) > 1:
                param1_property_name = param1.split(".")[-1]  # Last segment is property
                param1_value = fetch_value_from_event(event, param1_property_name)
                if param1_value is None:
                    print(f"Property '{param1_property_name}' not found in event for condition '{condition}', skipping")
                    continue
            else:
                param1_value = extract_const_value(param1)

            if len(param2.split(".")) > 1:
                param2_property_name = param2.split(".")[-1]
                param2_value = fetch_value_from_event(event, param2_property_name)
                if param2_value is None:
                    print(f"Property '{param2_property_name}' not found in event for condition '{condition}', skipping")
                    continue
            else:
                param2_value = extract_const_value(param2)

            match operation:
                case "<":
                    result = param1_value < param2_value
                case ">":
                    result = param1_value > param2_value
                case "==":
                    result = param1_value == param2_value

            if result:
                # Handle Action
                action_type = e["action"]["type"]
                
                if action_type == "lambda":
                    payload = {
                        "e": e
                    }
                    full_function_name = f"{DIGITAL_TWIN_INFO['config']['digital_twin_name']}-{e['action']['functionName']}"
                    lambda_client.invoke(FunctionName=full_function_name, InvocationType="Event", Payload=json.dumps(payload).encode("utf-8"))
                
                elif action_type == "step_function":
                    if USE_STEP_FUNCTIONS:
                        if not LAMBDA_CHAIN_STEP_FUNCTION_ARN:
                            raise ConfigurationError("LAMBDA_CHAIN_STEP_FUNCTION_ARN is required when USE_STEP_FUNCTIONS is enabled")
                        payload = _build_step_function_payload(e)
                        stepfunctions_client.start_execution(
                            stateMachineArn=LAMBDA_CHAIN_STEP_FUNCTION_ARN,
                            input=json.dumps(payload)
                        )
                    else:
                        print(f"Skipping Step Function execution (Disabled): {e}")

                else:
                     raise ValueError(f"Invalid action type: {action_type}")
                     
                # Handle Feedback
                if "feedback" in e["action"] and USE_FEEDBACK:
                    if not EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN:
                        raise ConfigurationError("EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN is required when USE_FEEDBACK is enabled")
                    
                    # Enrich feedback payload with runtime context
                    feedback_config = e["action"]["feedback"]
                    feedback_payload = {
                        "detail": {
                            "digitalTwinName": DIGITAL_TWIN_INFO["config"]["digital_twin_name"],
                            "iotDeviceId": feedback_config.get("device_id") or feedback_config.get("iotDeviceId"),
                            "payload": {
                                "message": e["action"]["feedback"]["payload"],
                                "actual_value": param1_value,
                                "threshold": param2_value,
                                "condition": e["condition"]
                            }
                        }
                    }
                    
                    lambda_client.invoke(FunctionName=EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN, InvocationType="Event", Payload=json.dumps(feedback_payload).encode("utf-8"))
                    print("Feedback sent.")

        except Exception as ex:
            print(f"Event check failed: {ex}")
            traceback.print_exc()
            # Continue checking other events despite one failure
            continue
