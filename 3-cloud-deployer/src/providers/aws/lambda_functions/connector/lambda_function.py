import json
import os
import boto3
import urllib.request
import time
import uuid
from datetime import datetime, timezone


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
REMOTE_INGESTION_URL = _require_env("REMOTE_INGESTION_URL")
INTER_CLOUD_TOKEN = _require_env("INTER_CLOUD_TOKEN")


def lambda_handler(event, context):
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
        'X-Inter-Cloud-Token': INTER_CLOUD_TOKEN
    }
    
    req = urllib.request.Request(REMOTE_INGESTION_URL, data=data, headers=headers)
    
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
