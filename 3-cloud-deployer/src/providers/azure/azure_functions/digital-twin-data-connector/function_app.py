"""
Digital Twin Data Connector Azure Function.

Routes Azure Digital Twins queries to the appropriate Hot Reader
(local or remote). This is the bridge between L4 and L3.

Architecture:
    Azure Digital Twins → Data Connector → Hot Reader (local/remote)

Source: src/providers/azure/azure_functions/digital-twin-data-connector/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func

# Handle import path for shared module
try:
    from _shared.inter_cloud import post_raw
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_raw


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))

# Multi-cloud configuration
LOCAL_HOT_READER_URL = os.environ.get("LOCAL_HOT_READER_URL", "").strip()
REMOTE_READER_URL = os.environ.get("REMOTE_READER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Create Function App instance
app = func.FunctionApp()


def _is_multi_cloud() -> bool:
    """Check if L3 and L4 are on different clouds."""
    return bool(REMOTE_READER_URL)


def _invoke_local_hot_reader(query: dict) -> dict:
    """
    Invoke local Hot Reader via HTTP.
    
    Args:
        query: Query parameters for Hot Reader
    
    Returns:
        dict: Query results
    """
    if not LOCAL_HOT_READER_URL:
        raise EnvironmentError("LOCAL_HOT_READER_URL not configured")
    
    data = json.dumps(query).encode('utf-8')
    req = urllib.request.Request(
        LOCAL_HOT_READER_URL,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _query_remote_hot_reader(query: dict) -> dict:
    """
    Query remote Hot Reader via HTTP POST.
    
    Args:
        query: Query parameters
    
    Returns:
        dict: Query results
    """
    if not REMOTE_READER_URL:
        raise EnvironmentError("REMOTE_READER_URL not configured")
    if not INTER_CLOUD_TOKEN:
        raise EnvironmentError("INTER_CLOUD_TOKEN not configured")
    
    result = post_raw(
        url=REMOTE_READER_URL,
        token=INTER_CLOUD_TOKEN,
        payload=query
    )
    
    return json.loads(result.get("body", "{}"))


@app.function_name(name="digital-twin-data-connector")
@app.route(route="digital-twin-data-connector", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def digital_twin_data_connector(req: func.HttpRequest) -> func.HttpResponse:
    """
    Route Azure Digital Twins query to Hot Reader.
    
    Args:
        req: HTTP request with ADT query
    
    Returns:
        func.HttpResponse: Query results in ADT format
    """
    logging.info("Azure Digital Twin Data Connector: Received request")
    
    try:
        query = req.get_json()
        logging.info(f"Query: {json.dumps(query)}")
        
        if _is_multi_cloud():
            logging.info(f"Multi-cloud: Routing to {REMOTE_READER_URL}")
            result = _query_remote_hot_reader(query)
        else:
            logging.info(f"Single-cloud: Routing to {LOCAL_HOT_READER_URL}")
            result = _invoke_local_hot_reader(query)
        
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Data Connector Error: {e}")
        return func.HttpResponse(
            json.dumps({"propertyValues": []}),
            status_code=200,
            mimetype="application/json"
        )
