"""
Ingestion Azure Function.

Receives device telemetry from remote cloud connectors and routes
to local processors. This is the entry point for multi-cloud data
flowing INTO Azure's L2 layer.

Architecture:
    Remote Connector → [HTTP POST] → Ingestion → Local Processor

Source: src/providers/azure/azure_functions/ingestion/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func

try:
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env
    from _shared.normalize import normalize_telemetry
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env
    from _shared.normalize import normalize_telemetry


# Lazy loading for environment variables to allow Azure function discovery
# (module-level require_env would fail during import if env var is missing)
_digital_twin_info = None
_inter_cloud_token = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_inter_cloud_token():
    """Lazy-load INTER_CLOUD_TOKEN to avoid import-time failures."""
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token


# Function base URL for invoking other functions
FUNCTION_APP_BASE_URL = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()

# L2 Function Key - lazy loaded for Azure→Azure authentication
_l2_function_key = None

def _get_l2_function_key():
    """Lazy-load L2_FUNCTION_KEY for Azure→Azure HTTP authentication."""
    global _l2_function_key
    if _l2_function_key is None:
        _l2_function_key = require_env("L2_FUNCTION_KEY")
    return _l2_function_key

# Create Blueprint for registration by main function_app.py
bp = func.Blueprint()


def _invoke_processor(processor_name: str, payload: dict) -> None:
    """
    Invoke processor function via HTTP POST.
    
    Args:
        processor_name: Name of the processor function
        payload: Event data to send
    """
    if not FUNCTION_APP_BASE_URL:
        raise ValueError(f"FUNCTION_APP_BASE_URL not set - cannot invoke {processor_name}")
    
    # Build URL with function key for Azure→Azure authentication
    base_url = f"{FUNCTION_APP_BASE_URL}/api/{processor_name}"
    l2_key = _get_l2_function_key()
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}code={l2_key}"
    
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Successfully invoked {processor_name}: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to invoke {processor_name}: {e.code} {e.reason}")
        raise
    except urllib.error.URLError as e:
        logging.error(f"Network error invoking {processor_name}: {e.reason}")
        raise


@bp.function_name(name="ingestion")
@bp.route(route="ingestion", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def ingestion(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receive and validate events from remote cloud connectors.
    
    Validates the X-Inter-Cloud-Token header, extracts the payload
    from the envelope, and routes to the local processor.
    """
    logging.info("Azure Ingestion: Received request")
    
    try:
        # 1. Validate authentication token
        headers = dict(req.headers)
        if not validate_token(headers, _get_inter_cloud_token()):
            logging.error("Token validation failed")
            return func.HttpResponse(
                json.dumps({"error": "Unauthorized", "message": "Invalid X-Inter-Cloud-Token"}),
                status_code=403,
                mimetype="application/json"
            )
        
        # 2. Parse the envelope
        body = req.get_json()
        source_cloud = body.get("source_cloud", "unknown")
        logging.info(f"Received envelope from: {source_cloud}")
        
        # 3. Extract actual payload
        payload = body.get("payload")
        if payload is None:
            logging.error("No payload in envelope")
            return func.HttpResponse(
                json.dumps({"error": "Bad Request", "message": "Missing 'payload' in envelope"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # 4. Normalize payload to canonical format (device_id, timestamp)
        payload = normalize_telemetry(payload)
        logging.info(f"Normalized payload: {json.dumps(payload)}")
        
        # 5. Validate required fields
        device_id = payload.get("device_id")
        if not device_id:
            logging.error("No device_id in payload")
            return func.HttpResponse(
                json.dumps({"error": "Bad Request", "message": "Missing 'device_id' in payload"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # 5. Determine target processor
        processor_name = f"{device_id}-processor"
        
        logging.info(f"Invoking processor: {processor_name}")
        
        # 6. Invoke processor (async fire-and-forget)
        _invoke_processor(processor_name, payload)
        
        return func.HttpResponse(
            json.dumps({
                "status": "accepted",
                "target_processor": processor_name,
                "source_cloud": source_cloud,
                "trace_id": body.get("trace_id")
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Bad Request", "message": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.exception(f"Ingestion Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
