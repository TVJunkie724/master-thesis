"""
Cold Writer Lambda Function (Multi-Cloud L3 Hot→Cold).

Receives chunked data from remote Hot-to-Cold Mover,
validates authentication, and writes to S3 Cold bucket.

Source: src/providers/aws/lambda_functions/cold-writer/lambda_function.py
Editable: Yes - This is the runtime Lambda code
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


# Validate env vars at startup (fail-fast)
COLD_S3_BUCKET_NAME = require_env("COLD_S3_BUCKET_NAME")
EXPECTED_TOKEN = require_env("INTER_CLOUD_TOKEN")

s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """
    Handle incoming chunk from remote Hot-to-Cold Mover.
    
    Expected payload:
    {
        "iot_device_id": "string",
        "chunk_index": int,
        "start_timestamp": "ISO string",
        "end_timestamp": "ISO string",
        "items": [...]
    }
    """
    print("Cold Writer: Received request")
    
    # 1. Validate Token
    headers = event.get("headers", {})
    incoming_token = None
    for k, v in headers.items():
        if k.lower() == "x-inter-cloud-token":
            incoming_token = v
            break
    
    if incoming_token != EXPECTED_TOKEN:
        print("Cold Writer: Token validation failed")
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Unauthorized: Invalid Token"})
        }
    
    # 2. Parse and validate payload
    try:
        body = json.loads(event.get("body", "{}"))
        
        iot_device_id = body.get("iot_device_id")
        chunk_index = body.get("chunk_index")
        start_timestamp = body.get("start_timestamp")
        end_timestamp = body.get("end_timestamp")
        items = body.get("items")
        
        if not all([iot_device_id, chunk_index is not None, start_timestamp, end_timestamp, items]):
            raise ValueError("Missing required fields: iot_device_id, chunk_index, start_timestamp, end_timestamp, items")
        
        if not isinstance(items, list):
            raise ValueError("'items' must be a list")
        
        # Log source for debugging
        source_cloud = body.get("source_cloud", "unknown")
        print(f"Cold Writer: Received {len(items)} items from {source_cloud}")
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Cold Writer: Validation error - {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Bad Request: {str(e)}"})
        }
    
    # 3. Write to S3 Cold bucket
    try:
        # Use consistent key format for idempotency
        key = f"{iot_device_id}/{start_timestamp}-{end_timestamp}/chunk-{chunk_index:05d}.json"
        
        s3_client.put_object(
            Bucket=COLD_S3_BUCKET_NAME,
            Key=key,
            Body=json.dumps(items, default=str),
            ContentType="application/json",
            StorageClass="STANDARD_IA"
        )
        
        print(f"Cold Writer: Wrote {len(items)} items to s3://{COLD_S3_BUCKET_NAME}/{key}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "written": len(items),
                "key": key
            })
        }
        
    except Exception as e:
        print(f"Cold Writer: S3 error - {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal Server Error: {str(e)}"})
        }
