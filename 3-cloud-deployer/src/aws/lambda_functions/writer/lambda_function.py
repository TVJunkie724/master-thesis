import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def lambda_handler(event, context):
    # 1. Validate Token
    expected_token = os.environ.get("INTER_CLOUD_TOKEN")
    headers = event.get("headers", {})
    incoming_token = None
    for k, v in headers.items():
        if k.lower() == "x-inter-cloud-token":
            incoming_token = v
            break
            
    if incoming_token != expected_token:
        return {
            "statusCode": 403,
            "body": json.dumps("Unauthorized: Invalid Token")
        }

    # 2. Write to DynamoDB
    try:
        body = json.loads(event.get("body", "{}"))
        actual_event = body.get("payload") # Expecting wrapper, or we can support raw if desired. Plan said wrapper.
        
        # Fallback if raw data sent directly (for flexibility)
        data_to_write = actual_event if actual_event else body 
        
        # Basic validation: ensure it's a dict
        if not isinstance(data_to_write, dict):
             raise ValueError("Data payload must be a JSON object.")

        table.put_item(Item=data_to_write)
        
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
