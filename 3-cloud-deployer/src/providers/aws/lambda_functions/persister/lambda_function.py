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
import traceback
import boto3

# Handle import path for both Lambda (deployed with _shared) and test (local development) contexts
try:
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


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


def _should_push_to_adt() -> bool:
    """
    Check if we should push data to remote ADT Pusher.
    
    Returns True only if:
    1. REMOTE_ADT_PUSHER_URL is set AND non-empty
    2. ADT_PUSHER_TOKEN is set AND non-empty
    
    ADT push is for multi-cloud L4 scenarios where L2 != L4 and L4 = Azure.
    """
    remote_url = os.environ.get("REMOTE_ADT_PUSHER_URL", "").strip()
    token = os.environ.get("ADT_PUSHER_TOKEN", "").strip()
    return bool(remote_url and token)


def _push_to_adt(event: dict) -> None:
    """
    Push telemetry to remote ADT Pusher (L4 Multi-Cloud).
    
    This is called IN ADDITION TO storage persist, not instead of it.
    Failures are logged but don't fail the overall persist operation.
    
    Args:
        event: Original telemetry event (with 'time' field)
    """
    if not _should_push_to_adt():
        return
    
    remote_url = os.environ.get("REMOTE_ADT_PUSHER_URL")
    token = os.environ.get("ADT_PUSHER_TOKEN")
    
    print(f"Pushing to ADT Pusher at {remote_url}")
    
    try:
        # Build ADT push payload
        adt_payload = {
            "device_id": event.get("device_id"),
            "device_type": event.get("device_type"),
            "telemetry": event.get("telemetry", {}),
            "timestamp": event.get("time")
        }
        
        result = post_to_remote(
            url=remote_url,
            token=token,
            payload=adt_payload,
            target_layer="L4"
        )
        print(f"ADT push successful: {result}")
    except Exception as e:
        # Log but don't fail - ADT is secondary to storage
        print(f"ADT push failed (non-fatal): {e}")


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
    print("Event: " + json.dumps(event))

    try:
        # Fail-fast validaton
        _validate_config()

        if "time" not in event:
            raise ValueError("Missing 'time' in event, cannot persist.")

        item = event.copy()
        item["id"] = str(item.pop("time"))  # DynamoDB Primary SK is 'id' (time)

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

        # Multi-cloud L4: Push to ADT Pusher (IN ADDITION to storage)
        # This is for scenarios where L2 != L4 and L4 = Azure
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

    except Exception as e:
        print(f"Persister Error: {e}")
        traceback.print_exc()
        raise e