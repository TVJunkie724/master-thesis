"""
Hot Writer Azure Function.

Receives data from remote Persisters and writes to local Cosmos DB.
This is the multi-cloud receiver for L3 Hot storage.

Architecture:
    Remote Persister → [HTTP POST] → Hot Writer → Cosmos DB

Source: src/providers/azure/azure_functions/hot-writer/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging

import azure.functions as func
from azure.cosmos import CosmosClient

# Handle import path for shared module
try:
    from _shared.inter_cloud import validate_token
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import validate_token


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


# Required environment variables - fail fast if missing
INTER_CLOUD_TOKEN = _require_env("INTER_CLOUD_TOKEN")
COSMOS_DB_ENDPOINT = _require_env("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = _require_env("COSMOS_DB_KEY")
COSMOS_DB_DATABASE = _require_env("COSMOS_DB_DATABASE")
COSMOS_DB_CONTAINER = _require_env("COSMOS_DB_CONTAINER")

# Cosmos DB container (lazy initialized)
_cosmos_container = None

# Create Function App instance
app = func.FunctionApp()


def _get_cosmos_container():
    """Lazy initialization of Cosmos DB container."""
    global _cosmos_container
    if _cosmos_container is None:
        client = CosmosClient(COSMOS_DB_ENDPOINT, credential=COSMOS_DB_KEY)
        database = client.get_database_client(COSMOS_DB_DATABASE)
        _cosmos_container = database.get_container_client(COSMOS_DB_CONTAINER)
    return _cosmos_container


@app.function_name(name="hot-writer")
@app.route(route="hot-writer", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def hot_writer(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receive and write data from remote Persister.
    
    Validates token, extracts payload, writes to Cosmos DB.
    """
    logging.info("Azure Hot Writer: Received request")
    
    try:
        # 1. Validate token
        headers = dict(req.headers)
        if not validate_token(headers, INTER_CLOUD_TOKEN):
            return func.HttpResponse(
                json.dumps({"error": "Unauthorized", "message": "Invalid X-Inter-Cloud-Token"}),
                status_code=403,
                mimetype="application/json"
            )
        
        # 2. Parse body
        body = req.get_json()
        source_cloud = body.get("source_cloud", "unknown")
        logging.info(f"Received from: {source_cloud}")
        
        # 3. Extract payload (may be wrapped in envelope or direct)
        payload = body.get("payload")
        if payload is None:
            payload = body  # Direct payload (no envelope)
        
        if not isinstance(payload, dict):
            return func.HttpResponse(
                json.dumps({"error": "Bad Request", "message": "Payload must be a JSON object"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # 4. Ensure required fields for Cosmos DB
        if "id" not in payload and "time" in payload:
            payload["id"] = str(payload.pop("time"))
        
        if "iotDeviceId" not in payload:
            return func.HttpResponse(
                json.dumps({"error": "Bad Request", "message": "Missing 'iotDeviceId'"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # 5. Write to Cosmos DB
        container = _get_cosmos_container()
        container.upsert_item(payload)
        logging.info(f"Wrote item to Cosmos DB: id={payload.get('id')}")
        
        return func.HttpResponse(
            json.dumps({"status": "written", "id": payload.get("id")}),
            status_code=200,
            mimetype="application/json"
        )
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Bad Request", "message": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Hot Writer Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
