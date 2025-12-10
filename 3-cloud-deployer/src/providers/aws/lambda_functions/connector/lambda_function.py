import json
import os
import boto3
import urllib.request
import urllib.parse
import time
import uuid
from datetime import datetime, timezone

def lambda_handler(event, context):
    remote_url = os.environ.get("REMOTE_INGESTION_URL")
    token = os.environ.get("INTER_CLOUD_TOKEN")
    
    if not remote_url or not token:
        raise ValueError("Missing configuration: REMOTE_INGESTION_URL or INTER_CLOUD_TOKEN")

    payload = {
        "source_cloud": "aws",                                
        "target_layer": "L2",                                 # TODO: Make configurable
        "message_type": "telemetry",                          # TODO: Support other types
        "timestamp": datetime.now(timezone.utc).isoformat(),  # Current UTC
        "payload": event,
        "trace_id": str(uuid.uuid4())                         # Unique trace ID
    }
    
    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'X-Inter-Cloud-Token': token
    }
    
    req = urllib.request.Request(remote_url, data=data, headers=headers)
    
    # Retry Logic (Exponential Backoff)
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req) as response:
                return {
                    "statusCode": response.getcode(),
                    "body": response.read().decode('utf-8')
                }
        except urllib.error.HTTPError as e:
            # client error: Do not retry
            if 400 <= e.code < 500:
                print(f"Client Error ({e.code}): {e.reason}. Not Retrying.")
                raise e # Fail fast
            
            # server error: Retry
            if attempt < max_retries:
                 print(f"Server Error ({e.code}): {e.reason}. Retrying in {retry_delay}s...")
                 time.sleep(retry_delay)
                 retry_delay *= 2
            else:
                 raise e

        except Exception as e:
            # Network/Connection error
            if attempt < max_retries:
                print(f"Connection Attempt {attempt+1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"All attempts failed. Error: {e}")
                raise e
