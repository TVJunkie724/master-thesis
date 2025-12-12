import json
import os
import sys
import boto3
from process import process  # User logic import

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
PERSISTER_LAMBDA_NAME = require_env("PERSISTER_LAMBDA_NAME")

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
