"""
Connector GCP Cloud Function.

[Multi-Cloud Only] Wraps events and POSTs to remote Ingestion API.
Only created if Layer 2 is on a different cloud provider.

Source: src/providers/gcp/cloud_functions/connector/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import functions_framework

# Handle import path for both Cloud Functions (deployed with _shared) and test contexts
try:
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None
_remote_ingestion_url = None
_inter_cloud_token = None

def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_remote_ingestion_url():
    global _remote_ingestion_url
    if _remote_ingestion_url is None:
        _remote_ingestion_url = require_env("REMOTE_INGESTION_URL")
    return _remote_ingestion_url

def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token


@functions_framework.http
def main(request):
    """
    Connect to remote L2 ingestion endpoint.
    
    Wraps event in inter-cloud envelope and POSTs to remote cloud.
    """
    print("Hello from Connector!")
    
    try:
        event = request.get_json()
        print("Event: " + json.dumps(event))
        
        # POST to remote Ingestion API
        remote_url = _get_remote_ingestion_url()
        print(f"Forwarding to remote ingestion: {remote_url}")
        
        result = post_to_remote(
            url=remote_url,
            token=_get_inter_cloud_token(),
            payload=event,
            target_layer="L2"
        )
        
        print(f"Remote ingestion response: {result['statusCode']}")
        
        return (json.dumps({"status": "forwarded", "remote_status": result["statusCode"]}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Connector Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})

