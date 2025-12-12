"""
Default Processor GCP Cloud Function.

Default processing logic template that passes events through unchanged.
Users customize this file with their own processing logic.

Source: src/providers/gcp/cloud_functions/default-processor/main.py
Editable: Yes - Users customize this file
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
PERSISTER_FUNCTION_URL = require_env("PERSISTER_FUNCTION_URL")


def process(event):
    """
    Process the incoming IoT event.
    Override this function with custom processing logic.
    """
    payload = event.copy()
    payload["pressure"] = 20  # Example: Add default pressure value
    return payload


@functions_framework.http
def main(request):
    """Default processor entry point."""
    print("Hello from Default Processor!")
    
    try:
        event = request.get_json()
        print("Event: " + json.dumps(event))
        
        payload = process(event)
        
        # Invoke Persister
        response = requests.post(
            PERSISTER_FUNCTION_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Persister invoked: {response.status_code}")
        
        return (json.dumps({"status": "processed", "result": payload}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Default Processor Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
