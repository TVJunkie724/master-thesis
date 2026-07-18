"""
ADT Pusher Azure Function.

HTTP triggered function that receives telemetry from the active L2 Persister
(on AWS, Azure, or GCP) and updates Azure Digital Twins.

This function is deployed as part of L0 (Glue Layer) and is used
whenever L4 is implemented by Azure Digital Twins.

Architecture:
    L2 Persister -> HTTP POST -> ADT Pusher (L0) -> Azure Digital Twins

Authentication:
    Uses X-Inter-Cloud-Token header for cross-cloud authentication.
    Uses DefaultAzureCredential (Managed Identity) to talk to ADT.

Environment Variables Required:
    - ADT_INSTANCE_URL: Azure Digital Twins endpoint URL
    - INTER_CLOUD_TOKEN: Expected token for authentication
    - DIGITAL_TWIN_INFO: JSON config with device-to-twin mappings
"""

import azure.functions as func
import json
import logging
import os
import sys

# Handle import path for both deployed (with _shared) and test contexts
try:
    from _shared.adt_helper import (
        create_adt_client,
        update_adt_twin
    )
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import validate_token
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from _shared.adt_helper import (
        create_adt_client,
        update_adt_twin
    )
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import validate_token


# Create Blueprint for registration in main function_app.py
bp = func.Blueprint()

# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass

# Load configuration at module load time
# Note: ADT_INSTANCE_URL may be empty before L4 is deployed - this is acceptable
ADT_INSTANCE_URL = os.environ.get("ADT_INSTANCE_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Lazy loading for DIGITAL_TWIN_INFO to allow Azure function discovery
_digital_twin_info = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info


# ==========================================
# HTTP Triggered Function
# ==========================================

@bp.function_name(name="adt-pusher")
@bp.route(route="adt-pusher", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def adt_pusher(req: func.HttpRequest) -> func.HttpResponse:
    """
    Update Azure Digital Twin from remote Persister HTTP request.
    
    This function receives telemetry data from the selected L2 Persister and
    updates the corresponding digital twin. It validates the inter-cloud
    token before processing.
    
    Expected Request Format:
        Headers:
            X-Inter-Cloud-Token: <expected_token>
            Content-Type: application/json
            
        Body:
            {
                "device_id": "sensor-1",
                "telemetry": {
                    "temperature": 23.5,
                    "humidity": 60.2
                }
            }
            
        OR (compatible with Persister output format):
            {
                "id": "timestamp",
                "device_id": "sensor-1",
                "temperature": 23.5,
                "humidity": 60.2
            }
    
    Returns:
        200: Success
        400: Invalid request body
        401: Missing or invalid token
        500: Runtime configuration error
        502: Azure Digital Twins delivery error
        503: ADT not configured (L4 not deployed yet)
    """
    logging.info("ADT Pusher: Received request")
    
    # 1. Validate inter-cloud token
    if not INTER_CLOUD_TOKEN:
        logging.error("ADT Pusher: INTER_CLOUD_TOKEN not configured")
        return failure_response(
            component="azure.adt-pusher.configuration",
            error=ConfigurationError("INTER_CLOUD_TOKEN is not configured"),
            code="CONFIGURATION_ERROR",
            message="Service configuration is unavailable.",
            status_code=500,
        )
    
    if not validate_token(req.headers, INTER_CLOUD_TOKEN):
        logging.warning("ADT Pusher: Invalid or missing token")
        return error_response(
            code="UNAUTHORIZED",
            message="Invalid or missing X-Inter-Cloud-Token",
            status_code=401,
        )
    
    # 2. Check if ADT is configured
    if not ADT_INSTANCE_URL:
        logging.error("ADT Pusher: ADT_INSTANCE_URL not configured")
        return failure_response(
            component="azure.adt-pusher.configuration",
            error=ConfigurationError("ADT_INSTANCE_URL is not configured"),
            code="SERVICE_UNAVAILABLE",
            message="Azure Digital Twins is unavailable.",
            status_code=503,
        )
    
    # 3. Parse request body
    try:
        body = parse_json_request(req)
    except InvalidRequestBody:
        logging.error("ADT Pusher: Invalid JSON in request body")
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid JSON",
            status_code=400,
        )

    if not isinstance(body, dict):
        logging.error("ADT Pusher: Request body is not an object")
        return error_response(
            code="INVALID_REQUEST",
            message="Request body must be an object",
            status_code=400,
        )
    
    # 3.5 Unwrap inter-cloud envelope if present
    # post_to_remote() wraps payloads in: {source_cloud, target_layer, payload: {...}}
    if "payload" in body and "source_cloud" in body:
        logging.info("ADT Pusher: Unwrapping inter-cloud envelope")
        body = body["payload"]
        if not isinstance(body, dict):
            logging.error("ADT Pusher: Envelope payload is not an object")
            return error_response(
                code="INVALID_REQUEST",
                message="Envelope payload must be an object",
                status_code=400,
            )
    
    # 4. Extract device_id and telemetry
    device_id = body.get("device_id")
    
    if not isinstance(device_id, str) or not device_id.strip():
        logging.error("ADT Pusher: Missing device_id in request")
        return error_response(
            code="INVALID_REQUEST",
            message="Missing device_id",
            status_code=400,
        )
    
    # Try to get telemetry from nested key or treat entire body as telemetry
    telemetry = body.get("telemetry")
    if not isinstance(telemetry, dict) or not telemetry:
        # Treat remaining body keys as telemetry (excluding metadata keys)
        if telemetry is None:
            excluded_keys = {
                "device_id",
                "device_type",
                "id",
                "time",
                "timestamp",
                "telemetry",
            }
            telemetry = {k: v for k, v in body.items() if k not in excluded_keys}
    
    if not isinstance(telemetry, dict) or not telemetry:
        logging.warning("ADT Pusher: Missing or invalid telemetry")
        return error_response(
            code="INVALID_REQUEST",
            message="Telemetry must be a non-empty object",
            status_code=400,
        )
    
    # 5. Update ADT twin
    try:
        digital_twin_info = _get_digital_twin_info()
    except (MissingEnvironmentVariableError, json.JSONDecodeError) as exc:
        return failure_response(
            component="azure.adt-pusher.configuration",
            error=exc,
            code="CONFIGURATION_ERROR",
            message="Digital twin mapping configuration is unavailable.",
            status_code=500,
        )

    try:
        adt_client = create_adt_client(ADT_INSTANCE_URL)
        twin_id = update_adt_twin(
            adt_client=adt_client,
            device_id=device_id,
            telemetry=telemetry,
            digital_twin_info=digital_twin_info,
        )
        
        logging.info("ADT Pusher: Successfully updated one twin")
        
        return func.HttpResponse(
            json.dumps({"status": "updated", "twin_id": twin_id}),
            status_code=200,
            mimetype="application/json"
        )
        
    except ValueError as exc:
        logging.error("ADT Pusher validation failed: %s", type(exc).__name__)
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid telemetry or twin mapping",
            status_code=400,
        )
    except Exception as exc:
        return failure_response(
            component="azure.adt-pusher",
            error=exc,
            code="ADT_DELIVERY_FAILED",
            message="Azure Digital Twins update failed.",
            status_code=502,
        )
