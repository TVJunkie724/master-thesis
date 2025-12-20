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


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None
_inter_cloud_token = None
_function_base_url = None

def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token

def _get_function_base_url():
    global _function_base_url
    if _function_base_url is None:
        _function_base_url = require_env("FUNCTION_BASE_URL")
    return _function_base_url


@functions_framework.http
def main(request):
    """
    Receive events from remote L1 and invoke local processor.
    
    Validates inter-cloud token before processing.
    """
    print("Hello from Ingestion!")
    
    # Validate token
    if not validate_token(request, _get_inter_cloud_token()):
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
        twin_name = _get_digital_twin_info()["config"]["digital_twin_name"]
        processor_name = f"{twin_name}-{device_id}-processor"
        processor_url = f"{_get_function_base_url()}/{processor_name}"
        
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

