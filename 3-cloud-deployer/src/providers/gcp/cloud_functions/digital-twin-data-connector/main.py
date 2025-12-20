"""
Digital Twin Data Connector GCP Cloud Function.

Routes data queries to hot-reader function (local or remote).
Used by L4/L5 visualization layers to access telemetry data.

Source: src/providers/gcp/cloud_functions/digital-twin-data-connector/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import requests
import functions_framework

# Handle import path for both Cloud Functions and test contexts
try:
    from _shared.inter_cloud import validate_token, build_auth_error_response
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import validate_token, build_auth_error_response
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None

def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

# Optional - for protected endpoints
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "")

# Local reader URL (for single-cloud mode)
LOCAL_HOT_READER_URL = os.environ.get("LOCAL_HOT_READER_URL", "")

# Remote reader URL (for multi-cloud mode when L3 is on different cloud)
REMOTE_HOT_READER_URL = os.environ.get("REMOTE_HOT_READER_URL", "")


def _is_multi_cloud_reader() -> bool:
    """Check if L3 Hot storage is on a different cloud."""
    if not REMOTE_HOT_READER_URL:
        return False
    
    providers = _get_digital_twin_info().get("config_providers")
    if providers is None:
        return False
    
    l4_provider = providers.get("layer_4_provider", "gcp")
    l3_provider = providers.get("layer_3_hot_provider", "gcp")
    
    return l4_provider != l3_provider


@functions_framework.http
def main(request):
    """
    Route data queries to appropriate hot reader.
    
    Query parameters are passed through to the reader.
    """
    print("Hello from Digital Twin Data Connector!")
    
    # Validate token if configured
    if INTER_CLOUD_TOKEN:
        if not validate_token(request, INTER_CLOUD_TOKEN):
            return build_auth_error_response()
    
    try:
        # Build query string from request args
        query_params = request.args.to_dict()
        
        if _is_multi_cloud_reader():
            # Multi-cloud: Query remote reader
            target_url = REMOTE_HOT_READER_URL
            headers = {"X-Inter-Cloud-Token": INTER_CLOUD_TOKEN} if INTER_CLOUD_TOKEN else {}
        else:
            # Single-cloud: Query local reader
            if not LOCAL_HOT_READER_URL:
                raise ConfigurationError("LOCAL_HOT_READER_URL is required for single-cloud mode")
            target_url = LOCAL_HOT_READER_URL
            headers = {}
        
        print(f"Querying: {target_url}")
        
        response = requests.get(
            target_url,
            params=query_params,
            headers=headers,
            timeout=30
        )
        
        # Return the reader's response
        return (response.text, response.status_code, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Digital Twin Data Connector Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
