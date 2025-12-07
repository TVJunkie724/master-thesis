import json
import os
import boto3


DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))
# Target function suffix is used to identify the target function, can be either "-processor" or "-connector"
TARGET_FUNCTION_SUFFIX = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    print("Hello from Dispatcher!")
    print("Event: " + json.dumps(event))

    processor_function_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"] + "-" + event["iotDeviceId"] + TARGET_FUNCTION_SUFFIX
    lambda_client.invoke(FunctionName=processor_function_name, InvocationType="Event", Payload=json.dumps(event).encode("utf-8"))
