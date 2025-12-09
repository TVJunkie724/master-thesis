import os
import json
import boto3


DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))
TWINMAKER_WORKSPACE_NAME = os.environ.get("TWINMAKER_WORKSPACE_NAME", None)

LAMBDA_CHAIN_STEP_FUNCTION_ARN = os.environ.get("LAMBDA_CHAIN_STEP_FUNCTION_ARN", None)
EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN = os.environ.get("EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN", None)

USE_STEP_FUNCTIONS = os.environ.get("USE_STEP_FUNCTIONS", "false").lower() == "true"
USE_FEEDBACK = os.environ.get("USE_FEEDBACK", "false").lower() == "true"

twinmaker_client = boto3.client("iottwinmaker")
lambda_client = boto3.client("lambda")
stepfunctions_client = boto3.client("stepfunctions")


def fetch_value(entity_id, component_name, property_name):
    response = twinmaker_client.get_property_value(
        workspaceId=TWINMAKER_WORKSPACE_NAME,
        entityId=entity_id,
        componentName=component_name,
        selectedProperties=[property_name]
    )

    property = list(response["propertyValues"].values())[0]
    value = list(property["propertyValue"].values())[0]

    return value


def extract_const_value(string):
    if string.startswith("DOUBLE"):
        return float(string[7:-1])
    elif string.startswith("INTEGER"):
        return int(string[8:-1])
    elif string.startswith("STRING"):
        return string[7:-1]
    return string


def lambda_handler(event, context):
    print("Hello from Event-Checker!")
    print("Event: " + json.dumps(event))
    print("Events: " + json.dumps(DIGITAL_TWIN_INFO["config_events"]))

    for e in DIGITAL_TWIN_INFO["config_events"]:
        try:
            condition = e["condition"]
            param1 = condition.split()[0]
            operation = condition.split()[1]
            param2 = condition.split()[2]

            if len(param1.split(".")) > 1:
                param1_entity_id = param1.split(".")[0]
                param1_component_name = param1.split(".")[1]
                param1_property_name = param1.split(".")[2]
                param1_value = fetch_value(param1_entity_id, param1_component_name, param1_property_name)
            else:
                param1_value = extract_const_value(param1)

            if len(param2.split(".")) > 1:
                param2_entity_id = param2.split(".")[0]
                param2_component_name = param2.split(".")[1]
                param2_property_name = param2.split(".")[2]
                param2_value = fetch_value(param2_entity_id, param2_component_name, param2_property_name)
            else:
                param2_value = extract_const_value(param2)

            match operation:
                case "<": result = param1_value < param2_value
                case ">": result = param1_value > param2_value
                case "==": result = param1_value == param2_value

            if result:
                # Handle Action
                action_type = e["action"]["type"]
                
                if action_type == "lambda":
                    payload = {
                        "e": e
                    }
                    lambda_client.invoke(FunctionName=e["action"]["functionName"], InvocationType="Event", Payload=json.dumps(payload).encode("utf-8"))
                
                elif action_type == "step_function":
                    if USE_STEP_FUNCTIONS:
                        stepfunctions_client.start_execution(
                            stateMachineArn=LAMBDA_CHAIN_STEP_FUNCTION_ARN,
                            input=json.dumps(e)
                        )
                    else:
                        print(f"Skipping Step Function execution (Disabled): {e}")

                else:
                     raise ValueError(f"Invalid action type: {action_type}")
                     
                # Handle Feedback
                if "feedback" in e["action"] and USE_FEEDBACK:
                    feedback_payload = {
                        "detail": {
                            "digitalTwinName": DIGITAL_TWIN_INFO["config"]["digital_twin_name"],
                            "iotDeviceId": e["action"]["feedback"]["iotDeviceId"], # Assuming logic matches intent
                             "payload": e["action"]["feedback"]["payload"]

                        }
                    }
                    # Adjust payload structure to match what event-feedback expects?
                    # event-feedback expects: detail > payload, iotDeviceId, digitalTwinName
                    # My payload construction above matches that structure in "detail" key?
                    # Wait, event-feedback handler: `detail = event["detail"]`.
                    # So I should send `{"detail": ...}`. Yes.
                    
                    # Need to verify where iotDeviceId comes from if not in feedback object.
                    # Looking at config_events.json earlier: "feedback": {"type":"mqtt", "iotDeviceId":"...", "payload":"..."}
                    # So it is there.
                    
                    lambda_client.invoke(FunctionName=EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN, InvocationType="Event", Payload=json.dumps(feedback_payload).encode("utf-8"))
                    print("Feedback sent.")

        except Exception as ex:
            print(f"Event Check Failed for event {e}: {ex}")
            # Continue checking other events despite one failure
            continue
