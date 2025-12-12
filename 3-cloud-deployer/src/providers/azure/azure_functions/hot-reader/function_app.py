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
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import validate_token
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
COSMOS_DB_ENDPOINT = require_env("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = require_env("COSMOS_DB_KEY")
COSMOS_DB_DATABASE = require_env("COSMOS_DB_DATABASE")
COSMOS_DB_CONTAINER = require_env("COSMOS_DB_CONTAINER")

# Optional: For cross-cloud HTTP access
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Optional: Azure Digital Twins instance URL
ADT_INSTANCE_URL = os.environ.get("ADT_INSTANCE_URL", "").strip()

# Cosmos DB client (lazy initialized)
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
    # Component type follows pattern: {twin_name}-{device_id}
    twin_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"]
    
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
        except Exception as e:
            logging.warning(f"Failed to get entity from ADT: {e}")
    
    if not iot_device_id:
        # Fallback: try to extract from component name or entity ID
        iot_device_id = component_name or entity_id
    
    # Query Cosmos DB
    query = f"""
        SELECT * FROM c 
        WHERE c.iotDeviceId = @device_id 
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


@app.function_name(name="hot-reader")
@app.route(route="hot-reader", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def hot_reader(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query Cosmos DB for time-range data.
    
    Supports both direct invocation (Azure Digital Twins) and
    remote HTTP requests (cross-cloud L4).
    """
    logging.info("Azure Hot Reader: Received request")
    
    try:
        headers = dict(req.headers)
        
        # Validate token for cross-cloud requests
        if _is_http_request_with_token(headers):
            logging.info("Cross-cloud request - validating token")
            if not validate_token(headers, INTER_CLOUD_TOKEN):
                return func.HttpResponse(
                    json.dumps({"error": "Unauthorized", "message": "Invalid X-Inter-Cloud-Token"}),
                    status_code=401,
                    mimetype="application/json"
                )
        
        # Parse query parameters
        query_params = req.get_json()
        logging.info(f"Query: {json.dumps(query_params)}")
        
        # Query Cosmos DB
        result = _query_cosmos_db(query_params)
        
        return func.HttpResponse(
            json.dumps(result),
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
        logging.error(f"Hot Reader Error: {e}")
        # Return empty to avoid breaking dashboard
        return func.HttpResponse(
            json.dumps({"propertyValues": []}),
            status_code=200,
            mimetype="application/json"
        )
