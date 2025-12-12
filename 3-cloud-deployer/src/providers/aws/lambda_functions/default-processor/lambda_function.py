import os
import sys
import json
import boto3

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
PERSISTER_LAMBDA_NAME = require_env("PERSISTER_LAMBDA_NAME")

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
