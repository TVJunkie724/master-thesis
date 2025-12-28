"""
Dispatcher GCP Cloud Function.

Routes incoming Pub/Sub events to device-specific processor functions.
Triggered by Eventarc from Pub/Sub topics.

Source: src/providers/gcp/cloud_functions/dispatcher/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import traceback
import requests
import functions_framework

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.env_utils import require_env


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None
_function_base_url = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_function_base_url():
    """Lazy-load FUNCTION_BASE_URL to avoid import-time failures."""
    global _function_base_url
    if _function_base_url is None:
        _function_base_url = require_env("FUNCTION_BASE_URL")
    return _function_base_url

# Target function suffix is used to identify the target function, can be either "-processor" or "-connector"
TARGET_FUNCTION_SUFFIX = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")


@functions_framework.http
def main(request):
    """
    Dispatch incoming events to device-specific processor.
    
    Triggered by Pub/Sub via Eventarc or HTTP for testing.
    """
    print("Hello from Dispatcher!")
    
    try:
        event = request.get_json()
        print("Event: " + json.dumps(event))
        
        # Extract ID
        device_id = event.get("iotDeviceId")
        if not device_id:
            print("Error: 'iotDeviceId' missing in event.")
            return (json.dumps({"error": "Missing iotDeviceId"}), 400, {"Content-Type": "application/json"})
        
        # Construct target function name
        # For multi-cloud connector: {twin_name}-connector (no device_id)
        # For single-cloud processor: {twin_name}-{device_id}-processor
        twin_name = _get_digital_twin_info()["config"]["digital_twin_name"]
        if TARGET_FUNCTION_SUFFIX == "-connector":
            # Multi-cloud: route to connector (no device-specific naming)
            function_name = f"{twin_name}-connector"
        else:
            # Single-cloud: route to processor wrapper (which then calls user processor)
            function_name = f"{twin_name}-processor"
        
        print(f"Dispatching to: {function_name}")
        
        # Invoke target function via HTTP POST
        target_url = f"{_get_function_base_url()}/{function_name}"
        response = requests.post(
            target_url,
            json=event,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Dispatch successful. Response: {response.status_code}")
        
        return (json.dumps({"status": "dispatched", "target": function_name}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Dispatcher Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})

