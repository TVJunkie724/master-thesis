import json
import os
import boto3
from process import process  # User logic import


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
PERSISTER_LAMBDA_NAME = _require_env("PERSISTER_LAMBDA_NAME")

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    print("Wrapper Invoked. executing User Logic...")
    
    # 1. Execute User Logic
    try:
        processed_event = process(event)
        print("User Logic Complete. Result: " + json.dumps(processed_event))
    except Exception as e:
        print(f"[USER_LOGIC_ERROR] Processing failed: {e}")
        raise e # Fail lambda to trigger retry

    # 2. Invoke Persister (System Pipeline)
    try:
        lambda_client.invoke(
            FunctionName=PERSISTER_LAMBDA_NAME, 
            InvocationType="Event", 
            Payload=json.dumps(processed_event).encode("utf-8")
        )
    except Exception as e:
        print(f"[SYSTEM_ERROR] Persister Invocation failed: {e}")
        raise e
        
    return processed_event
