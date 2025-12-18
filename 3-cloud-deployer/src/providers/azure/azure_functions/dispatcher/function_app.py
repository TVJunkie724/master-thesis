"""
Dispatcher Azure Function.

Routes incoming IoT Hub telemetry to the appropriate processor or connector function.
This is the entry point for all device data in Azure's L1 layer.

Architecture:
    IoT Hub → Event Grid → Dispatcher → Processor/Connector

Source: src/providers/azure/azure_functions/dispatcher/function_app.py
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


# DIGITAL_TWIN_INFO is lazy-loaded to allow Azure function discovery
# (module-level require_env would fail during import if env var is missing)
_digital_twin_info = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info


# Target function suffix: "-processor" for single-cloud, "-connector" for multi-cloud
TARGET_FUNCTION_SUFFIX = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")

# Function URL base for invoking other functions
FUNCTION_APP_BASE_URL = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()

# Create Blueprint for registration by main function_app.py
bp = func.Blueprint()


def _get_target_function_name(device_id: str) -> str:
    """
    Determine the target function to invoke based on deployment config.
    
    Uses TARGET_FUNCTION_SUFFIX to determine routing:
    - "-processor" for device-specific processor (single-cloud)
    - "-connector" for connector (multi-cloud L1→L2 bridge)
    """
    twin_info = _get_digital_twin_info()
    twin_name = twin_info["config"]["digital_twin_name"]
    
    if TARGET_FUNCTION_SUFFIX == "-connector":
        # Multi-cloud: route to connector (no device-specific naming)
        return f"{twin_name}-connector"
    else:
        # Single-cloud: route to device-specific processor
        return f"{twin_name}-{device_id}-processor"


def _invoke_function(function_name: str, payload: dict) -> None:
    """
    Invoke Azure Function via HTTP POST.
    
    Uses async invocation pattern (fire-and-forget).
    
    Args:
        function_name: Target function name
        payload: Event data to send
    """
    if not FUNCTION_APP_BASE_URL:
        logging.warning(f"FUNCTION_APP_BASE_URL not set - cannot invoke {function_name}")
        return
    
    url = f"{FUNCTION_APP_BASE_URL}/api/{function_name}"
    data = json.dumps(payload).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Successfully invoked {function_name}: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to invoke {function_name}: {e.code} {e.reason}")
        raise
    except urllib.error.URLError as e:
        logging.error(f"Network error invoking {function_name}: {e.reason}")
        raise


@bp.function_name(name="dispatcher")
@bp.event_grid_trigger(arg_name="event")
def dispatcher(event: func.EventGridEvent) -> None:
    """
    Main dispatcher function triggered by Event Grid (IoT Hub events).
    
    Receives device telemetry from IoT Hub via Event Grid, extracts
    the device ID, and routes to the appropriate processor or connector.
    """
    logging.info("Azure Dispatcher: Received event")
    
    try:
        # Parse event data
        event_data = event.get_json()
        logging.info(f"Event data: {json.dumps(event_data)}")
        
        # Extract device ID from event
        device_id = event_data.get("iotDeviceId")
        
        if not device_id:
            # Try alternative locations (IoT Hub Event Grid schema)
            device_id = event_data.get("systemProperties", {}).get("iothub-connection-device-id")
        
        if not device_id:
            logging.error("No device ID found in event")
            return
        
        # Determine routing target
        target_function = _get_target_function_name(device_id)
        logging.info(f"Dispatching to: {target_function}")
        
        # Invoke target function asynchronously
        _invoke_function(target_function, event_data)
        
        logging.info("Dispatch successful.")
        
    except Exception as e:
        logging.error(f"Dispatcher Error: {e}")
        raise e
