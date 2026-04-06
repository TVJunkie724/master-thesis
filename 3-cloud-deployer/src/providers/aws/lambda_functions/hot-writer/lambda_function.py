import json
import os
import sys
import traceback
import math
from decimal import Decimal
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
DYNAMODB_TABLE_NAME = require_env("DYNAMODB_TABLE_NAME")
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def _convert_floats_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB compatibility.
    
    DynamoDB does not support Python float type. This function handles:
    - Nested dicts and lists
    - NaN/Infinity (filtered to None to avoid Decimal errors)
    - Bool vs int distinction (bool checked first)
    """
    if isinstance(obj, bool):
        return obj  # Must check before int (bool is subclass of int)
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None  # DynamoDB can't store NaN/Inf
        return Decimal(str(obj))  # str() preserves precision
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(i) for i in obj]
    return obj


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

        # Validate ID field (should come from persister)
        if "id" not in data_to_write:
            print("WARNING: Received item without 'id' field. Source persister may need fixing.")

        # Convert floats to Decimal (DynamoDB requirement)
        data_to_write = _convert_floats_to_decimal(data_to_write)

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
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps(f"Internal Server Error: {str(e)}")
        }

    return {
        "statusCode": 200,
        "body": json.dumps("Data persisted successfully.")
    }
