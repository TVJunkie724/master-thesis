"""
Hot Reader GCP Cloud Function.

Reads data from Firestore hot storage with time range queries.
Used by Digital Twin Data Connector and API Gateway.

Source: src/providers/gcp/cloud_functions/hot-reader/main.py
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


def _get_inter_cloud_token():
    try:
        return require_env("INTER_CLOUD_TOKEN")
    except Exception:
        # If missing, we must fail secure (cannot authenticate)
        print("CRITICAL: INTER_CLOUD_TOKEN missing. Hot Reader requires authentication.")
        raise ValueError("INTER_CLOUD_TOKEN configuration missing")
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
    Read data from Firestore with time range filtering.
    
    Query parameters:
        iotDeviceId: Device ID to filter by
        startTime: Start of time range (ISO format)
        endTime: End of time range (ISO format)
        limit: Maximum number of results (default 100)
    """
    print("Hello from Hot Reader!")
    
    # Validate token
    # CRITICAL: Security - Always enforce token validation.
    if not validate_token(request, _get_inter_cloud_token()):
        return build_auth_error_response()
    
    try:
        # Get query parameters
        args = request.args
        device_id = args.get("iotDeviceId")
        start_time = args.get("startTime")
        end_time = args.get("endTime")
        limit = int(args.get("limit", 100))
        
        db = _get_firestore_client()
        query = db.collection(FIRESTORE_COLLECTION)
        
        # Apply filters
        if device_id:
            query = query.where("iotDeviceId", "==", device_id)
        
        if start_time:
            query = query.where("id", ">=", start_time)
        
        if end_time:
            query = query.where("id", "<=", end_time)
        
        # Order and limit
        query = query.order_by("id", direction=firestore.Query.DESCENDING).limit(limit)
        
        # Execute query
        docs = query.stream()
        items = [doc.to_dict() for doc in docs]
        
        print(f"Query returned {len(items)} items")
        
        return (json.dumps({"items": items, "count": len(items)}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Hot Reader Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
