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
    from _shared.inter_cloud import (
        get_id_token_headers,
        post_to_remote,
        validate_https_url,
    )
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _cloud_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _cloud_funcs_dir not in sys.path:
        sys.path.insert(0, _cloud_funcs_dir)
    from _shared.inter_cloud import (
        get_id_token_headers,
        post_to_remote,
        validate_https_url,
    )
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


class AdtDeliveryError(Exception):
    """Raised when required Azure Digital Twins delivery fails."""


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


def _get_adt_delivery_settings() -> tuple[str, str] | None:
    """Resolve required ADT delivery settings from the configured L4 provider."""
    providers = _get_digital_twin_info().get("config_providers")
    if not isinstance(providers, dict):
        raise ConfigurationError(
            "config_providers is required in DIGITAL_TWIN_INFO"
        )

    layer_4_provider = providers.get("layer_4_provider")
    if not isinstance(layer_4_provider, str) or not layer_4_provider.strip():
        raise ConfigurationError("layer_4_provider is required")
    if layer_4_provider.lower() != "azure":
        return None

    remote_url = os.environ.get("REMOTE_ADT_PUSHER_URL", "").strip()
    token = os.environ.get("ADT_PUSHER_TOKEN", "").strip()
    if not remote_url:
        raise ConfigurationError(
            "REMOTE_ADT_PUSHER_URL is required when L4 is Azure"
        )
    if not token:
        raise ConfigurationError("ADT_PUSHER_TOKEN is required when L4 is Azure")
    try:
        validate_https_url(remote_url)
    except ValueError:
        raise ConfigurationError(
            "REMOTE_ADT_PUSHER_URL must be an absolute HTTPS URL"
        ) from None
    return remote_url, token


def _build_adt_payload(event: dict) -> dict:
    """Build the provider-neutral telemetry payload accepted by ADT Pusher."""
    telemetry = event.get("telemetry")
    if telemetry is None:
        excluded_keys = {
            "device_id",
            "device_type",
            "id",
            "time",
            "timestamp",
            "ts",
            "telemetry",
        }
        telemetry = {key: value for key, value in event.items() if key not in excluded_keys}
    if not isinstance(telemetry, dict) or not telemetry:
        raise ValueError("Telemetry payload must be a non-empty object")

    return {
        "device_id": event.get("device_id"),
        "device_type": event.get("device_type"),
        "telemetry": telemetry,
        "timestamp": event.get("timestamp") or event.get("time"),
    }


def _push_to_adt(event: dict) -> None:
    """
    Push telemetry to the canonical Azure L4 ADT Pusher.

    This is called in addition to the idempotent storage write. Required
    delivery failures propagate so callers can retry the complete operation.
    
    Args:
        event: Original telemetry event (with 'timestamp' field)
    """
    settings = _get_adt_delivery_settings()
    if settings is None:
        return
    remote_url, token = settings

    try:
        post_to_remote(
            url=remote_url,
            token=token,
            payload=_build_adt_payload(event),
            target_layer="L4",
        )
        print("ADT push completed")
    except (ConfigurationError, ValueError):
        raise
    except Exception as exc:
        print(f"ADT push failed: {type(exc).__name__}")
        raise AdtDeliveryError("Azure Digital Twins update failed") from None


def _validate_config() -> None:
    """Validate provider-dependent configuration before any storage write."""
    if _is_multi_cloud_storage():
        if not os.environ.get("INTER_CLOUD_TOKEN", "").strip():
            raise ConfigurationError("INTER_CLOUD_TOKEN required for multi-cloud mode")
    _get_adt_delivery_settings()


@functions_framework.http
def main(request):
    """
    Persist telemetry data to storage.
    
    In single-cloud mode, writes directly to Firestore.
    In multi-cloud mode, POSTs to remote Hot Writer via shared module.
    """
    print("Hello from Persister!")
    
    try:
        _validate_config()
        event = request.get_json()
        print("Event received")
        
        # After normalization, event has 'timestamp' field (canonical)
        if "timestamp" not in event:
            return (json.dumps({"error": "Missing 'timestamp' in event. Did normalization run?"}), 400, {"Content-Type": "application/json"})
        
        item = event.copy()
        # Generate document ID (consistent across all clouds)
        # ID format: {device_id}_{timestamp} for uniqueness and traceability
        # Timestamp is ISO8601 string from normalize_telemetry() (e.g., "2026-01-28T12:00:00Z")
        if "device_id" not in item:
            return (json.dumps({"error": "Missing 'device_id' in event. Cannot generate document ID."}), 400, {"Content-Type": "application/json"})
        item["id"] = f"{item['device_id']}_{item['timestamp']}"
        # Remove 'time' to avoid duplicate data
        item.pop("time", None)

        # Reject known Azure L4 payload errors before the storage write.
        if _get_adt_delivery_settings() is not None:
            _build_adt_payload(event)
        
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
        
        # Azure L4: update ADT after the idempotent storage write.
        _push_to_adt(event)
        
        # Event checking (only if enabled)
        if os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true":
            if EVENT_CHECKER_FUNCTION_URL:
                try:
                    # Use OIDC ID token for GCP Cloud Functions Gen2 service-to-service auth
                    requests.post(
                        EVENT_CHECKER_FUNCTION_URL,
                        json=event,
                        headers=get_id_token_headers(EVENT_CHECKER_FUNCTION_URL),
                        timeout=10
                    )
                except Exception as e:
                    print(f"CRITICAL: Failed to invoke Event Checker: {e}")
                    raise e
        
        return (json.dumps({"status": "persisted"}), 200, {"Content-Type": "application/json"})
        
    except ValueError as exc:
        print(f"Persister payload validation failed: {type(exc).__name__}")
        return (
            json.dumps({"error": "Invalid telemetry payload"}),
            400,
            {"Content-Type": "application/json"},
        )
    except ConfigurationError as exc:
        print(f"Persister configuration failed: {type(exc).__name__}")
        return (
            json.dumps({"error": "Configuration error"}),
            500,
            {"Content-Type": "application/json"},
        )
    except AdtDeliveryError as exc:
        print(f"Persister ADT delivery failed: {type(exc).__name__}")
        return (
            json.dumps({"error": "Azure Digital Twins update failed"}),
            502,
            {"Content-Type": "application/json"},
        )
    except Exception as exc:
        print(f"Persister failed: {type(exc).__name__}")
        return (
            json.dumps({"error": "Persister error"}),
            500,
            {"Content-Type": "application/json"},
        )
