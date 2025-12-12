"""
Processor Wrapper GCP Cloud Function.

Merges user-defined processing logic with the system pipeline.
Executes user logic and then invokes the Persister.

Architecture:
    Ingestion → Processor (user logic) → Persister

Source: src/providers/gcp/cloud_functions/processor_wrapper/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import requests
import functions_framework
from process import process  # User logic import

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
PERSISTER_FUNCTION_URL = require_env("PERSISTER_FUNCTION_URL")


@functions_framework.http
def main(request):
    """
    Execute user processing logic and invoke Persister.
    
    This function wraps user-defined `process()` logic with the
    system pipeline, ensuring processed data flows to storage.
    """
    print("GCP Processor Wrapper: Executing user logic...")
    
    try:
        # Parse input event
        event = request.get_json()
        
        # 1. Execute User Logic
        try:
            processed_event = process(event)
            print(f"User Logic Complete. Result: {json.dumps(processed_event)}")
        except Exception as e:
            print(f"[USER_LOGIC_ERROR] Processing failed: {e}")
            return (json.dumps({"error": "User logic error", "message": str(e)}), 500, {"Content-Type": "application/json"})
        
        # 2. Invoke Persister
        response = requests.post(
            PERSISTER_FUNCTION_URL,
            json=processed_event,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Persister invoked: {response.status_code}")
        
        return (json.dumps({"status": "processed", "result": processed_event}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"[SYSTEM_ERROR] Processor error: {e}")
        return (json.dumps({"error": "System error", "message": str(e)}), 500, {"Content-Type": "application/json"})
