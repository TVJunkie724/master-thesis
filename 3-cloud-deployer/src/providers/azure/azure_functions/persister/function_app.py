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
from azure.cosmos import CosmosClient

# Handle import path for shared module
try:
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, log_runtime_failure, parse_json_request
    from _shared.inter_cloud import post_to_remote, safe_urlopen, validate_https_url
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, log_runtime_failure, parse_json_request
    from _shared.inter_cloud import post_to_remote, safe_urlopen, validate_https_url
    from _shared.env_utils import MissingEnvironmentVariableError, require_env


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


class AdtDeliveryError(Exception):
    """Raised when required Azure Digital Twins delivery fails."""


class PayloadValidationError(ValueError):
    """Raised when telemetry cannot satisfy the persistence contract."""


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

# ADT Pusher config (required whenever L4 is Azure)
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
        with safe_urlopen(req, timeout=30) as response:
            logging.info(f"Event Checker invoked: {response.getcode()}")
    except Exception as exc:
        log_runtime_failure(
            "azure.persister.optional-event-checker",
            exc,
        )
        # Don't fail persister if event checker fails


def _get_adt_delivery_settings() -> tuple[str, str] | None:
    """Resolve required ADT delivery settings from the configured L4 provider."""
    providers = _get_digital_twin_info().get("config_providers")
    if not isinstance(providers, dict):
        raise ConfigurationError(
            "config_providers is required in DIGITAL_TWIN_INFO"
        )

    layer_4_provider = providers.get("layer_4_provider")
    if not isinstance(layer_4_provider, str) or not layer_4_provider.strip():
        raise ConfigurationError("layer_4_provider is required")
    if layer_4_provider.lower() != "azure":
        return None

    if not REMOTE_ADT_PUSHER_URL:
        raise ConfigurationError(
            "REMOTE_ADT_PUSHER_URL is required when L4 is Azure"
        )
    if not ADT_PUSHER_TOKEN:
        raise ConfigurationError("ADT_PUSHER_TOKEN is required when L4 is Azure")
    try:
        validate_https_url(REMOTE_ADT_PUSHER_URL)
    except ValueError:
        raise ConfigurationError(
            "REMOTE_ADT_PUSHER_URL must be an absolute HTTPS URL"
        ) from None
    return REMOTE_ADT_PUSHER_URL, ADT_PUSHER_TOKEN


def _build_adt_payload(event: dict) -> dict:
    """Build the provider-neutral telemetry payload accepted by ADT Pusher."""
    telemetry = event.get("telemetry")
    if telemetry is None:
        excluded_keys = {
            "device_id",
            "device_type",
            "id",
            "time",
            "timestamp",
            "ts",
            "telemetry",
        }
        telemetry = {key: value for key, value in event.items() if key not in excluded_keys}
    if not isinstance(telemetry, dict) or not telemetry:
        raise PayloadValidationError(
            "Telemetry payload must be a non-empty object"
        )

    return {
        "device_id": event.get("device_id"),
        "device_type": event.get("device_type"),
        "telemetry": telemetry,
        "timestamp": event.get("timestamp") or event.get("time"),
    }


def _push_to_adt(event: dict) -> None:
    """
    Push telemetry to the canonical Azure L4 ADT Pusher.

    This is called in addition to the idempotent storage write. Required
    delivery failures propagate so callers can retry the complete operation.
    
    Args:
        event: Original telemetry event (with 'time' field)
    """
    settings = _get_adt_delivery_settings()
    if settings is None:
        return
    remote_url, token = settings

    try:
        post_to_remote(
            url=remote_url,
            token=token,
            payload=_build_adt_payload(event),
            target_layer="L4",
        )
        logging.info("ADT push completed")
    except (ConfigurationError, PayloadValidationError):
        raise
    except Exception as exc:
        logging.error("ADT push failed: %s", type(exc).__name__)
        raise AdtDeliveryError("Azure Digital Twins update failed") from None


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
    _get_adt_delivery_settings()


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

    try:
        # Fail-fast validation remains inside the stable HTTP error boundary.
        _validate_config()

        # Parse input data
        event = parse_json_request(req)
        if not isinstance(event, dict):
            return error_response(
                code="INVALID_REQUEST",
                message="Request body must be a JSON object",
                status_code=400,
            )
        logging.info("Event received")
        
        # Build storage item (Cosmos DB requires 'id' as primary key)
        item = event.copy()
        
        # Generate document ID (consistent across all clouds)
        # ID format: {device_id}_{timestamp} for uniqueness and traceability
        # Timestamp is ISO8601 string from normalize_telemetry() (e.g., "2026-01-28T12:00:00Z")
        timestamp_value = item.get("timestamp")
        device_id = item.get("device_id")
        
        if not device_id:
            logging.error("Missing 'device_id' in event - cannot generate document ID")
            return error_response(
                code="INVALID_REQUEST",
                message="Missing 'device_id' in event",
                status_code=400,
            )
        
        if not timestamp_value:
            logging.error("Missing 'timestamp' in event - cannot generate document ID")
            return error_response(
                code="INVALID_REQUEST",
                message="Missing 'timestamp' in event",
                status_code=400,
            )
        
        item["id"] = f"{device_id}_{timestamp_value}"
        
        # Remove 'time' to avoid duplicate data (timestamp is canonical)
        item.pop("time", None)

        # Reject known Azure L4 payload errors before the storage write.
        if _get_adt_delivery_settings() is not None:
            _build_adt_payload(event)
        
        # Route based on multi-cloud config
        if _is_multi_cloud_storage():
            logging.info("Multi-cloud mode: POSTing to configured writer")
            
            if not INTER_CLOUD_TOKEN:
                raise ConfigurationError("INTER_CLOUD_TOKEN required for multi-cloud mode")
            
            result = post_to_remote(
                url=REMOTE_WRITER_URL,
                token=INTER_CLOUD_TOKEN,
                payload=item,
                target_layer="L3"
            )
            logging.info(
                "Item persisted to remote cloud: HTTP %s",
                result.get("statusCode"),
            )
        else:
            # Single-cloud: Write to local Cosmos DB
            logging.info("Single-cloud mode: Writing to local Cosmos DB")
            container = _get_cosmos_container()
            container.upsert_item(item)
            logging.info("Item persisted to local Cosmos DB.")
        
        # Azure L4: update ADT after the idempotent storage write.
        _push_to_adt(event)
        
        # Optionally invoke Event Checker
        if USE_EVENT_CHECKING:
            _invoke_event_checker(event)
        
        return func.HttpResponse(
            json.dumps({"status": "persisted"}),
            status_code=200,
            mimetype="application/json"
        )
        
    except InvalidRequestBody:
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid JSON body",
            status_code=400,
        )

    except PayloadValidationError:
        logging.warning("Persister payload validation failed")
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid telemetry payload",
            status_code=400,
        )

    except (
        ConfigurationError,
        MissingEnvironmentVariableError,
        json.JSONDecodeError,
    ) as exc:
        return failure_response(
            component="azure.persister.configuration",
            error=exc,
            code="CONFIGURATION_ERROR",
            message="Persister configuration is unavailable.",
            status_code=500,
        )

    except AdtDeliveryError as exc:
        return failure_response(
            component="azure.persister.adt-delivery",
            error=exc,
            code="ADT_DELIVERY_FAILED",
            message="Azure Digital Twins update failed.",
            status_code=502,
        )

    except Exception as exc:
        return failure_response(
            component="azure.persister",
            error=exc,
        )
