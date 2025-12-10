import json
import os
import boto3


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
DYNAMODB_TABLE_NAME = _require_env("DYNAMODB_TABLE_NAME")
INTER_CLOUD_TOKEN = _require_env("INTER_CLOUD_TOKEN")

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def lambda_handler(event, context):
    # 1. Validate Token
    headers = event.get("headers", {})
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

    # 2. Write to DynamoDB
    try:
        body = json.loads(event.get("body", "{}"))
        
        # Log source cloud for debugging/auditing
        source_cloud = body.get("source_cloud", "unknown")
        print(f"Received data from source cloud: {source_cloud}")
        
        actual_event = body.get("payload")  # Expecting wrapper
        
        # Fallback if raw data sent directly (for flexibility)
        data_to_write = actual_event if actual_event else body 
        
        # Basic validation: ensure it's a dict
        if not isinstance(data_to_write, dict):
            raise ValueError("Data payload must be a JSON object.")

        table.put_item(Item=data_to_write)
        print("Data persisted to DynamoDB.")
        
    except ValueError as e:
        print(f"Validation Error: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps(f"Bad Request: {str(e)}")
        }
    except Exception as e:
        print(f"Error writing to DB: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Internal Server Error: {str(e)}")
        }

    return {
        "statusCode": 200,
        "body": json.dumps("Data persisted successfully.")
    }
