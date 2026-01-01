"""
Hot Reader Last Entry GCP Cloud Function.

Gets the last (most recent) entry per device from Firestore.
Optimized for digital twin "current state" queries.

TODO: Add Digital Twin query format support for parity with AWS/Azure.
      AWS & Azure support TwinMaker/ADT query format (entityId, componentName, 
      selectedProperties) and return propertyValues structure. This function
      currently uses a simpler iotDeviceId parameter and returns raw items.
      Consider adding optional "twin_query_mode" to support both formats.

Source: src/providers/gcp/cloud_functions/hot-reader-last-entry/main.py
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
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import validate_token, build_auth_error_response


# Optional - for protected endpoints
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "")
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
    Get the last entry for a device.
    
    Query parameters:
        iotDeviceId: Device ID to get last entry for (required)
    """
    print("Hello from Hot Reader Last Entry!")
    
    # Validate token if configured
    if INTER_CLOUD_TOKEN:
        if not validate_token(request, INTER_CLOUD_TOKEN):
            return build_auth_error_response()
    
    try:
        # Get device ID from query params
        device_id = request.args.get("device_id") or request.args.get("iotDeviceId")
        
        if not device_id:
            return (json.dumps({"error": "Missing device_id parameter"}), 400, {"Content-Type": "application/json"})
        
        db = _get_firestore_client()
        
        # Query for last entry (ordered by id/time descending, limit 1)
        query = (
            db.collection(FIRESTORE_COLLECTION)
            .where("device_id", "==", device_id)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        
        docs = list(query.stream())
        
        if not docs:
            return (json.dumps({"item": None, "message": "No entries found"}), 200, {"Content-Type": "application/json"})
        
        item = docs[0].to_dict()
        print(f"Last entry for {device_id}: {item.get('id')}")
        
        return (json.dumps({"item": item}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Hot Reader Last Entry Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
