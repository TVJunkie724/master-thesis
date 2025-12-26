"""
Processor Wrapper Azure Function.

Calls user-defined processor function via HTTP and invokes the Persister.
Dynamically constructs processor URL from device ID.

Architecture:
    Ingestion → Processor Wrapper → HTTP → User Processor → Wrapper → Persister

Source: src/providers/azure/azure_functions/processor_wrapper/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env


# Lazy loading for environment variables to allow Azure function discovery
_persister_function_url = None
_digital_twin_info = None

def _get_persister_function_url():
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


# Create Blueprint for registration by main function_app.py
bp = func.Blueprint()


def _invoke_persister(payload: dict) -> None:
    """
    Invoke Persister function via HTTP POST.
    
    Args:
        payload: Processed event data to persist
    """
    persister_url = _get_persister_function_url()
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(persister_url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Persister invoked successfully: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to invoke Persister: {e.code} {e.reason}")
        raise
    except urllib.error.URLError as e:
        logging.error(f"Network error invoking Persister: {e.reason}")
        raise


@bp.function_name(name="processor")
@bp.route(route="processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def processor(req: func.HttpRequest) -> func.HttpResponse:
    """
    Call user processor via HTTP and invoke Persister.
    
    Dynamically constructs the processor URL from the device ID in the event,
    calls the user's processor function, then sends the result to Persister.
    """
    logging.info("Azure Processor Wrapper: Executing user logic...")
    
    try:
        # Parse input event
        event = req.get_json()
        
        # 1. Call User Processor via HTTP
        device_id = event.get("iotDeviceId", "default")
        try:
            url = _get_processor_url(device_id)
            if not url or not url.startswith("http"):
                raise Exception(f"Cannot construct processor URL for device {device_id}")
            else:
                logging.info(f"Calling user processor at {url}")
                data = json.dumps(event).encode("utf-8")
                headers = {"Content-Type": "application/json"}
                req_proc = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req_proc, timeout=30) as response:
                    processed_event = json.loads(response.read().decode("utf-8"))
                logging.info(f"User Logic Complete. Result: {json.dumps(processed_event)}")
        except Exception as e:
            logging.error(f"[USER_LOGIC_ERROR] Processing failed: {e}")
            return func.HttpResponse(
                json.dumps({"error": "User logic error", "message": str(e)}),
                status_code=500,
                mimetype="application/json"
            )
        
        # 2. Invoke Persister
        _invoke_persister(processed_event)
        
        return func.HttpResponse(
            json.dumps({"status": "processed", "result": processed_event}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"[SYSTEM_ERROR] Processor error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "System error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
