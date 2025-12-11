"""
Hot-to-Cold Mover Azure Function.

Timer-triggered function that moves aged data from Cosmos DB (hot)
to Blob Storage (cold). Supports multi-cloud: if cold storage is
on a different cloud, POSTs chunks to remote Cold Writer.

Architecture:
    Timer → Hot-to-Cold Mover → Blob Storage (or Remote Cold Writer)

Source: src/providers/azure/azure_functions/hot-to-cold-mover/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient

# Handle import path for shared module
try:
    from _shared.inter_cloud import post_raw
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_raw


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
COSMOS_DB_ENDPOINT = _require_env("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = _require_env("COSMOS_DB_KEY")
COSMOS_DB_DATABASE = _require_env("COSMOS_DB_DATABASE")
COSMOS_DB_CONTAINER = _require_env("COSMOS_DB_CONTAINER")

# Blob Storage config
BLOB_CONNECTION_STRING = _require_env("BLOB_CONNECTION_STRING")
COLD_STORAGE_CONTAINER = _require_env("COLD_STORAGE_CONTAINER")

# Multi-cloud config (optional)
REMOTE_COLD_WRITER_URL = os.environ.get("REMOTE_COLD_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Constants
MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Create Function App instance
app = func.FunctionApp()

# Lazy-initialized clients
_cosmos_container = None
_blob_container_client = None


def _get_cosmos_container():
    """Lazy initialization of Cosmos DB container."""
    global _cosmos_container
    if _cosmos_container is None:
        client = CosmosClient(COSMOS_DB_ENDPOINT, credential=COSMOS_DB_KEY)
        database = client.get_database_client(COSMOS_DB_DATABASE)
        _cosmos_container = database.get_container_client(COSMOS_DB_CONTAINER)
    return _cosmos_container


def _get_blob_container():
    """Lazy initialization of Blob container client."""
    global _blob_container_client
    if _blob_container_client is None:
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        _blob_container_client = blob_service.get_container_client(COLD_STORAGE_CONTAINER)
    return _blob_container_client


def _is_multi_cloud_cold() -> bool:
    """Check if cold storage is on a different cloud."""
    if not REMOTE_COLD_WRITER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        raise ConfigurationError("CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO")
    
    l3_hot = providers.get("layer_3_hot_provider")
    l3_cold = providers.get("layer_3_cold_provider")
    
    if l3_hot is None or l3_cold is None:
        raise ConfigurationError(f"Missing provider mapping: hot={l3_hot}, cold={l3_cold}")
    
    if l3_hot == l3_cold:
        logging.warning(f"REMOTE_COLD_WRITER_URL set but providers match ({l3_hot}). Using local Blob.")
        return False
    
    return True


def _chunk_items(items: list, max_bytes: int = MAX_CHUNK_SIZE_BYTES) -> list:
    """
    Split items into chunks of max_bytes each.
    
    Returns list of (chunk_items, chunk_index) tuples.
    """
    if not items:
        return []
    
    chunks = []
    current_chunk = []
    current_size = 2  # Start with empty array "[]"
    
    for item in items:
        item_json = json.dumps(item, default=str)
        item_size = len(item_json.encode('utf-8')) + 1  # +1 for comma
        
        if current_size + item_size > max_bytes and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [item]
            current_size = 2 + item_size
        else:
            current_chunk.append(item)
            current_size += item_size
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return [(chunk, idx) for idx, chunk in enumerate(chunks)]


def _post_to_remote_cold_writer(
    iot_device_id: str,
    items: list,
    start_timestamp: str,
    end_timestamp: str,
    chunk_index: int
) -> None:
    """POST chunk to remote Cold Writer using shared inter_cloud module."""
    if not INTER_CLOUD_TOKEN:
        raise ValueError("INTER_CLOUD_TOKEN is required for multi-cloud transfers")
    
    payload = {
        "iot_device_id": iot_device_id,
        "chunk_index": chunk_index,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "items": items,
        "source_cloud": "azure"
    }
    
    result = post_raw(
        url=REMOTE_COLD_WRITER_URL,
        token=INTER_CLOUD_TOKEN,
        payload=payload
    )
    
    logging.info(f"Posted chunk {chunk_index} ({len(items)} items) to remote Cold Writer")


def _write_to_local_blob(
    iot_device_id: str,
    items: list,
    start: str,
    end: str,
    chunk_index: int
) -> None:
    """Write chunk to local Blob Storage with Cool tier."""
    if not items:
        return
    
    container = _get_blob_container()
    blob_name = f"{iot_device_id}/{start}-{end}/chunk-{chunk_index:05d}.json"
    body = json.dumps(items, default=str)
    
    # Upload to Cool tier
    blob_client = container.get_blob_client(blob_name)
    blob_client.upload_blob(
        body,
        overwrite=True,
        standard_blob_tier="Cool"
    )
    
    logging.info(f"Wrote {len(items)} items to blob: {blob_name}")


def _delete_from_cosmos(container, items: list) -> None:
    """Delete moved items from Cosmos DB."""
    for item in items:
        container.delete_item(
            item=item["id"],
            partition_key=item["iotDeviceId"]
        )
    logging.info(f"Deleted {len(items)} items from Cosmos DB")


@app.function_name(name="hot-to-cold-mover")
@app.timer_trigger(schedule="0 0 0 * * *", arg_name="timer", run_on_startup=False)
def hot_to_cold_mover(timer: func.TimerRequest) -> None:
    """
    Move aged data from Cosmos DB to cold storage.
    
    Runs daily at midnight UTC. Queries for items older than
    configured hot storage days and moves to Blob or remote.
    """
    logging.info("Azure Hot-to-Cold Mover: Starting")
    
    if timer.past_due:
        logging.warning("Timer is running late!")
    
    try:
        multi_cloud = _is_multi_cloud_cold()
        if multi_cloud:
            logging.info(f"Multi-cloud mode: Posting to {REMOTE_COLD_WRITER_URL}")
        else:
            logging.info(f"Single-cloud mode: Writing to Blob container {COLD_STORAGE_CONTAINER}")
        
        # Calculate cutoff
        hot_days = DIGITAL_TWIN_INFO["config"].get("hot_storage_size_in_days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=hot_days)
        cutoff_iso = cutoff.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        logging.info(f"Moving items older than: {cutoff_iso}")
        
        container = _get_cosmos_container()
        
        # Process each IoT device
        for iot_device in DIGITAL_TWIN_INFO.get("config_iot_devices", []):
            device_id = iot_device["id"]
            logging.info(f"Processing device: {device_id}")
            
            # Query items older than cutoff
            query = """
                SELECT * FROM c 
                WHERE c.iotDeviceId = @device_id 
                AND c.id < @cutoff
                ORDER BY c.id ASC
            """
            
            parameters = [
                {"name": "@device_id", "value": device_id},
                {"name": "@cutoff", "value": cutoff_iso}
            ]
            
            items = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            if not items:
                logging.info(f"No old items for device {device_id}")
                continue
            
            logging.info(f"Found {len(items)} items to move for device {device_id}")
            
            start_timestamp = items[0]["id"]
            end_timestamp = items[-1]["id"]
            
            # Process in chunks
            if multi_cloud:
                chunked = _chunk_items(items)
                for chunk_items, chunk_idx in chunked:
                    _post_to_remote_cold_writer(
                        device_id, chunk_items,
                        start_timestamp, end_timestamp,
                        chunk_idx
                    )
            else:
                chunked = _chunk_items(items)
                for chunk_items, chunk_idx in chunked:
                    _write_to_local_blob(
                        device_id, chunk_items,
                        start_timestamp, end_timestamp,
                        chunk_idx
                    )
            
            # Delete from Cosmos DB after successful move
            _delete_from_cosmos(container, items)
        
    except ConfigurationError as e:
        logging.error(f"Configuration Error: {e}")
        raise
        
    except Exception as e:
        logging.error(f"Hot-to-Cold Mover Error: {e}")
        raise
    
    logging.info("Azure Hot-to-Cold Mover: Complete")
