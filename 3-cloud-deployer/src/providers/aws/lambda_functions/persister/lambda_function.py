import os
import json
import boto3


DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", None)
EVENT_CHECKER_LAMBDA_NAME = os.environ.get("EVENT_CHECKER_LAMBDA_NAME", None)

dynamodb_client = boto3.resource("dynamodb")
dynamodb_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)
twinmaker_client = boto3.client("iottwinmaker")
lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    print("Hello from Persister!")
    print("Event: " + json.dumps(event))

    try:
        if "time" not in event:
             raise ValueError("Missing 'time' in event, cannot persist.")

        item = event.copy()
        item["id"] = str(item.pop("time")) # DynamoDB Primary SK is 'id' (time)

        dynamodb_table.put_item(Item=item)
        print("Item persisted.")

        if os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true":
            try:
                lambda_client.invoke(FunctionName=EVENT_CHECKER_LAMBDA_NAME, InvocationType="Event", Payload=json.dumps(event).encode("utf-8"))
            except Exception as e:
                print(f"Warning: Failed to invoke Event Checker: {e}")
                # Do not fail the whole lambda if event check fails? 
                # Usually fine, but if alerts are critical, maybe we should log error.
                pass 
                
    except Exception as e:
        print(f"Persister Error: {e}")
        raise e