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


lambda_client = boto3.client("lambda")

# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")


def lambda_handler(event, context):
    # 1. Validate Token
    # API Gateway/Lambda Function URL headers are case-insensitive, usually lower-cased
    headers = event.get("headers", {})
    # Look for token (case-insensitive)
    incoming_token = None
    for k, v in headers.items():
        if k.lower() == "x-inter-cloud-token":
            incoming_token = v
            break
            
    if incoming_token != INTER_CLOUD_TOKEN:
        return {
            "statusCode": 403,
            "body": json.dumps("Unauthorized: Invalid Token")
        }

    # 2. Unwrap Payload and log source
    try:
        body = json.loads(event.get("body", "{}"))
        
        # Log source cloud for debugging/auditing
        source_cloud = body.get("source_cloud", "unknown")
        print(f"Received event from source cloud: {source_cloud}")
        
        actual_event = body.get("payload")
        if not actual_event:
            raise ValueError("Missing 'payload' in wrapper.")
             
        device_id = actual_event.get("iotDeviceId")
        if not device_id:
            raise ValueError("Missing 'iotDeviceId' in event.")
             
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps(f"Bad Request: {str(e)}")
        }

    # 3. Invoke Local Processor
    try:
        twin_name = DIGITAL_TWIN_INFO.get("config", {}).get("digital_twin_name")
        processor_name = f"{twin_name}-{device_id}-processor" # Always invokes the local processor
        
        lambda_client.invoke(FunctionName=processor_name, InvocationType="Event", Payload=json.dumps(actual_event).encode("utf-8"))
    
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "Success", "invoked": processor_name})
        }
    except Exception as e:
        print(f"Ingestion Invocation Failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Internal Server Error: Failed to invoke processor {str(e)}")
        }
