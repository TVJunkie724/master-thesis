"""
Cold Writer GCP Cloud Function.

[Multi-Cloud Only] HTTP trigger that receives data from remote Hot-to-Cold Mover
and writes to local Cloud Storage (Nearline - Cold Storage).

Source: src/providers/gcp/cloud_functions/cold-writer/main.py
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


# Required environment variables
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")
COLD_BUCKET_NAME = require_env("COLD_BUCKET")

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
    Receive data from remote Mover and write to Cloud Storage (Nearline).
    """
    print("Hello from Cold Writer!")
    
    # Validate token
    if not validate_token(request, INTER_CLOUD_TOKEN):
        return build_auth_error_response()
    
    try:
        payload = request.get_json()
        print("Payload received")
        
        device_id = payload.get("iot_device_id") or payload.get("iotDeviceId", "unknown")
        items = payload.get("items", [])
        start_time = payload.get("startTimestamp", "")
        end_time = payload.get("endTimestamp", "")
        chunk_index = payload.get("chunkIndex", 0)
        
        if not items:
            return (json.dumps({"error": "No items in payload"}), 400, {"Content-Type": "application/json"})
        
        # Write to Cloud Storage
        client = _get_storage_client()
        bucket = client.bucket(COLD_BUCKET_NAME)
        
        blob_name = f"{device_id}/{start_time}_to_{end_time}_chunk{chunk_index}.json"
        blob = bucket.blob(blob_name)
        blob.storage_class = "NEARLINE"
        
        blob.upload_from_string(
            json.dumps(items, default=str),
            content_type="application/json"
        )
        
        print(f"Written to GCS: {blob_name} ({len(items)} items)")
        
        return (json.dumps({"status": "written", "blob": blob_name, "count": len(items)}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Cold Writer Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
