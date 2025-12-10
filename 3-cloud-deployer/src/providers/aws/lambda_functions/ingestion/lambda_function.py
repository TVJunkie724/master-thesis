import json
import os
import boto3

lambda_client = boto3.client("lambda")

DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", "{}"))

def lambda_handler(event, context):
    # 1. Validate Token
    expected_token = os.environ.get("INTER_CLOUD_TOKEN")
    # API Gateway/Lambda Function URL headers are case-insensitive, usually lower-cased
    headers = event.get("headers", {})
    # Look for token (case-insensitive)
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
