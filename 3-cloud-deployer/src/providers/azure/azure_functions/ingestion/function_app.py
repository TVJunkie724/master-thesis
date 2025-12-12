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

# Handle import path for shared module
try:
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")

# Function base URL for invoking other functions
FUNCTION_APP_BASE_URL = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()

# Create Function App instance
app = func.FunctionApp()


def _invoke_processor(processor_name: str, payload: dict) -> None:
    """
    Invoke processor function via HTTP POST.
    
    Args:
        processor_name: Name of the processor function
        payload: Event data to send
    """
    if not FUNCTION_APP_BASE_URL:
        logging.warning(f"FUNCTION_APP_BASE_URL not set - cannot invoke {processor_name}")
        return
    
    url = f"{FUNCTION_APP_BASE_URL}/api/{processor_name}"
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


@app.function_name(name="ingestion")
@app.route(route="ingestion", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
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
        if not validate_token(headers, INTER_CLOUD_TOKEN):
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
        
        # 4. Validate required fields
        device_id = payload.get("iotDeviceId")
        if not device_id:
            logging.error("No iotDeviceId in payload")
            return func.HttpResponse(
                json.dumps({"error": "Bad Request", "message": "Missing 'iotDeviceId' in payload"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # 5. Determine target processor
        twin_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"]
        processor_name = f"{twin_name}-{device_id}-processor"
        
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
        logging.error(f"Ingestion Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
