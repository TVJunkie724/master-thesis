"""
Persister GCP Cloud Function.

Persists processed telemetry data to storage (Firestore or remote Writer).
Handles both single-cloud (direct Firestore write) and multi-cloud (HTTP POST to remote Writer) modes.

Source: src/providers/gcp/cloud_functions/persister/main.py
Editable: Yes - This is the runtime Cloud Function code
"""
import json
import os
import sys
import requests
import functions_framework
from google.cloud import firestore

# Handle import path for both Cloud Functions and test contexts
try:
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


# Lazy-loaded environment variables (loaded on first use to avoid import-time failures)
_digital_twin_info = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

# Optional environment variables (only used in certain modes)
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "hot_data")
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "(default)")
EVENT_CHECKER_FUNCTION_URL = os.environ.get("EVENT_CHECKER_FUNCTION_URL", "")

# Firestore client (initialized lazily)
_firestore_client = None


def _get_firestore_client():
    """Lazy initialization of Firestore client with named database support."""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(database=FIRESTORE_DATABASE)
    return _firestore_client


def _is_multi_cloud_storage() -> bool:
    """
    Check if L3 storage is on a different cloud.
    
    Returns True only if:
    1. REMOTE_WRITER_URL is set AND non-empty
    2. layer_2_provider != layer_3_hot_provider in DIGITAL_TWIN_INFO
    """
    remote_url = os.environ.get("REMOTE_WRITER_URL", "").strip()
    if not remote_url:
        return False
    
    providers = _get_digital_twin_info().get("config_providers")
    if providers is None:
        raise ConfigurationError(
            "CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO. "
            "Ensure deployer injects config.providers into DIGITAL_TWIN_INFO."
        )
    
    l2_provider = providers.get("layer_2_provider")
    l3_provider = providers.get("layer_3_hot_provider")
    
    if l2_provider is None or l3_provider is None:
        raise ConfigurationError(
            f"CRITICAL: Missing provider mapping. "
            f"layer_2_provider={l2_provider}, layer_3_hot_provider={l3_provider}"
        )
    
    if l2_provider == l3_provider:
        raise ConfigurationError(f"REMOTE_WRITER_URL set but providers match ({l2_provider}). Invalid multi-cloud config.")
    
    return True


@functions_framework.http
def main(request):
    """
    Persist telemetry data to storage.
    
    In single-cloud mode, writes directly to Firestore.
    In multi-cloud mode, POSTs to remote Hot Writer via shared module.
    """
    print("Hello from Persister!")
    
    try:
        event = request.get_json()
        print("Event: " + json.dumps(event))
        
        if "time" not in event:
            return (json.dumps({"error": "Missing 'time' in event"}), 400, {"Content-Type": "application/json"})
        
        item = event.copy()
        item["id"] = str(item.pop("time"))  # Firestore document ID is 'id' (time)
        
        # Multi-cloud: Check if we should write to remote Writer
        if _is_multi_cloud_storage():
            remote_url = os.environ.get("REMOTE_WRITER_URL")
            token = os.environ.get("INTER_CLOUD_TOKEN", "").strip()
            
            print(f"Multi-cloud mode: POSTing to remote Hot Writer at {remote_url}")
            post_to_remote(
                url=remote_url,
                token=token,
                payload=item,
                target_layer="L3"
            )
            print("Item persisted to remote cloud.")
        else:
            # Single-cloud: Write to local Firestore
            db = _get_firestore_client()
            doc_ref = db.collection(FIRESTORE_COLLECTION).document(item["id"])
            doc_ref.set(item)
            print("Item persisted to local Firestore.")
        
        # Event checking (only if enabled)
        if os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true":
            if EVENT_CHECKER_FUNCTION_URL:
                try:
                    requests.post(
                        EVENT_CHECKER_FUNCTION_URL,
                        json=event,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                except Exception as e:
                    print(f"CRITICAL: Failed to invoke Event Checker: {e}")
                    raise e
        
        return (json.dumps({"status": "persisted"}), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        print(f"Persister Error: {e}")
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
