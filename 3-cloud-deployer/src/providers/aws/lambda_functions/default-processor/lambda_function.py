import os
import json
import boto3


DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))
PERSISTER_LAMBDA_NAME = os.environ.get("PERSISTER_LAMBDA_NAME", None)

lambda_client = boto3.client("lambda")


def process(event):
    payload = event.copy()
    payload["pressure"] = 20
    return payload


def lambda_handler(event, context):
    print("Hello from Default Processor!")
    print("Event: " + json.dumps(event))

    try:
        payload = process(event)
        lambda_client.invoke(FunctionName=PERSISTER_LAMBDA_NAME, InvocationType="Event", Payload=json.dumps(payload).encode("utf-8"))
    except Exception as e:
        print(f"Default Processor Error: {e}")
        raise e
