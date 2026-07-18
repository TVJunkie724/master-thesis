"""
Hot Reader Azure Function.

Queries Cosmos DB for time-range data. Provides data to L4 (Azure Digital Twins)
or remote L4 via Function URL.

Architecture:
    ADT / Remote Data Connector → Hot Reader → Cosmos DB

Source: src/providers/azure/azure_functions/hot-reader/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.digitaltwins.core import DigitalTwinsClient
from azure.identity import DefaultAzureCredential

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
_digital_twin_info = None
_cosmos_db_endpoint = None
_cosmos_db_key = None
_cosmos_db_database = None
_cosmos_db_container = None

def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

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


def _get_inter_cloud_token():
    """
    Get inter-cloud token for authentication.
    
    Returns empty string in single-cloud mode (token not configured).
    In single-cloud, all communication is internal so auth is optional.
    """
    return os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Optional: Azure Digital Twins instance URL
ADT_INSTANCE_URL = os.environ.get("ADT_INSTANCE_URL", "").strip()

# Cosmos DB client (lazy initialized)
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


def _is_http_request_with_token(headers: dict) -> bool:
    """Check if this is an HTTP request that should validate token."""
    return "x-inter-cloud-token" in headers or "X-Inter-Cloud-Token" in headers


def _query_cosmos_db(query_params: dict) -> dict:
    """
    Query Cosmos DB for time-range data.
    
    Args:
        query_params: Query with entityId, startTime, endTime, selectedProperties, etc.
    
    Returns:
        dict: Azure Digital Twins compatible response
    """
    container = _get_cosmos_container()
    
    # Extract device ID from entity/component mapping
    entity_id = query_params.get("entityId")
    component_name = query_params.get("componentName")
    start_time = query_params.get("startTime")
    end_time = query_params.get("endTime")
    selected_properties = query_params.get("selectedProperties", [])
    properties_metadata = query_params.get("properties", {})
    
    # Get IoT device ID from component type
    twin_info = _get_digital_twin_info()
    twin_name = twin_info["config"]["digital_twin_name"]
    
    # Query ADT to get the device ID if ADT_INSTANCE_URL is available
    iot_device_id = None
    if ADT_INSTANCE_URL:
        try:
            credential = DefaultAzureCredential()
            adt_client = DigitalTwinsClient(ADT_INSTANCE_URL, credential)
            entity = adt_client.get_digital_twin(entity_id)
            
            # Extract component info
            components = entity.get("$metadata", {})
            if component_name in components:
                component_type = components[component_name].get("$model", "")
                iot_device_id = component_type.replace(f"{twin_name}-", "")
        except Exception as exc:
            logging.warning(
                "Failed to get entity from ADT: %s",
                type(exc).__name__,
            )
    
    if not iot_device_id:
        # Fallback: try to extract from component name or entity ID
        iot_device_id = component_name or entity_id
    
    # Query Cosmos DB
    query = """
        SELECT * FROM c 
        WHERE c.device_id = @device_id 
        AND c.id >= @start_time 
        AND c.id <= @end_time
        ORDER BY c.id ASC
    """
    
    parameters = [
        {"name": "@device_id", "value": iot_device_id},
        {"name": "@start_time", "value": start_time},
        {"name": "@end_time", "value": end_time}
    ]
    
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    logging.info(f"Found {len(items)} items for device {iot_device_id}")
    
    # Build ADT-compatible response
    property_values = []
    for property_name in selected_properties:
        prop_meta = properties_metadata.get(property_name, {})
        prop_def = prop_meta.get("definition", {})
        data_type = prop_def.get("dataType", {}).get("type", "STRING")
        property_type = f"{data_type.capitalize()}Value"

        entry = {
            "entityPropertyReference": {
                "propertyName": property_name
            },
            "values": []
        }
        
        for item in items:
            if property_name in item:
                entry["values"].append({
                    "time": item["id"],
                    "value": {property_type: item[property_name]}
                })
        
        property_values.append(entry)
    
    return {"propertyValues": property_values}


@bp.function_name(name="hot-reader")
@bp.route(route="hot-reader", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS)
def hot_reader(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query Cosmos DB for time-range data.
    
    Supports both direct invocation (Azure Digital Twins) and
    remote HTTP requests (cross-cloud L4).
    
    Methods:
        GET: Simple queries with query parameters (device_id, limit)
        POST: Complex ADT-compatible queries with JSON body
    """
    logging.info("Azure Hot Reader: Received request")
    
    try:
        headers = dict(req.headers)
        
        # Validate token for cross-cloud requests (skip in single-cloud mode)
        # In single-cloud, INTER_CLOUD_TOKEN is not set - skip authentication.
        # In multi-cloud, token is required for security.
        token = _get_inter_cloud_token()
        if token and not validate_token(headers, token):
            return error_response(
                code="UNAUTHORIZED",
                message="Invalid or missing X-Inter-Cloud-Token",
                status_code=401,
            )
        
        # Handle GET requests (simple queries from E2E tests and basic API clients)
        if req.method == "GET":
            device_id = req.params.get("device_id") or req.params.get("iotDeviceId")
            try:
                limit = int(req.params.get("limit", "100"))
            except (TypeError, ValueError):
                return error_response(
                    code="INVALID_REQUEST",
                    message="Query parameter 'limit' must be an integer",
                    status_code=400,
                )
            
            container = _get_cosmos_container()
            
            # Build query
            if device_id:
                query = "SELECT TOP @limit * FROM c WHERE c.device_id = @device_id ORDER BY c.timestamp DESC"
                parameters = [
                    {"name": "@device_id", "value": device_id},
                    {"name": "@limit", "value": limit}
                ]
            else:
                query = "SELECT TOP @limit * FROM c ORDER BY c.timestamp DESC"
                parameters = [{"name": "@limit", "value": limit}]
            
            items = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            logging.info(f"GET query returned {len(items)} items for device {device_id}")
            
            return func.HttpResponse(
                json.dumps({"items": items, "count": len(items)}),
                status_code=200,
                mimetype="application/json"
            )
        
        # Handle POST requests (complex ADT-compatible queries)
        query_params = parse_json_request(req)
        if not isinstance(query_params, dict):
            return error_response(
                code="INVALID_REQUEST",
                message="Request body must be a JSON object",
                status_code=400,
            )
        logging.info("Received a hot-reader query")
        
        # Query Cosmos DB
        result = _query_cosmos_db(query_params)
        
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        
    except InvalidRequestBody:
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid JSON",
            status_code=400,
        )

    except (MissingEnvironmentVariableError, json.JSONDecodeError) as exc:
        return failure_response(
            component="azure.hot-reader.configuration",
            error=exc,
            code="CONFIGURATION_ERROR",
            message="Hot reader configuration is unavailable.",
            status_code=500,
        )

    except Exception as exc:
        return failure_response(
            component="azure.hot-reader",
            error=exc,
        )
