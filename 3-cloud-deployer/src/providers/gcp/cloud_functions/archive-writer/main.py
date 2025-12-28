"""
Archive Writer GCP Cloud Function.

[Multi-Cloud Only] HTTP trigger that receives data from remote Cold-to-Archive Mover
and writes to local Cloud Storage (Archive class).

Source: src/providers/gcp/cloud_functions/archive-writer/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import traceback
import functions_framework
from google.cloud import storage

# Handle import path for both Cloud Functions and test contexts
try:
    from _shared.inter_cloud import validate_token, build_auth_error_response
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import validate_token, build_auth_error_response
    from _shared.env_utils import require_env


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_inter_cloud_token = None
_archive_bucket_name = None

def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token

def _get_archive_bucket_name():
    global _archive_bucket_name
    if _archive_bucket_name is None:
        _archive_bucket_name = require_env("ARCHIVE_BUCKET")
    return _archive_bucket_name

# Storage client
_storage_client = None


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


@functions_framework.http
def main(request):
    """
    Receive data from remote Mover and write to Cloud Storage (Archive class).
    """
    print("Hello from Archive Writer!")
    
    # Validate token
    if not validate_token(request, _get_inter_cloud_token()):
        return build_auth_error_response()
    
    try:
        payload = request.get_json()
        print("Payload received")
        
        blob_name = payload.get("blobName", "")
        items = payload.get("items", [])
        
        if not blob_name or not items:
            return (json.dumps({"error": "Missing blobName or items"}), 400, {"Content-Type": "application/json"})
        
        # Write to Cloud Storage with Archive class
        client = _get_storage_client()
        bucket = client.bucket(_get_archive_bucket_name())
        
        blob = bucket.blob(blob_name)
        blob.storage_class = "ARCHIVE"
        
        blob.upload_from_string(
            json.dumps(items, default=str),
            content_type="application/json"
        )
        
        print(f"Written to archive: {blob_name} ({len(items)} items)")
        
        return (json.dumps({"status": "archived", "blob": blob_name, "count": len(items)}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Archive Writer Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
