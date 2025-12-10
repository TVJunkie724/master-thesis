"""
Hot-to-Cold Mover Lambda Function.

Moves data from DynamoDB (Hot Storage) to S3 Cold Storage.
Supports multi-cloud: If L3 Cold is on different cloud, POSTs to remote Cold Writer.

Source: src/providers/aws/lambda_functions/hot-to-cold-mover/lambda_function.py
Editable: Yes - This is the runtime Lambda code
"""
import boto3
import os
import json
import datetime
import time
import urllib.request
import urllib.error
from boto3.dynamodb.conditions import Key


# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

def _require_env(name: str) -> str:
    """Get required environment variable or raise RuntimeError."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


# Validate at startup
_raw_twin_info = os.environ.get("DIGITAL_TWIN_INFO")
if not _raw_twin_info:
    raise RuntimeError("Required environment variable 'DIGITAL_TWIN_INFO' is not set")
DIGITAL_TWIN_INFO = json.loads(_raw_twin_info)

DYNAMODB_TABLE_NAME = _require_env("DYNAMODB_TABLE_NAME")
COLD_S3_BUCKET_NAME = _require_env("COLD_S3_BUCKET_NAME")

# Multi-cloud config (optional)
REMOTE_COLD_WRITER_URL = os.environ.get("REMOTE_COLD_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# AWS clients
dynamodb_client = boto3.resource("dynamodb")
dynamodb_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)
s3_client = boto3.client("s3")

# Constants
MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds


# ==========================================
# Multi-Cloud Detection
# ==========================================

class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


def _is_multi_cloud_cold() -> bool:
    """
    Check if L3 Cold storage is on a different cloud.
    
    Returns True only if:
    1. REMOTE_COLD_WRITER_URL is set AND non-empty
    2. layer_3_hot_provider != layer_3_cold_provider in DIGITAL_TWIN_INFO
    """
    if not REMOTE_COLD_WRITER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        raise ConfigurationError(
            "CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO. "
            "Ensure deployer injects config.providers into DIGITAL_TWIN_INFO."
        )
    
    l3_hot = providers.get("layer_3_hot_provider")
    l3_cold = providers.get("layer_3_cold_provider")
    
    if l3_hot is None or l3_cold is None:
        raise ConfigurationError(
            f"CRITICAL: Missing provider mapping. "
            f"layer_3_hot_provider={l3_hot}, layer_3_cold_provider={l3_cold}"
        )
    
    if l3_hot == l3_cold:
        print(f"Warning: REMOTE_COLD_WRITER_URL set but providers match ({l3_hot}). Using local S3.")
        return False
    
    return True


# ==========================================
# 5MB Chunking for Multi-Cloud
# ==========================================

def _estimate_json_size(items: list) -> int:
    """Estimate JSON byte size of items list."""
    return len(json.dumps(items, default=str).encode('utf-8'))


def _chunk_items(items: list, max_bytes: int = MAX_CHUNK_SIZE_BYTES) -> list:
    """
    Split items into chunks of max_bytes.
    
    Returns list of (chunk_items, chunk_index) tuples.
    """
    if not items:
        return []
    
    chunks = []
    current_chunk = []
    current_size = 2  # Start with empty array "[]"
    
    for item in items:
        item_json = json.dumps(item, default=str)
        item_size = len(item_json.encode('utf-8')) + 1  # +1 for comma
        
        if current_size + item_size > max_bytes and current_chunk:
            # Current chunk is full, start new one
            chunks.append(current_chunk)
            current_chunk = [item]
            current_size = 2 + item_size
        else:
            current_chunk.append(item)
            current_size += item_size
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return [(chunk, idx) for idx, chunk in enumerate(chunks)]


# ==========================================
# Remote POST with Retry
# ==========================================

def _post_to_remote_cold_writer(
    iot_device_id: str,
    items: list,
    start_timestamp: str,
    end_timestamp: str,
    chunk_index: int
) -> None:
    """
    POST chunk to remote Cold Writer with exponential backoff retry.
    """
    if not INTER_CLOUD_TOKEN:
        raise ValueError("INTER_CLOUD_TOKEN is required for multi-cloud transfers")
    
    payload = {
        "iot_device_id": iot_device_id,
        "chunk_index": chunk_index,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "items": items,
        "source_cloud": "aws"
    }
    
    data = json.dumps(payload, default=str).encode('utf-8')
    
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                REMOTE_COLD_WRITER_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Inter-Cloud-Token": INTER_CLOUD_TOKEN
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                status = response.getcode()
                if status == 200:
                    print(f"Successfully posted chunk {chunk_index} ({len(items)} items) to remote Cold Writer")
                    return
                else:
                    raise urllib.error.HTTPError(
                        REMOTE_COLD_WRITER_URL, status, f"Unexpected status: {status}", {}, None
                    )
                    
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                # Client error - don't retry
                print(f"Client error {e.code} posting to Cold Writer: {e.reason}")
                raise
            else:
                # Server error - retry
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"Server error {e.code}, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(delay)
                else:
                    print(f"Max retries exceeded for Cold Writer POST")
                    raise
                    
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"Network error: {e.reason}, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            else:
                print(f"Max retries exceeded for Cold Writer POST")
                raise


# ==========================================
# Local S3 Write
# ==========================================

def _write_to_local_s3(iot_device_id: str, items: list, start: str, end: str, chunk_index: int) -> None:
    """Write chunk to local S3 Cold bucket."""
    if not items:
        return

    key = f"{iot_device_id}/{start}-{end}/chunk-{chunk_index:05d}.json"
    body = json.dumps(items, default=str)

    s3_client.put_object(
        Bucket=COLD_S3_BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType="application/json",
        StorageClass="STANDARD_IA"
    )

    print(f"Wrote {len(items)} items to s3://{COLD_S3_BUCKET_NAME}/{key}")


# ==========================================
# Main Handler
# ==========================================

def lambda_handler(event, context):
    print("Hot-to-Cold Mover: Starting")
    print(f"Event: {json.dumps(event)}")
    
    # Detect multi-cloud mode
    multi_cloud = _is_multi_cloud_cold()
    if multi_cloud:
        print(f"Multi-cloud mode: Posting to {REMOTE_COLD_WRITER_URL}")
    else:
        print(f"Single-cloud mode: Writing to s3://{COLD_S3_BUCKET_NAME}")

    try:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=DIGITAL_TWIN_INFO["config"]["hot_storage_size_in_days"]
        )
        cutoff_iso = cutoff.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        print(f"Moving items older than: {cutoff_iso}")

        with dynamodb_table.batch_writer() as batch:
            for iot_device in DIGITAL_TWIN_INFO["config_iot_devices"]:
                device_id = iot_device["id"]
                
                # Get end timestamp (most recent item to move)
                response = dynamodb_table.query(
                    KeyConditionExpression=Key("iotDeviceId").eq(device_id) &
                                           Key("id").lt(cutoff_iso),
                    ScanIndexForward=False,
                    Limit=1
                )
                items = response.get("Items", [])

                if not items:
                    continue

                end_timestamp = items[0]["id"]

                # Get all items to move (ascending order)
                response = dynamodb_table.query(
                    KeyConditionExpression=Key("iotDeviceId").eq(device_id) &
                                           Key("id").lt(cutoff_iso),
                    ScanIndexForward=True
                )
                items = response.get("Items", [])

                if not items:
                    continue

                start_timestamp = items[0]["id"]
                
                # Process in chunks
                chunk_index = 0
                while items:
                    # For multi-cloud, chunk to 5MB
                    if multi_cloud:
                        chunked = _chunk_items(items)
                        for chunk_items, sub_index in chunked:
                            _post_to_remote_cold_writer(
                                device_id, chunk_items, 
                                start_timestamp, end_timestamp, 
                                chunk_index + sub_index
                            )
                        chunk_index += len(chunked)
                    else:
                        # Single cloud: write directly
                        _write_to_local_s3(device_id, items, start_timestamp, end_timestamp, chunk_index)
                        chunk_index += 1

                    # Delete from DynamoDB
                    for item in items:
                        batch.delete_item(
                            Key={
                                "iotDeviceId": item["iotDeviceId"],
                                "id": item["id"],
                            }
                        )
                    print(f"Deleted {len(items)} items from DynamoDB")

                    # Check for more pages
                    if "LastEvaluatedKey" not in response:
                        break

                    response = dynamodb_table.query(
                        KeyConditionExpression=Key("iotDeviceId").eq(device_id) &
                                               Key("id").lt(cutoff_iso),
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                    items = response.get("Items", [])
                    
    except Exception as e:
        print(f"Hot-to-Cold Mover Error: {e}")
        raise e
    
    print("Hot-to-Cold Mover: Complete")

