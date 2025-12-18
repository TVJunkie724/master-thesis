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
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env


# Lazy loading for environment variables to allow Azure function discovery
_inter_cloud_token = None
_cosmos_db_endpoint = None
_cosmos_db_key = None
_cosmos_db_database = None
_cosmos_db_container = None

def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token

def _get_cosmos_db_endpoint():
    global _cosmos_db_endpoint
    if _cosmos_db_endpoint is None:
        _cosmos_db_endpoint = require_env("COSMOS_DB_ENDPOINT")
    return _cosmos_db_endpoint

def _get_cosmos_db_key():
    global _cosmos_db_key
    if _cosmos_db_key is None:
        _cosmos_db_key = require_env("COSMOS_DB_KEY")
    return _cosmos_db_key

def _get_cosmos_db_database():
    global _cosmos_db_database
    if _cosmos_db_database is None:
        _cosmos_db_database = require_env("COSMOS_DB_DATABASE")
    return _cosmos_db_database

def _get_cosmos_db_container_name():
    global _cosmos_db_container
    if _cosmos_db_container is None:
        _cosmos_db_container = require_env("COSMOS_DB_CONTAINER")
    return _cosmos_db_container


# Cosmos DB container (lazy initialized)
_cosmos_container_client = None

# Create Blueprint for registration by main function_app.py
bp = func.Blueprint()


def _get_cosmos_container():
    """Lazy initialization of Cosmos DB container."""
    global _cosmos_container_client
    if _cosmos_container_client is None:
        client = CosmosClient(_get_cosmos_db_endpoint(), credential=_get_cosmos_db_key())
        database = client.get_database_client(_get_cosmos_db_database())
        _cosmos_container_client = database.get_container_client(_get_cosmos_db_container_name())
    return _cosmos_container_client


@bp.function_name(name="hot-writer")
@bp.route(route="hot-writer", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def hot_writer(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receive and write data from remote Persister.
    
    Validates token, extracts payload, writes to Cosmos DB.
    """
    logging.info("Azure Hot Writer: Received request")
    
    try:
        # 1. Validate token
        headers = dict(req.headers)
        if not validate_token(headers, _get_inter_cloud_token()):
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
