import json
import os
import boto3
from process import process  # User logic import

lambda_client = boto3.client("lambda")
PERSISTER_LAMBDA_NAME = os.environ.get("PERSISTER_LAMBDA_NAME")

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
        if PERSISTER_LAMBDA_NAME:
            lambda_client.invoke(
                FunctionName=PERSISTER_LAMBDA_NAME, 
                InvocationType="Event", 
                Payload=json.dumps(processed_event).encode("utf-8")
            )
        else:
            print("Warning: PERSISTER_LAMBDA_NAME not set. Data not persisted.")
    except Exception as e:
        print(f"[SYSTEM_ERROR] Persister Invocation failed: {e}")
        raise e
        
    return processed_event
