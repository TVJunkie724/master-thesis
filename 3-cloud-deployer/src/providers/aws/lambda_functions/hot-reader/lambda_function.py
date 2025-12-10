import json
import os
import boto3
from boto3.dynamodb.conditions import Key


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))
DYNAMODB_TABLE_NAME = _require_env("DYNAMODB_TABLE_NAME")

twinmaker_client = boto3.client("iottwinmaker")
dynamodb_resource = boto3.resource("dynamodb")
dynamodb_table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)


def lambda_handler(event, context):
    print("Hello from Hot Reader!")
    print("Event: " + json.dumps(event))

    try:
        entity = twinmaker_client.get_entity(workspaceId=event["workspaceId"], entityId=event["entityId"])
        components = entity.get("components", {})
        component_info = components.get(event["componentName"])
        if not component_info:
             raise ValueError(f"Component {event['componentName']} not found.")
        
        component_type_id = component_info.get("componentTypeId")

        iot_device_id = component_type_id.removeprefix(DIGITAL_TWIN_INFO["config"]["digital_twin_name"] + "-")

        response = dynamodb_table.query(
            KeyConditionExpression=Key("iotDeviceId").eq(iot_device_id) &
                                   Key("id").between(event["startTime"], event["endTime"])
            )
        items = response["Items"]

        property_values = []

        for property_name in event["selectedProperties"]:
            property_type = f"{event['properties'][property_name]['definition']['dataType']['type'].capitalize()}Value"

            entry = {
                "entityPropertyReference": {
                    "propertyName": property_name
                },
                "values": []
            }

            for item in items:
                entry["values"].append({
                    "time": item["id"],
                    "value": { property_type: item[property_name] }
                })

            property_values.append(entry)

        return { "propertyValues": property_values }

    except Exception as e:
        print(f"Hot Reader Error: {e}")
        # TwinMaker expects specific error signatures or empty results?
        # Typically, TwinMaker reads just want the data or nothing.
        # Returning empty to avoid breaking the dashboard, but logging error.
        print("Returning empty propertyValues due to error.")
        return { "propertyValues": [] }
