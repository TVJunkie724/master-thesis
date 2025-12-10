"""
Archive Writer Lambda Function (Multi-Cloud L3 Cold→Archive).

Receives data from remote Cold-to-Archive Mover,
validates authentication, and writes to S3 Archive bucket.

Source: src/providers/aws/lambda_functions/archive-writer/lambda_function.py
Editable: Yes - This is the runtime Lambda code
"""
import json
import os
import boto3


def _require_env(name: str) -> str:
    """Get required environment variable or raise RuntimeError."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


# Validate env vars at startup (fail-fast)
ARCHIVE_S3_BUCKET_NAME = _require_env("ARCHIVE_S3_BUCKET_NAME")
EXPECTED_TOKEN = _require_env("INTER_CLOUD_TOKEN")

s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """
    Handle incoming data from remote Cold-to-Archive Mover.
    
    Expected payload:
    {
        "object_key": "string",
        "data": "base64 or JSON string",
        "source_cloud": "string"
    }
    """
    print("Archive Writer: Received request")
    
    # 1. Validate Token
    headers = event.get("headers", {})
    incoming_token = None
    for k, v in headers.items():
        if k.lower() == "x-inter-cloud-token":
            incoming_token = v
            break
    
    if incoming_token != EXPECTED_TOKEN:
        print("Archive Writer: Token validation failed")
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Unauthorized: Invalid Token"})
        }
    
    # 2. Parse and validate payload
    try:
        body = json.loads(event.get("body", "{}"))
        
        object_key = body.get("object_key")
        data = body.get("data")
        
        if not object_key or data is None:
            raise ValueError("Missing required fields: object_key, data")
        
        # Log source for debugging
        source_cloud = body.get("source_cloud", "unknown")
        print(f"Archive Writer: Received object '{object_key}' from {source_cloud}")
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Archive Writer: Validation error - {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Bad Request: {str(e)}"})
        }
    
    # 3. Write to S3 Archive bucket
    try:
        # Data is JSON string (from cold storage batch files)
        body_content = data if isinstance(data, str) else json.dumps(data, default=str)
        
        s3_client.put_object(
            Bucket=ARCHIVE_S3_BUCKET_NAME,
            Key=object_key,
            Body=body_content,
            ContentType="application/json",
            StorageClass="DEEP_ARCHIVE"
        )
        
        print(f"Archive Writer: Wrote to s3://{ARCHIVE_S3_BUCKET_NAME}/{object_key}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "archived": True,
                "key": object_key
            })
        }
        
    except Exception as e:
        print(f"Archive Writer: S3 error - {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal Server Error: {str(e)}"})
        }
