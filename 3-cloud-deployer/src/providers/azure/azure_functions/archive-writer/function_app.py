"""
Archive Writer Azure Function.

Receives data from remote Cold-to-Archive Movers and writes
to Blob Storage (Archive tier).

Architecture:
    Remote Cold-to-Archive Mover → [HTTP POST] → Archive Writer → Blob Archive

Source: src/providers/azure/azure_functions/archive-writer/function_app.py
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
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import MissingEnvironmentVariableError, require_env


# Lazy loading for environment variables to allow Azure function discovery
_inter_cloud_token = None
_blob_connection_string = None
_archive_storage_container = None
_archive_blob_tier = None


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


def _get_archive_storage_container():
    global _archive_storage_container
    if _archive_storage_container is None:
        _archive_storage_container = require_env("ARCHIVE_STORAGE_CONTAINER")
    return _archive_storage_container


def _get_archive_blob_tier():
    global _archive_blob_tier
    if _archive_blob_tier is None:
        _archive_blob_tier = require_env("ARCHIVE_BLOB_TIER")
    return _archive_blob_tier


# Blob container (lazy initialized)
_blob_container_client = None

# Create Function App instance
app = func.FunctionApp()


def _get_blob_container():
    """Lazy initialization of Blob container client."""
    global _blob_container_client
    if _blob_container_client is None:
        blob_service = BlobServiceClient.from_connection_string(_get_blob_connection_string())
        _blob_container_client = blob_service.get_container_client(_get_archive_storage_container())
    return _blob_container_client


@app.function_name(name="archive-writer")
@app.route(route="archive-writer", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def archive_writer(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receive and write data to Blob Archive tier.
    """
    logging.info("Azure Archive Writer: Received request")
    
    try:
        # 1. Validate token
        headers = dict(req.headers)
        if not validate_token(headers, _get_inter_cloud_token()):
            return error_response(
                code="UNAUTHORIZED",
                message="Invalid X-Inter-Cloud-Token",
                status_code=403,
            )

        # 2. Parse body
        body = parse_json_request(req)
        if not isinstance(body, dict):
            return error_response(
                code="INVALID_REQUEST",
                message="Request body must be a JSON object",
                status_code=400,
            )
        
        object_key = body.get("object_key")
        data = body.get("data")
        source_cloud = body.get("source_cloud", "unknown")
        
        if not object_key or data is None:
            return error_response(
                code="INVALID_REQUEST",
                message="Missing required fields: object_key, data",
                status_code=400,
            )
        
        logging.info(f"Received '{object_key}' from {source_cloud}")
        
        # 3. Write to Blob Archive tier
        container = _get_blob_container()
        blob_client = container.get_blob_client(object_key)
        
        # Upload with Archive tier
        blob_client.upload_blob(
            data,
            overwrite=True,
            standard_blob_tier=_get_archive_blob_tier()
        )
        
        logging.info(f"Wrote {object_key} to archive tier")
        
        return func.HttpResponse(
            json.dumps({"archived": True, "key": object_key}),
            status_code=200,
            mimetype="application/json"
        )
        
    except InvalidRequestBody:
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid JSON",
            status_code=400,
        )

    except MissingEnvironmentVariableError as exc:
        return failure_response(
            component="azure.archive-writer.configuration",
            error=exc,
            code="CONFIGURATION_ERROR",
            message="Archive writer configuration is unavailable.",
            status_code=500,
        )

    except Exception as exc:
        return failure_response(
            component="azure.archive-writer",
            error=exc,
        )
