"""
Hot-to-Cold Mover GCP Cloud Function.

Moves data from Firestore (Hot Storage) to Cloud Storage (Nearline - Cold Storage).
Triggered by Cloud Scheduler on a cron schedule.

Source: src/providers/gcp/cloud_functions/hot-to-cold-mover/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
import functions_framework
from google.cloud import firestore
from google.cloud import storage

# Handle import path for both Cloud Functions and test contexts
try:
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


# Required environment variables
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
FIRESTORE_COLLECTION = require_env("FIRESTORE_COLLECTION")
COLD_BUCKET_NAME = require_env("COLD_BUCKET_NAME")

# Multi-cloud config (optional)
REMOTE_COLD_WRITER_URL = os.environ.get("REMOTE_COLD_WRITER_URL", "")
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "")

# Retention period - items older than this are moved
RETENTION_DAYS = int(os.environ.get("HOT_RETENTION_DAYS", "7"))

# Firestore and Storage clients
_firestore_client = None
_storage_client = None

# Constants
MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client()
    return _firestore_client


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def _is_multi_cloud_cold() -> bool:
    """Check if L3 Cold storage is on a different cloud."""
    if not REMOTE_COLD_WRITER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        return False
    
    l3_hot = providers.get("layer_3_hot_provider")
    l3_cold = providers.get("layer_3_cold_provider")
    
    return l3_hot != l3_cold


def _chunk_items(items: list, max_bytes: int = MAX_CHUNK_SIZE_BYTES) -> list:
    """Split items into chunks of max_bytes."""
    chunks = []
    current_chunk = []
    current_size = 0
    
    for item in items:
        item_size = len(json.dumps(item).encode('utf-8'))
        
        if current_size + item_size > max_bytes and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0
        
        current_chunk.append(item)
        current_size += item_size
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def _write_to_local_gcs(device_id: str, items: list, start: str, end: str, chunk_index: int):
    """Write chunk to local Cloud Storage (Nearline class)."""
    client = _get_storage_client()
    bucket = client.bucket(COLD_BUCKET_NAME)
    
    blob_name = f"{device_id}/{start}_to_{end}_chunk{chunk_index}.json"
    blob = bucket.blob(blob_name)
    
    # Set storage class to NEARLINE
    blob.storage_class = "NEARLINE"
    
    blob.upload_from_string(
        json.dumps(items, default=str),
        content_type="application/json"
    )
    
    print(f"Written to GCS: {blob_name} ({len(items)} items)")


@functions_framework.http
def main(request):
    """
    Move old data from Firestore to Cloud Storage (Nearline).
    
    Triggered by Cloud Scheduler.
    """
    print("Hello from Hot-to-Cold Mover!")
    
    try:
        db = _get_firestore_client()
        
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        cutoff_str = cutoff.isoformat()
        
        print(f"Moving items older than {cutoff_str}")
        
        # Query old items
        query = (
            db.collection(FIRESTORE_COLLECTION)
            .where("id", "<", cutoff_str)
            .order_by("id")
            .limit(1000)  # Process in batches
        )
        
        docs = list(query.stream())
        
        if not docs:
            print("No items to move")
            return (json.dumps({"status": "no_items"}), 200, {"Content-Type": "application/json"})
        
        # Group by device
        items_by_device = {}
        for doc in docs:
            item = doc.to_dict()
            device_id = item.get("iotDeviceId", "unknown")
            if device_id not in items_by_device:
                items_by_device[device_id] = []
            items_by_device[device_id].append(item)
        
        moved_count = 0
        
        for device_id, items in items_by_device.items():
            if not items:
                continue
            
            # Get time range
            sorted_items = sorted(items, key=lambda x: x.get("id", ""))
            start_time = sorted_items[0].get("id", "")
            end_time = sorted_items[-1].get("id", "")
            
            # Chunk and write
            chunks = _chunk_items(items)
            
            for idx, chunk in enumerate(chunks):
                if _is_multi_cloud_cold():
                    # Multi-cloud: POST to remote Cold Writer
                    payload = {
                        "iotDeviceId": device_id,
                        "items": chunk,
                        "startTimestamp": start_time,
                        "endTimestamp": end_time,
                        "chunkIndex": idx
                    }
                    post_raw(
                        url=REMOTE_COLD_WRITER_URL,
                        token=INTER_CLOUD_TOKEN,
                        payload=payload
                    )
                else:
                    # Local: Write to Cloud Storage
                    _write_to_local_gcs(device_id, chunk, start_time, end_time, idx)
                
                moved_count += len(chunk)
        
        # Delete moved items from Firestore
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        
        print(f"Moved {moved_count} items, deleted from Firestore")
        
        return (json.dumps({"status": "moved", "count": moved_count}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Hot-to-Cold Mover Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
