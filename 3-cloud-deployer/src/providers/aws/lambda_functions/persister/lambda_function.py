import os
import json
import boto3
import urllib.request
import time
import uuid
from datetime import datetime, timezone


# Configuration from environment
DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", "{}"))
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", None)
EVENT_CHECKER_LAMBDA_NAME = os.environ.get("EVENT_CHECKER_LAMBDA_NAME", None)

# AWS clients (initialized lazily for single-cloud mode)
dynamodb_client = None
dynamodb_table = None
lambda_client = boto3.client("lambda")


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


def _get_dynamodb_table():
    """Lazy initialization of DynamoDB table for single-cloud mode."""
    global dynamodb_client, dynamodb_table
    if dynamodb_table is None:
        dynamodb_client = boto3.resource("dynamodb")
        dynamodb_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)
    return dynamodb_table


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


def _post_to_remote_writer(remote_url: str, item: dict) -> None:
    """
    POST data to remote Writer API with retry logic.
    
    Args:
        remote_url: The Writer function URL
        item: The data item to persist
    
    Raises:
        ValueError: If INTER_CLOUD_TOKEN is missing
        Exception: If all retry attempts fail
    """
    token = os.environ.get("INTER_CLOUD_TOKEN", "").strip()
    if not token:
        raise ValueError("Multi-cloud mode enabled but INTER_CLOUD_TOKEN is missing or empty")
    
    # Build payload envelope per technical_specs.md
    payload = {
        "source_cloud": "aws",
        "target_layer": "L3",
        "message_type": "telemetry",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": item,
        "trace_id": str(uuid.uuid4())
    }
    
    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'X-Inter-Cloud-Token': token
    }
    
    req = urllib.request.Request(remote_url, data=data, headers=headers)
    
    # Retry Logic (Exponential Backoff)
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                print(f"Remote Writer response: {response.getcode()}")
                return
        except urllib.request.HTTPError as e:
            # Client error: Do not retry
            if 400 <= e.code < 500:
                print(f"Client Error ({e.code}): {e.reason}. Not Retrying.")
                raise e
            
            # Server error: Retry
            if attempt < max_retries:
                print(f"Server Error ({e.code}): {e.reason}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise e
        except Exception as e:
            # Network/Connection error
            if attempt < max_retries:
                print(f"Connection Attempt {attempt+1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"All attempts failed. Error: {e}")
                raise e


def lambda_handler(event, context):
    print("Hello from Persister!")
    print("Event: " + json.dumps(event))

    try:
        if "time" not in event:
            raise ValueError("Missing 'time' in event, cannot persist.")

        item = event.copy()
        item["id"] = str(item.pop("time"))  # DynamoDB Primary SK is 'id' (time)

        # Multi-cloud: Check if we should write to remote Writer
        if _is_multi_cloud_storage():
            remote_url = os.environ.get("REMOTE_WRITER_URL")
            print(f"Multi-cloud mode: POSTing to remote Writer at {remote_url}")
            _post_to_remote_writer(remote_url, item)
            print("Item persisted to remote cloud.")
        else:
            # Single-cloud: Write to local DynamoDB
            table = _get_dynamodb_table()
            table.put_item(Item=item)
            print("Item persisted to local DynamoDB.")

        # Event checking (only in single-cloud mode or if explicitly enabled)
        if os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true":
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
        raise e