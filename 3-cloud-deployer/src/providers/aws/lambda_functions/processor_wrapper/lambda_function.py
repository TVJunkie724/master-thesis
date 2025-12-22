"""
Processor Wrapper AWS Lambda.

Calls user-defined processor Lambda and invokes the Persister.
Dynamically constructs processor Lambda name from device ID.

Architecture:
    Ingestion → Processor Wrapper → Lambda Invoke → User Processor → Wrapper → Persister
"""
import json
import os
import sys
import boto3

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.env_utils import require_env


# Lazy-loaded environment variables and clients
_persister_lambda_name = None
_digital_twin_info = None
_lambda_client = None

def _get_lambda_client():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client

def _get_persister_lambda_name():
    global _persister_lambda_name
    if _persister_lambda_name is None:
        _persister_lambda_name = require_env("PERSISTER_LAMBDA_NAME")
    return _persister_lambda_name

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_processor_lambda_name(device_id: str) -> str:
    """Construct processor Lambda name dynamically from device ID."""
    twin_name = _get_digital_twin_info()["config"]["digital_twin_name"]
    return f"{twin_name}-{device_id}-processor"


def lambda_handler(event, context):
    print("Wrapper Invoked. Calling User Processor...")
    
    # 1. Call User Processor Lambda
    device_id = event.get("iotDeviceId", "default")
    processor_name = _get_processor_lambda_name(device_id)
    
    try:
        print(f"Invoking user processor: {processor_name}")
        response = _get_lambda_client().invoke(
            FunctionName=processor_name,
            InvocationType="RequestResponse",  # Sync call
            Payload=json.dumps(event).encode("utf-8")
        )
        processed_event = json.loads(response['Payload'].read().decode("utf-8"))
        print("User Processor Complete. Result: " + json.dumps(processed_event))
    except Exception as e:
        print(f"[USER_LOGIC_ERROR] Processor invocation failed: {e}")
        raise e

    # 2. Invoke Persister (System Pipeline)
    try:
        _get_lambda_client().invoke(
            FunctionName=_get_persister_lambda_name(),
            InvocationType="Event",  # Async call
            Payload=json.dumps(processed_event).encode("utf-8")
        )
    except Exception as e:
        print(f"[SYSTEM_ERROR] Persister Invocation failed: {e}")
        raise e
        
    return processed_event
