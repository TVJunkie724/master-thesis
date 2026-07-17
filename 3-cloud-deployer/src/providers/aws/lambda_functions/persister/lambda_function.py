"""
Persister Lambda Function.

Persists processed telemetry data to storage (DynamoDB or remote Writer).
Handles both single-cloud (direct DynamoDB write) and multi-cloud (HTTP POST to remote Writer) modes.

Source: src/providers/aws/lambda_functions/persister/lambda_function.py
Editable: Yes - This is the runtime Lambda code
"""
import os
import sys
import json
import boto3

# Handle import path for both Lambda (deployed with _shared) and test (local development) contexts
try:
    from _shared.inter_cloud import post_to_remote, validate_https_url
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.inter_cloud import post_to_remote, validate_https_url
    from _shared.env_utils import require_env


# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


class AdtDeliveryError(Exception):
    """Raised when required Azure Digital Twins delivery fails."""


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

# Optional environment variables (only used in certain modes)
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "")
EVENT_CHECKER_LAMBDA_NAME = os.environ.get("EVENT_CHECKER_LAMBDA_NAME", "")

# AWS clients (initialized lazily for single-cloud mode)
dynamodb_client = None
dynamodb_table = None
lambda_client = boto3.client("lambda")


# ==========================================
# DynamoDB Helpers
# ==========================================

def _get_dynamodb_table():
    """Lazy initialization of DynamoDB table for single-cloud mode."""
    global dynamodb_client, dynamodb_table
    if dynamodb_table is None:
        if not DYNAMODB_TABLE_NAME:
            raise ConfigurationError("DYNAMODB_TABLE_NAME is required for single-cloud storage mode")
        dynamodb_client = boto3.resource("dynamodb")
        dynamodb_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)
    return dynamodb_table


# ==========================================
# Multi-Cloud Detection
# ==========================================

def _is_multi_cloud_storage() -> bool:
    """
    Check if L3 storage is on a different cloud.
    
    Returns True only if:
    1. REMOTE_WRITER_URL is set AND non-empty
    2. layer_2_provider != layer_3_hot_provider in DIGITAL_TWIN_INFO
    
    Raises:
        ConfigurationError: If config_providers is missing from DIGITAL_TWIN_INFO
    """
    remote_url = os.environ.get("REMOTE_WRITER_URL", "").strip()
    if not remote_url:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        raise ConfigurationError(
            "CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO. "
            "This indicates a deployment configuration error. "
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
        print(f"Warning: REMOTE_WRITER_URL is set but providers match ({l2_provider}). Using local write.")
        return False
    
    return True


def _get_adt_delivery_settings() -> tuple[str, str] | None:
    """Resolve required ADT delivery settings from the configured L4 provider."""
    providers = DIGITAL_TWIN_INFO.get("config_providers")
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
        event: Original telemetry event (with 'time' field)
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


# ==========================================
# Configuration Validation
# ==========================================

def _validate_config():
    """
    Validate configuration at runtime based on active mode.
    Raises ConfigurationError if invalid.
    """
    # If NOT in multi-cloud storage mode, we MUST have local storage config
    if not _is_multi_cloud_storage():
        if not DYNAMODB_TABLE_NAME:
            raise ConfigurationError("DYNAMODB_TABLE_NAME is required for single-cloud storage mode")
    _get_adt_delivery_settings()


# ==========================================
# Handler
# ==========================================

def lambda_handler(event, context):
    """
    Persist telemetry data to storage.
    
    In single-cloud mode, writes directly to DynamoDB.
    In multi-cloud mode, POSTs to remote Hot Writer via shared module.
    
    Args:
        event: Telemetry event with 'time' field
        context: Lambda context
    
    Raises:
        ValueError: If 'time' field is missing
        ConfigurationError: If multi-cloud config is invalid
    """
    print("Hello from Persister!")
    print("Event received")

    try:
        # Fail-fast validation
        _validate_config()

        # After normalization, event has both 'time' (original) and 'timestamp' (normalized)
        # DynamoDB schema uses device_id (hash) + timestamp (range)
        if "timestamp" not in event:
            raise ValueError("Missing 'timestamp' in event, cannot persist. Did normalization run?")

        item = event.copy()
        # Remove 'time' to avoid storing duplicate data (timestamp is the canonical sort key)
        item.pop("time", None)

        # Generate document ID (consistent across all clouds)
        # ID format: {device_id}_{timestamp} for uniqueness and traceability
        # Timestamp is ISO8601 string from normalize_telemetry() (e.g., "2026-01-28T12:00:00Z")
        if "device_id" not in item:
            raise ValueError("Missing 'device_id' in event. Cannot generate document ID.")
        item["id"] = f"{item['device_id']}_{item['timestamp']}"

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
            # Single-cloud: Write to local DynamoDB
            table = _get_dynamodb_table()
            table.put_item(Item=item)
            print("Item persisted to local DynamoDB.")

        # Azure L4: update ADT after the idempotent storage write.
        _push_to_adt(event)

        # Event checking (only in single-cloud mode or if explicitly enabled)
        if os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true":
            if not EVENT_CHECKER_LAMBDA_NAME:
                print("Warning: USE_EVENT_CHECKING is true but EVENT_CHECKER_LAMBDA_NAME is not set")
            else:
                try:
                    lambda_client.invoke(
                        FunctionName=EVENT_CHECKER_LAMBDA_NAME,
                        InvocationType="Event",
                        Payload=json.dumps(event).encode("utf-8")
                    )
                except Exception as e:
                    print(f"Warning: Failed to invoke Event Checker: {e}")
                    pass

    except Exception as exc:
        print(f"Persister failed: {type(exc).__name__}")
        raise
