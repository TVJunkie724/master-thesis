"""
Hot-to-Cold Mover Lambda Function.

Moves data from DynamoDB (Hot Storage) to S3 Cold Storage.
Supports multi-cloud: If L3 Cold is on different cloud, POSTs to remote Cold Writer.

Source: src/providers/aws/lambda_functions/hot-to-cold-mover/lambda_function.py
Editable: Yes - This is the runtime Lambda code
"""
import boto3
import os
import sys
import json
import traceback
import datetime
from boto3.dynamodb.conditions import Key

# Handle import path for both Lambda (deployed with _shared) and test (local development) contexts
try:
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env


# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

# Validate at startup
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

DYNAMODB_TABLE_NAME = require_env("DYNAMODB_TABLE_NAME")
COLD_S3_BUCKET_NAME = require_env("COLD_S3_BUCKET_NAME")

# Multi-cloud config (optional)
REMOTE_COLD_WRITER_URL = os.environ.get("REMOTE_COLD_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# AWS clients
dynamodb_client = boto3.resource("dynamodb")
dynamodb_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)
s3_client = boto3.client("s3")

# Constants
MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


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
        raise ConfigurationError(f"REMOTE_COLD_WRITER_URL set but providers match ({l3_hot}). Invalid multi-cloud config.")
    
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
# Remote POST with Retry (using shared module)
# ==========================================

def _post_to_remote_cold_writer(
    iot_device_id: str,
    items: list,
    start_timestamp: str,
    end_timestamp: str,
    chunk_index: int
) -> None:
    """
    POST chunk to remote Cold Writer using shared inter_cloud module.
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
    
    result = post_raw(
        url=REMOTE_COLD_WRITER_URL,
        token=INTER_CLOUD_TOKEN,
        payload=payload
    )
    
    print(f"Successfully posted chunk {chunk_index} ({len(items)} items) to remote Cold Writer")


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
                    KeyConditionExpression=Key("device_id").eq(device_id) &
                                           Key("timestamp").lt(cutoff_iso),
                    ScanIndexForward=False,
                    Limit=1
                )
                items = response.get("Items", [])

                if not items:
                    continue

                end_timestamp = items[0]["timestamp"]

                # Get all items to move (ascending order)
                response = dynamodb_table.query(
                    KeyConditionExpression=Key("device_id").eq(device_id) &
                                           Key("timestamp").lt(cutoff_iso),
                    ScanIndexForward=True
                )
                items = response.get("Items", [])

                if not items:
                    continue

                start_timestamp = items[0]["timestamp"]
                
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
                                "device_id": item["device_id"],
                                "timestamp": item["timestamp"],
                            }
                        )
                    print(f"Deleted {len(items)} items from DynamoDB")

                    # Check for more pages
                    if "LastEvaluatedKey" not in response:
                        break

                    response = dynamodb_table.query(
                        KeyConditionExpression=Key("device_id").eq(device_id) &
                                               Key("timestamp").lt(cutoff_iso),
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                    items = response.get("Items", [])
                    
    except Exception as e:
        print(f"Hot-to-Cold Mover Error: {e}")
        traceback.print_exc()
        raise e
    
    print("Hot-to-Cold Mover: Complete")

