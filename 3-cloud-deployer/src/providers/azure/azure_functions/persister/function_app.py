"""
Persister Azure Function.

Persists processed device data to storage. In single-cloud mode,
writes directly to Cosmos DB. In multi-cloud mode, POSTs to remote
Hot Writer.

Architecture:
    Processor → Persister → Cosmos DB (or Remote Hot Writer)

Source: src/providers/azure/azure_functions/persister/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func
from azure.cosmos import CosmosClient, PartitionKey

# Handle import path for shared module
try:
    from _shared.inter_cloud import post_to_remote
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_to_remote


def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))

# Cosmos DB config (for single-cloud mode)
COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT", "").strip()
COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY", "").strip()
COSMOS_DB_DATABASE = os.environ.get("COSMOS_DB_DATABASE", "").strip()
COSMOS_DB_CONTAINER = os.environ.get("COSMOS_DB_CONTAINER", "").strip()

# Multi-cloud config (optional)
REMOTE_WRITER_URL = os.environ.get("REMOTE_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Event checking config (optional)
EVENT_CHECKER_FUNCTION_URL = os.environ.get("EVENT_CHECKER_FUNCTION_URL", "").strip()
USE_EVENT_CHECKING = os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true"

# Function base URL for invoking other functions
FUNCTION_APP_BASE_URL = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()

# Cosmos DB client (lazy initialized)
_cosmos_container = None

# Create Function App instance
app = func.FunctionApp()


def _get_cosmos_container():
    """Lazy initialization of Cosmos DB container."""
    global _cosmos_container
    if _cosmos_container is None:
        if not all([COSMOS_DB_ENDPOINT, COSMOS_DB_KEY, COSMOS_DB_DATABASE, COSMOS_DB_CONTAINER]):
            raise ConfigurationError("Cosmos DB configuration incomplete for single-cloud mode")
        
        client = CosmosClient(COSMOS_DB_ENDPOINT, credential=COSMOS_DB_KEY)
        database = client.get_database_client(COSMOS_DB_DATABASE)
        _cosmos_container = database.get_container_client(COSMOS_DB_CONTAINER)
    
    return _cosmos_container


def _is_multi_cloud_storage() -> bool:
    """
    Check if L2 and L3 Hot are on different cloud providers.
    
    Returns True only if:
    1. REMOTE_WRITER_URL is set AND non-empty
    2. layer_2_provider != layer_3_hot_provider
    """
    if not REMOTE_WRITER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        raise ConfigurationError(
            "CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO."
        )
    
    l2_provider = providers.get("layer_2_provider")
    l3_provider = providers.get("layer_3_hot_provider")
    
    if l2_provider is None or l3_provider is None:
        raise ConfigurationError(
            f"CRITICAL: Missing provider mapping. "
            f"layer_2_provider={l2_provider}, layer_3_hot_provider={l3_provider}"
        )
    
    if l2_provider == l3_provider:
        logging.warning(f"REMOTE_WRITER_URL set but providers match ({l2_provider}). Using local Cosmos DB.")
        return False
    
    return True


def _invoke_event_checker(event: dict) -> None:
    """Invoke Event Checker function via HTTP POST."""
    if not EVENT_CHECKER_FUNCTION_URL:
        logging.warning("EVENT_CHECKER_FUNCTION_URL not set - cannot invoke Event Checker")
        return
    
    data = json.dumps(event).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(EVENT_CHECKER_FUNCTION_URL, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Event Checker invoked: {response.getcode()}")
    except Exception as e:
        logging.warning(f"Failed to invoke Event Checker: {e}")
        # Don't fail persister if event checker fails


@app.function_name(name="persister")
@app.route(route="persister", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def persister(req: func.HttpRequest) -> func.HttpResponse:
    """
    Persist processed data to storage.
    
    Routes to either local Cosmos DB or remote Hot Writer
    based on multi-cloud configuration.
    """
    logging.info("Azure Persister: Received request")
    
    try:
        # Parse input data
        event = req.get_json()
        logging.info(f"Event: {json.dumps(event)}")
        
        # Validate required field
        if "time" not in event:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'time' in event"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Build storage item (Cosmos DB requires 'id' as primary key)
        item = event.copy()
        item["id"] = str(item.pop("time"))
        
        # Route based on multi-cloud config
        if _is_multi_cloud_storage():
            logging.info(f"Multi-cloud mode: POSTing to {REMOTE_WRITER_URL}")
            
            if not INTER_CLOUD_TOKEN:
                raise ConfigurationError("INTER_CLOUD_TOKEN required for multi-cloud mode")
            
            result = post_to_remote(
                url=REMOTE_WRITER_URL,
                token=INTER_CLOUD_TOKEN,
                payload=item,
                target_layer="L3"
            )
            logging.info(f"Item persisted to remote cloud: {result}")
        else:
            # Single-cloud: Write to local Cosmos DB
            logging.info("Single-cloud mode: Writing to local Cosmos DB")
            container = _get_cosmos_container()
            container.upsert_item(item)
            logging.info("Item persisted to local Cosmos DB.")
        
        # Optionally invoke Event Checker
        if USE_EVENT_CHECKING:
            _invoke_event_checker(event)
        
        return func.HttpResponse(
            json.dumps({"status": "persisted"}),
            status_code=200,
            mimetype="application/json"
        )
        
    except ConfigurationError as e:
        logging.error(f"Persister Configuration Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Persister Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
