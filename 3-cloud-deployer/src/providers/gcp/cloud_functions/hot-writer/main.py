"""
Hot Writer GCP Cloud Function.

[Multi-Cloud Only] HTTP trigger that receives data from remote Persister
and writes to local Firestore hot storage.

Source: src/providers/gcp/cloud_functions/hot-writer/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import traceback
import functions_framework
from google.cloud import firestore

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

def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token

FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "hot_data")
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "(default)")

# Firestore client
_firestore_client = None


def _get_firestore_client():
    """Lazy initialization of Firestore client with named database support."""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(database=FIRESTORE_DATABASE)
    return _firestore_client


@functions_framework.http
def main(request):
    """
    Receive data from remote Persister and write to Firestore.
    """
    print("Hello from Hot Writer!")
    
    # Validate token
    if not validate_token(request, _get_inter_cloud_token()):
        return build_auth_error_response()
    
    try:
        envelope = request.get_json()
        print("Envelope: " + json.dumps(envelope))
        
        # Extract payload from envelope
        item = envelope.get("payload", envelope)
        
        if "id" not in item:
            return (json.dumps({"error": "Missing 'id' in item"}), 400, {"Content-Type": "application/json"})
        
        # Write to Firestore
        db = _get_firestore_client()
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(item["id"])
        doc_ref.set(item)
        
        print(f"Item written to Firestore: {item['id']}")
        
        return (json.dumps({"status": "written", "id": item["id"]}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Hot Writer Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
