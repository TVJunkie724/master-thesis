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
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import safe_urlopen, validate_token
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
    from _shared.normalize import normalize_telemetry
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import safe_urlopen, validate_token
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
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
        raise MissingEnvironmentVariableError(
            "FUNCTION_APP_BASE_URL is missing or empty"
        )
    
    # Build URL with function key for Azure→Azure authentication
    base_url = f"{FUNCTION_APP_BASE_URL}/api/{processor_name}"
    l2_key = _get_l2_function_key()
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}code={l2_key}"
    
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with safe_urlopen(req, timeout=30) as response:
            logging.info(f"Successfully invoked {processor_name}: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error("Failed to invoke %s: HTTP %s", processor_name, e.code)
        raise
    except urllib.error.URLError as e:
        logging.error(
            "Network error invoking %s: %s",
            processor_name,
            type(e.reason).__name__,
        )
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
            return error_response(
                code="UNAUTHORIZED",
                message="Invalid X-Inter-Cloud-Token",
                status_code=403,
            )

        # 2. Parse the envelope
        body = parse_json_request(req)
        if not isinstance(body, dict):
            return error_response(
                code="INVALID_REQUEST",
                message="Request body must be a JSON object",
                status_code=400,
            )
        source_cloud = body.get("source_cloud", "unknown")
        logging.info(f"Received envelope from: {source_cloud}")
        
        # 3. Extract actual payload
        payload = body.get("payload")
        if not isinstance(payload, dict):
            logging.error("No payload in envelope")
            return error_response(
                code="INVALID_REQUEST",
                message="Envelope payload must be a JSON object",
                status_code=400,
            )
        
        # 4. Normalize payload to canonical format (device_id, timestamp)
        try:
            payload = normalize_telemetry(payload)
        except (TypeError, ValueError):
            return error_response(
                code="INVALID_REQUEST",
                message="Telemetry payload is invalid",
                status_code=400,
            )
        logging.info("Payload normalized")
        
        # 5. Validate required fields
        device_id = payload.get("device_id")
        if not device_id:
            logging.error("No device_id in payload")
            return error_response(
                code="INVALID_REQUEST",
                message="Missing 'device_id' in payload",
                status_code=400,
            )
        
        # 5. Invoke processor wrapper (handles user processing + persister)
        processor_name = "processor"
        
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
        
    except InvalidRequestBody:
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid JSON body",
            status_code=400,
        )

    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        return failure_response(
            component="azure.ingestion.processor",
            error=exc,
            code="UPSTREAM_ERROR",
            message="The processing service is unavailable.",
            status_code=502,
        )

    except MissingEnvironmentVariableError as exc:
        return failure_response(
            component="azure.ingestion.configuration",
            error=exc,
            code="CONFIGURATION_ERROR",
            message="Ingestion configuration is unavailable.",
            status_code=500,
        )

    except Exception as exc:
        return failure_response(
            component="azure.ingestion",
            error=exc,
        )
