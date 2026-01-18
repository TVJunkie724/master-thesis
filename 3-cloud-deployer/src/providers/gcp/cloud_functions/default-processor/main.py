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
_persister_function_url = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_persister_function_url():
    """Lazy-load PERSISTER_FUNCTION_URL to avoid import-time failures."""
    global _persister_function_url
    if _persister_function_url is None:
        _persister_function_url = require_env("PERSISTER_FUNCTION_URL")
    return _persister_function_url


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
            _get_persister_function_url(),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Persister invoked: {response.status_code}")
        
        return (json.dumps({"status": "processed", "result": payload}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Default Processor Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})

