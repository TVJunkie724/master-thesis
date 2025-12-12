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


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
REMOTE_INGESTION_URL = require_env("REMOTE_INGESTION_URL")
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")


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
        print(f"Forwarding to remote ingestion: {REMOTE_INGESTION_URL}")
        
        result = post_to_remote(
            url=REMOTE_INGESTION_URL,
            token=INTER_CLOUD_TOKEN,
            payload=event,
            target_layer="L2"
        )
        
        print(f"Remote ingestion response: {result['statusCode']}")
        
        return (json.dumps({"status": "forwarded", "remote_status": result["statusCode"]}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Connector Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
