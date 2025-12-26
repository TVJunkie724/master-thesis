"""
Cold-to-Archive Mover GCP Cloud Function.

Moves data from Cloud Storage (Nearline) to Archive storage class.
Triggered by Cloud Scheduler on a cron schedule.

Source: src/providers/gcp/cloud_functions/cold-to-archive-mover/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
import functions_framework
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


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None
_cold_bucket_name = None
_archive_bucket_name = None

def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_cold_bucket_name():
    global _cold_bucket_name
    if _cold_bucket_name is None:
        _cold_bucket_name = require_env("COLD_BUCKET_NAME")
    return _cold_bucket_name

def _get_archive_bucket_name():
    global _archive_bucket_name
    if _archive_bucket_name is None:
        _archive_bucket_name = require_env("ARCHIVE_BUCKET_NAME")
    return _archive_bucket_name

# Multi-cloud config (optional)
REMOTE_ARCHIVE_WRITER_URL = os.environ.get("REMOTE_ARCHIVE_WRITER_URL", "")
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "")

# Retention period
COLD_RETENTION_DAYS = int(os.environ.get("COLD_RETENTION_DAYS", "30"))

# Storage client
_storage_client = None


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def _is_multi_cloud_archive() -> bool:
    """Check if Archive storage is on a different cloud."""
    if not REMOTE_ARCHIVE_WRITER_URL:
        return False
    
    providers = _get_digital_twin_info().get("config_providers")
    if providers is None:
        return False
    
    l3_cold = providers.get("layer_3_cold_provider")
    l3_archive = providers.get("layer_3_archive_provider")
    
    if l3_cold == l3_archive:
        raise ConfigurationError(f"REMOTE_ARCHIVE_WRITER_URL set but providers match ({l3_cold}). Invalid multi-cloud config.")

    return True


@functions_framework.http
def main(request):
    """
    Move old data from Nearline to Archive storage class.
    
    Triggered by Cloud Scheduler.
    """
    print("Hello from Cold-to-Archive Mover!")
    
    try:
        client = _get_storage_client()
        cold_bucket = client.bucket(_get_cold_bucket_name())
        archive_bucket = client.bucket(_get_archive_bucket_name())
        
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(days=COLD_RETENTION_DAYS)
        
        print(f"Moving blobs older than {cutoff.isoformat()}")
        
        moved_count = 0
        
        # List blobs in cold bucket
        blobs = list(cold_bucket.list_blobs(max_results=100))
        
        for blob in blobs:
            # Check if blob is old enough
            if blob.time_created and blob.time_created < cutoff:
                if _is_multi_cloud_archive():
                    # Multi-cloud: Download and POST to remote Archive Writer
                    if not INTER_CLOUD_TOKEN:
                        raise ConfigurationError("INTER_CLOUD_TOKEN is required for multi-cloud mode")

                    content = blob.download_as_text()
                    items = json.loads(content)
                    
                    payload = {
                        "blobName": blob.name,
                        "items": items
                    }
                    post_raw(
                        url=REMOTE_ARCHIVE_WRITER_URL,
                        token=INTER_CLOUD_TOKEN,
                        payload=payload
                    )
                else:
                    # Local: Copy to archive bucket with ARCHIVE class
                    archive_blob = archive_bucket.blob(blob.name)
                    archive_blob.storage_class = "ARCHIVE"
                    
                    # Rewrite (copy) the blob
                    archive_blob.rewrite(blob)
                
                # Delete from cold bucket
                blob.delete()
                moved_count += 1
                
                print(f"Moved: {blob.name}")
        
        print(f"Moved {moved_count} blobs to archive")
        
        return (json.dumps({"status": "moved", "count": moved_count}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Cold-to-Archive Mover Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
