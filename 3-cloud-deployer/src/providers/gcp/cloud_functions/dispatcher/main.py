"""
Dispatcher GCP Cloud Function.

Routes incoming Pub/Sub events to device-specific processor functions.
Triggered by Eventarc from Pub/Sub topics.

Source: src/providers/gcp/cloud_functions/dispatcher/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import base64
import json
import os
import sys
import traceback
import requests
import functions_framework

try:
    from _shared.env_utils import require_env
    from _shared.normalize import normalize_telemetry
    from _shared.inter_cloud import get_id_token_headers
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.env_utils import require_env
    from _shared.normalize import normalize_telemetry
    from _shared.inter_cloud import get_id_token_headers


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


def _extract_pubsub_payload(envelope: dict) -> dict:
    """
    Extract telemetry from Pub/Sub push envelope.
    
    Pub/Sub via Eventarc wraps messages in:
    {"message": {"data": "<base64>", "messageId": "..."}}
    
    Returns original payload for direct HTTP calls (testing).
    """
    if "message" in envelope and "data" in envelope.get("message", {}):
        try:
            encoded = envelope["message"]["data"]
            decoded = base64.b64decode(encoded).decode("utf-8")
            return json.loads(decoded)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to decode Pub/Sub data: {e}")
            return envelope  # Fallback to raw envelope
    return envelope  # Direct HTTP call, no wrapper


@functions_framework.http
def main(request):
    """
    Dispatch incoming events to device-specific processor.
    
    Triggered by Pub/Sub via Eventarc or HTTP for testing.
    """
    print("Hello from Dispatcher!")
    
    try:
        event = request.get_json()
        print("Event received")
        
        # Extract payload from Pub/Sub envelope if present
        event = _extract_pubsub_payload(event)
        print("Payload extracted")
        
        # Normalize event to canonical format (device_id, timestamp)
        event = normalize_telemetry(event)
        print("Payload normalized")
        
        # Extract ID (now using canonical device_id)
        device_id = event.get("device_id")
        if not device_id:
            print("Error: 'device_id' missing in event.")
            return (json.dumps({"error": "Missing device_id"}), 400, {"Content-Type": "application/json"})
        
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
            headers=get_id_token_headers(target_url),
            timeout=30
        )
        
        print(f"Dispatch successful. Response: {response.status_code}")
        
        return (json.dumps({"status": "dispatched", "target": function_name}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Dispatcher Error: {e}")
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
