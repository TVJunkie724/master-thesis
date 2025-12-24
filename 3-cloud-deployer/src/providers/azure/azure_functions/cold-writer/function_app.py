"""
Cold Writer Azure Function.

Receives chunked data from remote Hot-to-Cold Movers and writes
to Blob Storage (Cool tier).

Architecture:
    Remote Hot-to-Cold Mover → [HTTP POST] → Cold Writer → Blob Cool

Source: src/providers/azure/azure_functions/cold-writer/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging

import azure.functions as func
from azure.storage.blob import BlobServiceClient

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
_blob_connection_string = None
_cold_storage_container = None


def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token


def _get_blob_connection_string():
    global _blob_connection_string
    if _blob_connection_string is None:
        _blob_connection_string = require_env("BLOB_CONNECTION_STRING")
    return _blob_connection_string


def _get_cold_storage_container():
    global _cold_storage_container
    if _cold_storage_container is None:
        _cold_storage_container = require_env("COLD_STORAGE_CONTAINER")
    return _cold_storage_container


# Blob container (lazy initialized)
_blob_container_client = None

# Create Function App instance
app = func.FunctionApp()


def _get_blob_container():
    """Lazy initialization of Blob container client."""
    global _blob_container_client
    if _blob_container_client is None:
        blob_service = BlobServiceClient.from_connection_string(_get_blob_connection_string())
        _blob_container_client = blob_service.get_container_client(_get_cold_storage_container())
    return _blob_container_client


@app.function_name(name="cold-writer")
@app.route(route="cold-writer", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def cold_writer(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receive and write chunked data from remote movers.
    
    Validates token, parses chunk payload, writes to Blob Storage Cool tier.
    """
    logging.info("Azure Cold Writer: Received request")
    
    try:
        # 1. Validate token
        headers = dict(req.headers)
        if not validate_token(headers, _get_inter_cloud_token()):
            return func.HttpResponse(
                json.dumps({"error": "Unauthorized"}),
                status_code=403,
                mimetype="application/json"
            )
        
        # 2. Parse body
        body = req.get_json()
        
        iot_device_id = body.get("iot_device_id")
        chunk_index = body.get("chunk_index")
        start_timestamp = body.get("start_timestamp")
        end_timestamp = body.get("end_timestamp")
        items = body.get("items")
        source_cloud = body.get("source_cloud", "unknown")
        
        # 3. Validate required fields
        if not all([iot_device_id, chunk_index is not None, start_timestamp, end_timestamp, items]):
            return func.HttpResponse(
                json.dumps({"error": "Missing required fields"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not isinstance(items, list):
            return func.HttpResponse(
                json.dumps({"error": "'items' must be a list"}),
                status_code=400,
                mimetype="application/json"
            )
        
        logging.info(f"Received {len(items)} items from {source_cloud}")
        
        # 4. Write to Blob Storage with Cool tier
        container = _get_blob_container()
        blob_name = f"{iot_device_id}/{start_timestamp}-{end_timestamp}/chunk-{chunk_index:05d}.json"
        
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(
            json.dumps(items, default=str),
            overwrite=True,
            standard_blob_tier="Cool"
        )
        
        logging.info(f"Wrote {len(items)} items to blob: {blob_name}")
        
        return func.HttpResponse(
            json.dumps({"written": len(items), "key": blob_name}),
            status_code=200,
            mimetype="application/json"
        )
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Cold Writer Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
