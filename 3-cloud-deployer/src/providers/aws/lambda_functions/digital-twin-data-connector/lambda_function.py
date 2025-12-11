"""
Digital Twin Data Connector Lambda Function.

This function is invoked by TwinMaker and routes requests to:
- Local Hot Reader (if L3 = L4, same cloud)
- Remote Hot Reader (if L3 ≠ L4, different clouds via HTTP POST)

Architecture:
```
TwinMaker → Digital Twin Data Connector → Hot Reader (local or remote)
```

This function only exists in multi-cloud scenarios where L3 ≠ L4.
"""

import json
import os
import boto3
import urllib.request
import urllib.error


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))

# Multi-cloud configuration
# If L3 = L4 (same cloud), LOCAL_HOT_READER_NAME is set
# If L3 ≠ L4 (different clouds), REMOTE_READER_URL and INTER_CLOUD_TOKEN are set
LOCAL_HOT_READER_NAME = os.environ.get("LOCAL_HOT_READER_NAME", "").strip()
REMOTE_READER_URL = os.environ.get("REMOTE_READER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

lambda_client = boto3.client("lambda")


def _is_multi_cloud() -> bool:
    """Check if this is a multi-cloud deployment (L3 ≠ L4)."""
    return bool(REMOTE_READER_URL)


def _invoke_local_hot_reader(event: dict) -> dict:
    """Invoke local Hot Reader Lambda directly."""
    if not LOCAL_HOT_READER_NAME:
        raise EnvironmentError("LOCAL_HOT_READER_NAME not configured for single-cloud mode")
    
    response = lambda_client.invoke(
        FunctionName=LOCAL_HOT_READER_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode("utf-8")
    )
    
    payload = json.loads(response["Payload"].read().decode("utf-8"))
    return payload


def _query_remote_hot_reader(event: dict) -> dict:
    """Query remote Hot Reader via HTTP POST with X-Inter-Cloud-Token."""
    if not REMOTE_READER_URL:
        raise EnvironmentError("REMOTE_READER_URL not configured for multi-cloud mode")
    if not INTER_CLOUD_TOKEN:
        raise EnvironmentError("INTER_CLOUD_TOKEN not configured for multi-cloud mode")
    
    data = json.dumps(event).encode("utf-8")
    
    req = urllib.request.Request(
        REMOTE_READER_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Inter-Cloud-Token": INTER_CLOUD_TOKEN
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"Remote Hot Reader returned {e.code}: {error_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to reach Remote Hot Reader: {e.reason}")


def lambda_handler(event, context):
    """
    Route TwinMaker query to local or remote Hot Reader.
    
    Args:
        event: TwinMaker query event with workspaceId, entityId, componentName, etc.
        context: Lambda context
    
    Returns:
        TwinMaker-compatible response with propertyValues
    """
    print("Hello from Digital Twin Data Connector!")
    print("Event: " + json.dumps(event))
    
    try:
        if _is_multi_cloud():
            print(f"Multi-cloud mode: Routing to remote Hot Reader at {REMOTE_READER_URL}")
            result = _query_remote_hot_reader(event)
        else:
            print(f"Single-cloud mode: Invoking local Hot Reader {LOCAL_HOT_READER_NAME}")
            result = _invoke_local_hot_reader(event)
        
        print("Response: " + json.dumps(result))
        return result
        
    except Exception as e:
        print(f"Digital Twin Data Connector Error: {e}")
        # Return empty to avoid breaking TwinMaker dashboard
        print("Returning empty propertyValues due to error.")
        return { "propertyValues": [] }
