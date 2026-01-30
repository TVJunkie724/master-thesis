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

GCP Compatibility:
When L3-Hot = GCP, this connector must:
1. Build URL with query params (GCP reads request.args)
2. Transform response from {"items"} to {"propertyValues"}
"""
import json
import os
import sys
import traceback
import boto3
from urllib.parse import urlencode

# Handle import path for both Lambda (deployed with _shared) and test (local development) contexts
try:
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

# Multi-cloud configuration
# If L3 = L4 (same cloud), LOCAL_HOT_READER_NAME is set
# If L3 ≠ L4 (different clouds), REMOTE_READER_URL and INTER_CLOUD_TOKEN are set
LOCAL_HOT_READER_NAME = os.environ.get("LOCAL_HOT_READER_NAME", "").strip()
REMOTE_READER_URL = os.environ.get("REMOTE_READER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

lambda_client = boto3.client("lambda")


# ==============================================================================
# Cloud Detection
# ==============================================================================

def _is_multi_cloud() -> bool:
    """Check if this is a multi-cloud deployment (L3 ≠ L4)."""
    return bool(REMOTE_READER_URL)


def _is_gcp_reader() -> bool:
    """
    Check if remote reader is GCP Cloud Functions Gen2.
    
    GCP Gen2 functions are backed by Cloud Run with URLs like:
    https://hot-reader-abc123xyz-uc.a.run.app
    
    Note: Gen1 uses cloudfunctions.net but we use Gen2 exclusively.
    """
    return bool(REMOTE_READER_URL and ".run.app" in REMOTE_READER_URL)


# ==============================================================================
# GCP Query Translation
# ==============================================================================

def _build_gcp_query_url(event: dict) -> str:
    """
    Build GCP hot-reader URL with query parameters.
    
    TwinMaker sends: {entityId, componentName, startTime, endTime, selectedProperties}
    GCP expects: ?device_id=...&startTime=...&endTime=...
    
    Device ID mapping: componentName typically matches device_id in Firestore
    (naming convention maintained during twin creation).
    """
    # Extract device_id from componentName (naming convention: componentName = device_id)
    device_id = event.get("componentName") or event.get("entityId")
    
    params = {
        "device_id": device_id,
        "startTime": event.get("startTime", ""),
        "endTime": event.get("endTime", ""),
    }
    
    # Filter out empty params
    params = {k: v for k, v in params.items() if v}
    
    return f"{REMOTE_READER_URL}?{urlencode(params)}"


# ==============================================================================
# Response Transformation
# ==============================================================================

def _transform_gcp_to_twinmaker(raw_response: dict, event: dict) -> dict:
    """
    Transform GCP hot-reader response to TwinMaker propertyValues format.
    
    Input (GCP): {"items": [{device_id, temperature, humidity, timestamp}], "count": N}
    Output (TwinMaker): {"propertyValues": [{entityPropertyReference, values}]}
    
    Args:
        raw_response: Response from GCP hot-reader
        event: Original TwinMaker query with selectedProperties and properties metadata
    
    Returns:
        TwinMaker-compatible response with propertyValues list
    """
    items = raw_response.get("items", [])
    if not items and "item" in raw_response:
        items = [raw_response["item"]] if raw_response["item"] else []
    
    selected_properties = event.get("selectedProperties", [])
    properties_meta = event.get("properties", {})
    
    property_values = []
    for prop_name in selected_properties:
        # Get type from TwinMaker metadata or infer from data
        prop_def = properties_meta.get(prop_name, {}).get("definition", {})
        declared_type = prop_def.get("dataType", {}).get("type", "").upper()
        
        entry = {
            "entityPropertyReference": {"propertyName": prop_name},
            "values": []
        }
        
        for item in items:
            if prop_name in item:
                value = item[prop_name]
                
                # Determine TwinMaker value type
                if declared_type:
                    type_key = f"{declared_type.capitalize()}Value"
                elif isinstance(value, bool):
                    type_key = "BooleanValue"
                elif isinstance(value, int):
                    type_key = "IntegerValue"
                elif isinstance(value, float):
                    type_key = "DoubleValue"
                else:
                    type_key = "StringValue"
                    value = str(value)
                
                # Get timestamp from item (id or timestamp field)
                timestamp = item.get("timestamp") or item.get("id", "")
                entry["values"].append({
                    "time": timestamp,
                    "value": {type_key: value}
                })
        
        property_values.append(entry)
    
    return {"propertyValues": property_values}


# ==============================================================================
# Hot Reader Invocation
# ==============================================================================

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
    """
    Query remote Hot Reader via HTTP.
    
    Handles two cases:
    1. GCP hot-reader: Use URL query params, transform response to TwinMaker format
    2. Azure hot-reader: POST JSON body, response already in TwinMaker format
    """
    if not REMOTE_READER_URL:
        raise EnvironmentError("REMOTE_READER_URL not configured for multi-cloud mode")
    if not INTER_CLOUD_TOKEN:
        raise EnvironmentError("INTER_CLOUD_TOKEN not configured for multi-cloud mode")
    
    # GCP hot-reader requires URL query params
    if _is_gcp_reader():
        url = _build_gcp_query_url(event)
        print(f"GCP mode: Querying {url}")
        
        # POST with query params works in Flask (request.args populated regardless of method)
        result = post_raw(
            url=url,
            token=INTER_CLOUD_TOKEN,
            payload={}  # Empty body - params are in URL
        )
        raw = json.loads(result.get("body", "{}"))
        print(f"GCP response (pre-transform): {json.dumps(raw)}")
        
        # Transform GCP format to TwinMaker format
        transformed = _transform_gcp_to_twinmaker(raw, event)
        print(f"Transformed to TwinMaker format: {json.dumps(transformed)}")
        return transformed
    
    # Azure/other hot-readers support POST with JSON body and return TwinMaker format
    print(f"Azure mode: POST to {REMOTE_READER_URL}")
    result = post_raw(
        url=REMOTE_READER_URL,
        token=INTER_CLOUD_TOKEN,
        payload=event
    )
    return json.loads(result.get("body", "{}"))


# ==============================================================================
# Lambda Handler
# ==============================================================================

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
        traceback.print_exc()
        # Return empty to avoid breaking TwinMaker dashboard
        print(f"CRITICAL: Data Connector execution failed: {e}")
        raise e
