"""
ADT Pusher Azure Function.

HTTP triggered function that receives telemetry from REMOTE Persisters
(on AWS/GCP) and updates Azure Digital Twins.

This function is deployed as part of L0 (Glue Layer) and is used
for MULTI-CLOUD scenarios where L2 Persisters are on a different cloud
than L4 (ADT on Azure).

Architecture:
    AWS/GCP Persister → HTTP POST → ADT Pusher (L0) → Azure Digital Twins

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
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from _shared.adt_helper import (
        create_adt_client,
        update_adt_twin
    )


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

# Import require_env with fallback (same pattern as adt_helper)
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    # Fallback already handled in adt_helper import above
    from _shared.env_utils import require_env

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
    
    This function receives telemetry data from AWS/GCP Persisters and
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
        500: Internal error
        503: ADT not configured (L4 not deployed yet)
    """
    logging.info("ADT Pusher: Received request")
    
    # 1. Validate inter-cloud token
    if not INTER_CLOUD_TOKEN:
        logging.error("ADT Pusher: INTER_CLOUD_TOKEN not configured")
        return func.HttpResponse(
            json.dumps({"error": "ADT Pusher not properly configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    request_token = req.headers.get("X-Inter-Cloud-Token", "")
    if request_token != INTER_CLOUD_TOKEN:
        logging.warning("ADT Pusher: Invalid or missing token")
        return func.HttpResponse(
            json.dumps({"error": "Unauthorized"}),
            status_code=401,
            mimetype="application/json"
        )
    
    # 2. Check if ADT is configured
    if not ADT_INSTANCE_URL:
        logging.warning("ADT Pusher: ADT_INSTANCE_URL not set (L4 not deployed yet)")
        return func.HttpResponse(
            json.dumps({"error": "ADT not configured - deploy L4 first"}),
            status_code=503,
            mimetype="application/json"
        )
    
    # 3. Parse request body
    try:
        body = req.get_json()
    except ValueError:
        logging.error("ADT Pusher: Invalid JSON in request body")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )
    
    logging.info(f"ADT Pusher: Body = {json.dumps(body)}")
    
    # 4. Extract device_id and telemetry
    device_id = body.get("device_id")
    
    if not device_id:
        logging.error("ADT Pusher: Missing device_id in request")
        return func.HttpResponse(
            json.dumps({"error": "Missing 'device_id' in request body"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Try to get telemetry from nested key or treat entire body as telemetry
    telemetry = body.get("telemetry")
    if not telemetry:
        # Treat remaining body keys as telemetry (excluding metadata keys)
        excluded_keys = {"device_id", "id", "time", "timestamp"}
        telemetry = {k: v for k, v in body.items() if k not in excluded_keys}
    
    if not telemetry:
        logging.warning(f"ADT Pusher: No telemetry data for device {device_id}")
        return func.HttpResponse(
            json.dumps({"status": "no_data", "message": "No telemetry to update"}),
            status_code=200,
            mimetype="application/json"
        )
    
    # 5. Update ADT twin
    try:
        adt_client = create_adt_client(ADT_INSTANCE_URL)
        twin_id = update_adt_twin(
            adt_client=adt_client,
            device_id=device_id,
            telemetry=telemetry,
            digital_twin_info=_get_digital_twin_info()
        )
        
        logging.info(f"ADT Pusher: Successfully updated twin '{twin_id}'")
        
        return func.HttpResponse(
            json.dumps({"status": "updated", "twin_id": twin_id}),
            status_code=200,
            mimetype="application/json"
        )
        
    except ValueError as e:
        logging.error(f"ADT Pusher: Validation error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"ADT Pusher: Error updating ADT: {type(e).__name__}: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"ADT update failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
