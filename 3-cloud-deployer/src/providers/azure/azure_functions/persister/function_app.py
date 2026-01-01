"""
Persister Azure Function.

Persists processed device data to storage. In single-cloud mode,
writes directly to Cosmos DB. In multi-cloud mode, POSTs to remote
Hot Writer.

Architecture:
    Processor → Persister → Cosmos DB (or Remote Hot Writer)

SECURITY NOTE - AuthLevel.ANONYMOUS
==================================
This function uses AuthLevel.ANONYMOUS instead of AuthLevel.FUNCTION due to a
Terraform infrastructure limitation:

Problem: When deploying Azure Function Apps with Terraform, retrieving the
function's host key creates a circular dependency:
  1. L2 Function App needs L2_FUNCTION_KEY in its app_settings
  2. L2_FUNCTION_KEY comes from data.azurerm_function_app_host_keys.l2
  3. That data source depends on the L2 Function App being created
  4. CYCLE: L2 App → data.l2 → L2 App

Terraform cannot resolve this cycle, causing deployment to fail.

Workaround: Internal L2 functions (persister, event-checker) that are only
called by other L2 functions use AuthLevel.ANONYMOUS. This is acceptable because:
  - These endpoints are NOT exposed to the public internet directly
  - They are only called by processor_wrapper and persister (same Function App)
  - Network-level security (Azure VNet, Private Endpoints) can be added for
    production deployments
  - The X-Inter-Cloud-Token pattern is still available for cross-cloud calls

Future Fix: See docs/future-work.md for proper solutions when Terraform
supports post-deployment app_settings updates or two-phase deployments.

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
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


# DIGITAL_TWIN_INFO is lazy-loaded to allow Azure function discovery
# (module-level require_env would fail during import if env var is missing)
_digital_twin_info = None

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

# Cosmos DB config (for single-cloud mode)
COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT", "").strip()
COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY", "").strip()
COSMOS_DB_DATABASE = os.environ.get("COSMOS_DB_DATABASE", "").strip()
COSMOS_DB_CONTAINER = os.environ.get("COSMOS_DB_CONTAINER", "").strip()

# Multi-cloud config (optional)
REMOTE_WRITER_URL = os.environ.get("REMOTE_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# ADT Pusher config (for multi-cloud L4 - L2 != L4 and L4 = Azure)
REMOTE_ADT_PUSHER_URL = os.environ.get("REMOTE_ADT_PUSHER_URL", "").strip()
ADT_PUSHER_TOKEN = os.environ.get("ADT_PUSHER_TOKEN", "").strip()

# Event checking config (optional)
EVENT_CHECKER_FUNCTION_URL = os.environ.get("EVENT_CHECKER_FUNCTION_URL", "").strip()
USE_EVENT_CHECKING = os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true"

# Function base URL for invoking other functions
FUNCTION_APP_BASE_URL = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()

# NOTE: _l2_function_key removed - event-checker is now AuthLevel.ANONYMOUS (Terraform cycle workaround)

# Cosmos DB client (lazy initialized)
_cosmos_container = None

# Create Blueprint for registration in main function_app.py
bp = func.Blueprint()


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
    
    providers = _get_digital_twin_info().get("config_providers")
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
        raise ConfigurationError(f"REMOTE_WRITER_URL set but providers match ({l2_provider}). Invalid configuration.")
    
    return True


def _invoke_event_checker(event: dict) -> None:
    """
    Invoke Event Checker function via HTTP POST.
    
    NOTE: Event Checker uses AuthLevel.ANONYMOUS (no function key required).
    This is a workaround for Terraform cycle limitations - see event-checker/function_app.py
    for full security documentation.
    """
    if not EVENT_CHECKER_FUNCTION_URL:
        logging.warning("EVENT_CHECKER_FUNCTION_URL not set - cannot invoke Event Checker")
        return
    
    # No function key needed - event-checker uses AuthLevel.ANONYMOUS
    data = json.dumps(event).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(EVENT_CHECKER_FUNCTION_URL, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Event Checker invoked: {response.getcode()}")
    except Exception as e:
        logging.warning(f"Failed to invoke Event Checker: {e}")
        # Don't fail persister if event checker fails


def _should_push_to_adt() -> bool:
    """
    Check if we should push data to remote ADT Pusher.
    
    Returns True only if:
    1. REMOTE_ADT_PUSHER_URL is set AND non-empty
    2. ADT_PUSHER_TOKEN is set AND non-empty
    
    ADT push is for multi-cloud L4 scenarios where L2 != L4 and L4 = Azure.
    """
    return bool(REMOTE_ADT_PUSHER_URL and ADT_PUSHER_TOKEN)


def _push_to_adt(event: dict) -> None:
    """
    Push telemetry to remote ADT Pusher (L4 Multi-Cloud).
    
    This is called IN ADDITION TO storage persist, not instead of it.
    Failures are logged but don't fail the overall persist operation.
    
    Args:
        event: Original telemetry event (with 'time' field)
    """
    if not _should_push_to_adt():
        return
    
    logging.info(f"Pushing to ADT Pusher at {REMOTE_ADT_PUSHER_URL}")
    
    try:
        # Build ADT push payload
        adt_payload = {
            "device_id": event.get("device_id"),
            "device_type": event.get("device_type"),
            "telemetry": event.get("telemetry", {}),
            "timestamp": event.get("timestamp") or event.get("time")
        }
        
        result = post_to_remote(
            url=REMOTE_ADT_PUSHER_URL,
            token=ADT_PUSHER_TOKEN,
            payload=adt_payload,
            target_layer="L4"
        )
        logging.info(f"ADT push successful: {result}")
    except Exception as e:
        # Log but don't fail - ADT is secondary to storage
        logging.warning(f"ADT push failed (non-fatal): {e}")


# ==========================================
# Configuration Validation
# ==========================================

def _validate_config():
    """
    Validate configuration at runtime based on active mode.
    Raises ConfigurationError if invalid.
    """
    if not _is_multi_cloud_storage():
        # Single-cloud mode requires Cosmos DB config
        if not all([COSMOS_DB_ENDPOINT, COSMOS_DB_KEY, COSMOS_DB_DATABASE, COSMOS_DB_CONTAINER]):
            raise ConfigurationError(
                "Cosmos DB configuration (ENDPOINT, KEY, DATABASE, CONTAINER) "
                "is required for single-cloud storage mode"
            )


@bp.function_name(name="persister")
# AuthLevel.ANONYMOUS: See module docstring for Terraform cycle limitation explanation
@bp.route(route="persister", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def persister(req: func.HttpRequest) -> func.HttpResponse:
    """
    Persist processed data to storage.
    
    Routes to either local Cosmos DB or remote Hot Writer
    based on multi-cloud configuration.
    """
    logging.info("Azure Persister: Received request")
    
    # Fail-fast validation
    _validate_config()
    
    try:
        # Parse input data
        event = req.get_json()
        logging.info(f"Event: {json.dumps(event)}")
        
        # Build storage item (Cosmos DB requires 'id' as primary key)
        item = event.copy()
        
        # After normalization, event has 'timestamp' field (canonical)
        # Use 'timestamp' as the document ID for consistency with other clouds
        timestamp_value = item.get("timestamp")
        if timestamp_value:
            item["id"] = str(timestamp_value)
        else:
            # Fallback: generate a unique ID using current timestamp + UUID
            import uuid
            from datetime import datetime
            timestamp = datetime.utcnow().isoformat() + "Z"
            item["id"] = f"{timestamp}_{uuid.uuid4().hex[:8]}"
            item["timestamp"] = timestamp  # Ensure timestamp field exists
            logging.info(f"Generated document ID: {item['id']}")
        
        # Remove 'time' to avoid duplicate data (timestamp is canonical)
        item.pop("time", None)
        
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
        
        # Multi-cloud L4: Push to ADT Pusher (IN ADDITION to storage)
        # This is for scenarios where L2 != L4 and L4 = Azure
        _push_to_adt(event)
        
        # Optionally invoke Event Checker
        if USE_EVENT_CHECKING:
            _invoke_event_checker(event)
        
        return func.HttpResponse(
            json.dumps({"status": "persisted"}),
            status_code=200,
            mimetype="application/json"
        )
        
    except ConfigurationError as e:
        logging.exception(f"Persister Configuration Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Configuration error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.exception(f"Persister Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Persister error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
