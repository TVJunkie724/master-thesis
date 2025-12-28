"""
Processor Wrapper GCP Cloud Function.

Calls user-defined processor function via HTTP and invokes the Persister.
Dynamically constructs processor URL from device ID.

Architecture:
    Ingestion → Processor Wrapper → HTTP → User Processor → Wrapper → Persister

Source: src/providers/gcp/cloud_functions/processor_wrapper/main.py
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
_persister_function_url = None
_digital_twin_info = None

def _get_persister_function_url():
    """Lazy-load PERSISTER_FUNCTION_URL to avoid import-time failures."""
    global _persister_function_url
    if _persister_function_url is None:
        _persister_function_url = require_env("PERSISTER_FUNCTION_URL")
    return _persister_function_url

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_processor_url(device_id: str) -> str:
    """Construct processor URL dynamically from device ID."""
    twin_name = _get_digital_twin_info()["config"]["digital_twin_name"]
    processor_name = f"{twin_name}-{device_id}-processor"
    base_url = os.environ.get("FUNCTION_APP_BASE_URL", "")
    return f"{base_url}/api/{processor_name}"


@functions_framework.http
def main(request):
    """
    Call user processor via HTTP and invoke Persister.
    
    Dynamically constructs the processor URL from the device ID in the event,
    calls the user's processor function, then sends the result to Persister.
    """
    print("GCP Processor Wrapper: Executing user logic...")
    
    try:
        # Parse input event
        event = request.get_json()
        
        # 1. Call User Processor via HTTP
        device_id = event.get("iotDeviceId", "default")
        try:
            url = _get_processor_url(device_id)
            if not url or not url.startswith("http"):
                raise ValueError(f"Cannot construct valid processor URL for device {device_id} (Base URL: {os.environ.get('FUNCTION_APP_BASE_URL')})")

            else:
                print(f"Calling user processor at {url}")
                response = requests.post(url, json=event, headers={"Content-Type": "application/json"}, timeout=30)
                response.raise_for_status()
                processed_event = response.json()
                print(f"User Logic Complete. Result: {json.dumps(processed_event)}")
        except Exception as e:
            print(f"[USER_LOGIC_ERROR] Processing failed: {e}")
            traceback.print_exc()
            return (json.dumps({"error": "User logic error", "message": str(e)}), 500, {"Content-Type": "application/json"})
        
        # 2. Invoke Persister
        response = requests.post(
            _get_persister_function_url(),
            json=processed_event,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Persister invoked: {response.status_code}")
        
        return (json.dumps({"status": "processed", "result": processed_event}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"[SYSTEM_ERROR] Processor error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": "System error", "message": str(e)}), 500, {"Content-Type": "application/json"})

