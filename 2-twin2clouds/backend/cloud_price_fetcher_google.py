import json
import re
from typing import Dict, Any, Optional, List
from google.cloud import billing_v1
from backend.logger import logger
import backend.constants as CONSTANTS
from backend.config_loader import load_gcp_credentials
from backend.fetch_data import initial_fetch_google

# -------------------------------------------------------------------
# Region mapping + defaults
# -------------------------------------------------------------------
def _load_gcp_regions() -> Dict[str, str]:
    """
    Load GCP regions using the shared initial fetch logic (with caching).
    """
    return initial_fetch_google.fetch_region_map()

GCP_REGION_NAMES = _load_gcp_regions()

STATIC_DEFAULTS_GCP = {
    "transfer": {"egressPrice": 0.12},
    "iot": {"pricePerMessage": 0.0005}, # Approx
    "functions": {
        "requestPrice": 0.40, # per million
        "durationPrice": 0.0000025, # per gb-second
        "freeRequests": 2_000_000,
        "freeComputeTime": 400_000
    },
    "storage_hot": {
        "storagePrice": 0.020,
        "writePrice": 0.05, # per 10k
        "readPrice": 0.004, # per 10k
    },
    "storage_cool": {
        "storagePrice": 0.010,
        "writePrice": 0.10,
        "readPrice": 0.01,
        "dataRetrievalPrice": 0.01
    },
    "storage_archive": {
        "storagePrice": 0.0012,
        "writePrice": 0.10,
        "readPrice": 0.05,
        "dataRetrievalPrice": 0.05
    },
    "twinmaker": {
        "entityPrice": 0.0, # Not directly comparable
        "unifiedDataAccessAPICallsPrice": 0.0,
        "queryPrice": 0.0
    },
    "grafana": {
        "editorPrice": 0.0, # Managed Service for Prometheus?
        "viewerPrice": 0.0
    }
}

# -------------------------------------------------------------------
# Main Fetcher
# -------------------------------------------------------------------
def fetch_gcp_price(service_name, region_code, debug=False):
    """
    Fetch pricing for a specific GCP service in a given region.
    Currently uses static defaults as the Catalog API is complex to query for specific SKUs dynamically without a large map.
    TODO: Implement dynamic SKU lookup.
    """
    region_human = GCP_REGION_NAMES.get(region_code, region_code)
    
    logger.info(f"🔍 Fetching GCP {service_name} pricing for {region_human}...")
    
    # For now, return static defaults
    # The implementation plan noted that GCP dynamic fetching is a future task
    return STATIC_DEFAULTS_GCP.get(service_name)
