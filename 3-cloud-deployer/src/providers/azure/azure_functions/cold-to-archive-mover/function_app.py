"""
Cold-to-Archive Mover Azure Function.

Timer-triggered function that moves aged data from Blob Cool
to Blob Archive tier. Supports multi-cloud transfers.

Architecture:
    Timer → Cold-to-Archive Mover → Blob Archive (or Remote Archive Writer)

Source: src/providers/azure/azure_functions/cold-to-archive-mover/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

import azure.functions as func
from azure.storage.blob import BlobServiceClient, StandardBlobTier

# Handle import path for shared module
try:
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env


class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


# Lazy loading for environment variables to allow Azure function discovery
_digital_twin_info = None
_blob_connection_string = None
_cold_storage_container = None
_archive_storage_container = None


def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info


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


def _get_archive_storage_container():
    global _archive_storage_container
    if _archive_storage_container is None:
        _archive_storage_container = require_env("ARCHIVE_STORAGE_CONTAINER")
    return _archive_storage_container


# Multi-cloud config (optional)
REMOTE_ARCHIVE_WRITER_URL = os.environ.get("REMOTE_ARCHIVE_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

# Memory guard
MAX_OBJECT_SIZE_BYTES = 200 * 1024 * 1024  # 200MB

# Create Function App instance
app = func.FunctionApp()

# Lazy-initialized clients
_blob_service_client = None


def _get_blob_service():
    """Lazy initialization of Blob service client."""
    global _blob_service_client
    if _blob_service_client is None:
        _blob_service_client = BlobServiceClient.from_connection_string(_get_blob_connection_string())
    return _blob_service_client


def _is_multi_cloud_archive() -> bool:
    """Check if archive storage is on a different cloud."""
    if not REMOTE_ARCHIVE_WRITER_URL:
        return False
    
    providers = _get_digital_twin_info().get("config_providers")
    if providers is None:
        raise ConfigurationError("CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO")
    
    l3_cold = providers.get("layer_3_cold_provider")
    l3_archive = providers.get("layer_3_archive_provider")
    
    if l3_cold is None or l3_archive is None:
        raise ConfigurationError(f"Missing provider mapping: cold={l3_cold}, archive={l3_archive}")
    
    if l3_cold == l3_archive:
        raise ConfigurationError(f"REMOTE_ARCHIVE_WRITER_URL set but providers match ({l3_cold}). Invalid multi-cloud config.")
    
    return True


def _post_to_remote_archive_writer(object_key: str, data: str) -> None:
    """POST data to remote Archive Writer."""
    if not INTER_CLOUD_TOKEN:
        raise ValueError("INTER_CLOUD_TOKEN is required for multi-cloud transfers")
    
    payload = {
        "object_key": object_key,
        "data": data,
        "source_cloud": "azure"
    }
    
    post_raw(
        url=REMOTE_ARCHIVE_WRITER_URL,
        token=INTER_CLOUD_TOKEN,
        payload=payload
    )
    
    logging.info(f"Posted {object_key} to remote Archive Writer")


@app.function_name(name="cold-to-archive-mover")
@app.timer_trigger(schedule="0 0 0 * * *", arg_name="timer", run_on_startup=False)
def cold_to_archive_mover(timer: func.TimerRequest) -> None:
    """
    Move aged data from Blob Cool to Archive tier.
    
    Runs daily at midnight UTC.
    """
    logging.info("Azure Cold-to-Archive Mover: Starting")
    
    if timer.past_due:
        logging.warning("Timer is running late!")
    
    try:
        multi_cloud = _is_multi_cloud_archive()
        if multi_cloud:
            logging.info(f"Multi-cloud mode: Posting to {REMOTE_ARCHIVE_WRITER_URL}")
        else:
            logging.info(f"Single-cloud mode: Archiving to {_get_archive_storage_container()}")
        
        # Calculate cutoff
        cold_days = _get_digital_twin_info()["config"].get("cold_storage_size_in_days", 30)
        cutoff = datetime.now(timezone.utc) - timedelta(days=cold_days)
        logging.info(f"Archiving items older than: {cutoff.isoformat()}")
        
        blob_service = _get_blob_service()
        cold_container = blob_service.get_container_client(_get_cold_storage_container())
        archive_container = blob_service.get_container_client(_get_archive_storage_container())
        
        # List blobs in cold container
        blobs = list(cold_container.list_blobs())
        logging.info(f"Found {len(blobs)} blobs in cold container")
        
        moved_count = 0
        for blob in blobs:
            # Check if blob is older than cutoff
            if blob.last_modified and blob.last_modified < cutoff:
                blob_name = blob.name
                logging.info(f"Processing blob: {blob_name}")
                
                # Memory guard
                if blob.size and blob.size > MAX_OBJECT_SIZE_BYTES:
                    logging.warning(f"Skipping {blob_name}: size {blob.size} exceeds limit")
                    continue
                
                if multi_cloud:
                    # Download and POST to remote
                    blob_client = cold_container.get_blob_client(blob_name)
                    data = blob_client.download_blob().readall().decode('utf-8')
                    _post_to_remote_archive_writer(blob_name, data)
                else:
                    # Copy to archive container with Archive tier
                    source_blob = cold_container.get_blob_client(blob_name)
                    dest_blob = archive_container.get_blob_client(blob_name)
                    
                    dest_blob.start_copy_from_url(
                        source_blob.url,
                        standard_blob_tier=StandardBlobTier.ARCHIVE
                    )
                    logging.info(f"Copied {blob_name} to archive tier")
                
                # Delete from cold container
                cold_container.delete_blob(blob_name)
                logging.info(f"Deleted {blob_name} from cold container")
                moved_count += 1
        
        logging.info(f"Moved {moved_count} blobs to archive")
        
    except ConfigurationError as e:
        logging.error(f"Configuration Error: {e}")
        raise
        
    except Exception as e:
        logging.error(f"Cold-to-Archive Mover Error: {e}")
        raise
    
    logging.info("Azure Cold-to-Archive Mover: Complete")
