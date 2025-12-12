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


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
# Target function suffix is used to identify the target function, can be either "-processor" or "-connector"
TARGET_FUNCTION_SUFFIX = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")
# Base URL for Cloud Functions (e.g., https://REGION-PROJECT.cloudfunctions.net)
FUNCTION_BASE_URL = require_env("FUNCTION_BASE_URL")


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
        # FORMAT: {twin_name}-{device_id}{target_suffix}
        twin_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"]
        function_name = f"{twin_name}-{device_id}{TARGET_FUNCTION_SUFFIX}"
        
        print(f"Dispatching to: {function_name}")
        
        # Invoke target function via HTTP POST
        target_url = f"{FUNCTION_BASE_URL}/{function_name}"
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
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
