import os
import json
import boto3


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))
PERSISTER_LAMBDA_NAME = _require_env("PERSISTER_LAMBDA_NAME")

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
