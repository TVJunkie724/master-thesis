"""
Ingestion GCP Cloud Function.

[Multi-Cloud Only] HTTP trigger that receives events from remote Connector.
Only created if Layer 1 is on a different cloud provider.

Source: src/providers/gcp/cloud_functions/ingestion/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import requests
import functions_framework

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


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")
FUNCTION_BASE_URL = require_env("FUNCTION_BASE_URL")


@functions_framework.http
def main(request):
    """
    Receive events from remote L1 and invoke local processor.
    
    Validates inter-cloud token before processing.
    """
    print("Hello from Ingestion!")
    
    # Validate token
    if not validate_token(request, INTER_CLOUD_TOKEN):
        return build_auth_error_response()
    
    try:
        envelope = request.get_json()
        print("Envelope: " + json.dumps(envelope))
        
        # Extract payload from envelope
        payload = envelope.get("payload", envelope)
        
        # Get device ID to route to correct processor
        device_id = payload.get("iotDeviceId")
        if not device_id:
            return (json.dumps({"error": "Missing iotDeviceId in payload"}), 400, {"Content-Type": "application/json"})
        
        # Invoke local processor
        twin_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"]
        processor_name = f"{twin_name}-{device_id}-processor"
        processor_url = f"{FUNCTION_BASE_URL}/{processor_name}"
        
        print(f"Invoking local processor: {processor_url}")
        
        response = requests.post(
            processor_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Processor response: {response.status_code}")
        
        return (json.dumps({"status": "ingested", "processor_status": response.status_code}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Ingestion Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
