"""
Hot Reader Last Entry Azure Function.

Queries Cosmos DB for the most recent entry per device.

Architecture:
    ADT / Remote Data Connector → Hot Reader Last Entry → Cosmos DB

Source: src/providers/azure/azure_functions/hot-reader-last-entry/function_app.py
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


# Optional: For cross-cloud HTTP access
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

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


def _query_last_entry(query_params: dict) -> dict:
    """
    Query Cosmos DB for last entry.
    
    Args:
        query_params: Query with entityId, componentName, selectedProperties, etc.
    
    Returns:
        dict: ADT-compatible last entry response
    """
    container = _get_cosmos_container()
    
    entity_id = query_params.get("entityId")
    component_name = query_params.get("componentName")
    selected_properties = query_params.get("selectedProperties", [])
    properties_metadata = query_params.get("properties", {})
    
    # Get IoT device ID from component
    twin_info = _get_digital_twin_info()
    twin_name = twin_info["config"]["digital_twin_name"]
    iot_device_id = component_name or entity_id
    
    # Query for the most recent item
    query = """
        SELECT TOP 1 * FROM c 
        WHERE c.device_id = @device_id 
        ORDER BY c.id DESC
    """
    
    parameters = [{"name": "@device_id", "value": iot_device_id}]
    
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if not items:
        return {"propertyValues": {}}
    
    item = items[0]
    logging.info(f"Found last entry for device {iot_device_id}: id={item.get('id')}")
    
    # Build ADT-compatible response
    property_values = {}
    for property_name in selected_properties:
        if property_name in item:
            prop_meta = properties_metadata.get(property_name, {})
            prop_def = prop_meta.get("definition", {})
            data_type = prop_def.get("dataType", {}).get("type", "STRING")
            property_type = f"{data_type.capitalize()}Value"
            
            property_values[property_name] = {
                "value": {property_type: item[property_name]},
                "time": item["id"]
            }
    
    return {"propertyValues": property_values}


@bp.function_name(name="hot-reader-last-entry")
@bp.route(route="hot-reader-last-entry", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def hot_reader_last_entry(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query Cosmos DB for most recent entry per device.
    """
    logging.info("Azure Hot Reader Last Entry: Received request")
    
    try:
        headers = dict(req.headers)
        
        # Validate token for cross-cloud requests
        if "x-inter-cloud-token" in headers or "X-Inter-Cloud-Token" in headers:
            if not validate_token(headers, INTER_CLOUD_TOKEN):
                return func.HttpResponse(
                    json.dumps({"error": "Unauthorized"}),
                    status_code=401,
                    mimetype="application/json"
                )
        
        query_params = req.get_json()
        result = _query_last_entry(query_params)
        
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.exception(f"Hot Reader Last Entry Error: {e}")
        return func.HttpResponse(
            json.dumps({"propertyValues": {}}),
            status_code=200,
            mimetype="application/json"
        )
