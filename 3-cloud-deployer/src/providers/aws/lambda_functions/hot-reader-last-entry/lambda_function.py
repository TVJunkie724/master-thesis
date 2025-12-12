import json
import os
import sys
import boto3
from boto3.dynamodb.conditions import Key

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
DYNAMODB_TABLE_NAME = require_env("DYNAMODB_TABLE_NAME")

# Optional: For cross-cloud HTTP access via Function URL
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

twinmaker_client = boto3.client("iottwinmaker")
dynamodb_resource = boto3.resource("dynamodb")
dynamodb_table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)


def _is_http_request(event: dict) -> bool:
    """Detect if invoked via Function URL (HTTP) vs direct Lambda invoke."""
    return "requestContext" in event and "http" in event.get("requestContext", {})


def _validate_token(event: dict) -> bool:
    """Validate X-Inter-Cloud-Token header for HTTP requests."""
    if not INTER_CLOUD_TOKEN:
        return False
    headers = event.get("headers", {})
    token = headers.get("x-inter-cloud-token", "")
    return token == INTER_CLOUD_TOKEN


def _parse_http_request(event: dict) -> dict:
    """Parse query parameters from HTTP request body."""
    body = event.get("body", "{}")
    if event.get("isBase64Encoded", False):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body)


def _query_last_entry(query_event: dict) -> dict:
    """Query DynamoDB for the last entry and return TwinMaker-compatible response."""
    entity = twinmaker_client.get_entity(
        workspaceId=query_event["workspaceId"], 
        entityId=query_event["entityId"]
    )
    components = entity.get("components", {})
    component_info = components.get(query_event["componentName"])
    if not component_info:
        raise ValueError(f"Component {query_event['componentName']} not found.")
    
    component_type_id = component_info.get("componentTypeId")
    iot_device_id = component_type_id.removeprefix(DIGITAL_TWIN_INFO["config"]["digital_twin_name"] + "-")

    response = dynamodb_table.query(
        KeyConditionExpression=Key("iotDeviceId").eq(iot_device_id),
        ScanIndexForward=False,
        Limit=1
    )

    if len(response["Items"]) <= 0:
        return { "propertyValues": {} }

    item = response["Items"][0]
    property_values = {}

    for property_name in query_event["selectedProperties"]:
        property_type = f"{query_event['properties'][property_name]['definition']['dataType']['type'].lower()}Value"

        property_values[property_name] = {
            "propertyReference": {
                "entityId": query_event["entityId"],
                "componentName": query_event["componentName"],
                "propertyName": property_name
            },
            "propertyValue": {
                property_type: item[property_name]
            }
        }

    return { "propertyValues": property_values }


def lambda_handler(event, context):
    print("Hello from Hot Reader Last Entry!")
    print("Event: " + json.dumps(event))

    try:
        # Check if this is an HTTP request (via Function URL)
        if _is_http_request(event):
            print("HTTP request detected - validating token")
            if not _validate_token(event):
                print("ERROR: Invalid or missing X-Inter-Cloud-Token")
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "Unauthorized: Invalid X-Inter-Cloud-Token"})
                }
            query_event = _parse_http_request(event)
            result = _query_last_entry(query_event)
            return {
                "statusCode": 200,
                "body": json.dumps(result)
            }
        
        # Direct Lambda invocation (from TwinMaker or Digital Twin Data Connector)
        result = _query_last_entry(event)
        return result

    except Exception as e:
        print(f"Hot Reader Last Entry Error: {e}")
        if _is_http_request(event):
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)})
            }
        print("Returning empty propertyValues due to error.")
        return { "propertyValues": {} }

