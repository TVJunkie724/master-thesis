"""
Digital Twin Data Connector Last Entry Lambda Function.

Routes TwinMaker getPropertyValueHistory requests for last entry to:
- Local Hot Reader Last Entry (if L3 = L4, same cloud)
- Remote Hot Reader Last Entry (if L3 ≠ L4, different clouds via HTTP POST)
"""

import json
import os
import sys
import boto3
import urllib.request
import urllib.error

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

# Multi-cloud configuration
LOCAL_HOT_READER_LAST_ENTRY_NAME = os.environ.get("LOCAL_HOT_READER_LAST_ENTRY_NAME", "").strip()
REMOTE_READER_URL = os.environ.get("REMOTE_READER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

lambda_client = boto3.client("lambda")


def _is_multi_cloud() -> bool:
    """Check if this is a multi-cloud deployment (L3 ≠ L4)."""
    return bool(REMOTE_READER_URL)


def _invoke_local_hot_reader(event: dict) -> dict:
    """Invoke local Hot Reader Last Entry Lambda directly."""
    if not LOCAL_HOT_READER_LAST_ENTRY_NAME:
        raise EnvironmentError("LOCAL_HOT_READER_LAST_ENTRY_NAME not configured")
    
    response = lambda_client.invoke(
        FunctionName=LOCAL_HOT_READER_LAST_ENTRY_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode("utf-8")
    )
    
    payload = json.loads(response["Payload"].read().decode("utf-8"))
    return payload


def _query_remote_hot_reader(event: dict) -> dict:
    """Query remote Hot Reader Last Entry via HTTP POST."""
    if not REMOTE_READER_URL:
        raise EnvironmentError("REMOTE_READER_URL not configured")
    if not INTER_CLOUD_TOKEN:
        raise EnvironmentError("INTER_CLOUD_TOKEN not configured")
    
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
    """Route TwinMaker last entry query to local or remote Hot Reader."""
    print("Hello from Digital Twin Data Connector Last Entry!")
    print("Event: " + json.dumps(event))
    
    try:
        if _is_multi_cloud():
            print(f"Multi-cloud mode: Routing to {REMOTE_READER_URL}")
            result = _query_remote_hot_reader(event)
        else:
            print(f"Single-cloud mode: Invoking {LOCAL_HOT_READER_LAST_ENTRY_NAME}")
            result = _invoke_local_hot_reader(event)
        
        print("Response: " + json.dumps(result))
        return result
        
    except Exception as e:
        print(f"Digital Twin Data Connector Last Entry Error: {e}")
        print("Returning empty propertyValues due to error.")
        return { "propertyValues": {} }
