"""
Regions API endpoints for fetching cloud provider region lists.
"""
from fastapi import APIRouter, HTTPException

from backend.logger import logger
from backend.utils import is_file_fresh
from backend.config_loader import load_json_file
from backend.fetch_data import initial_fetch_aws, initial_fetch_azure, initial_fetch_google
import backend.constants as CONSTANTS

router = APIRouter(tags=["Regions"])


# --------------------------------------------------
# Region Fetching Endpoints
# --------------------------------------------------

@router.post("/fetch_regions/aws", summary="Fetch AWS Regions")
def fetch_regions_aws(force_fetch: bool = False):
    """
    Fetches the latest list of available AWS regions.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from AWS.
    
    **Returns**: A dictionary mapping region codes (e.g., `us-east-1`) to human-readable names (e.g., `US East (N. Virginia)`).
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AWS_REGIONS_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached AWS regions data")
            return load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)

        logger.info("🔄 Fetching fresh AWS regions...")
        return initial_fetch_aws.fetch_region_map(force_update=True)
    except FileNotFoundError as e:
        logger.error(f"Regions file not found: {e}")
        raise HTTPException(status_code=404, detail="AWS regions data not available. Run refresh first.")
    except Exception as e:
        logger.error(f"Error fetching AWS regions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AWS regions. Check server logs.")


@router.post("/fetch_regions/azure", summary="Fetch Azure Regions")
def fetch_regions_azure(force_fetch: bool = False):
    """
    Fetches the latest list of available Azure regions.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from Azure.
    
    **Returns**: A dictionary mapping region codes (e.g., `westeurope`) to human-readable names (e.g., `West Europe`).
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AZURE_REGIONS_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached Azure regions data")
            return load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)

        logger.info("🔄 Fetching fresh Azure regions...")
        return initial_fetch_azure.fetch_region_map(force_update=True)
    except FileNotFoundError as e:
        logger.error(f"Regions file not found: {e}")
        raise HTTPException(status_code=404, detail="Azure regions data not available. Run refresh first.")
    except Exception as e:
        logger.error(f"Error fetching Azure regions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Azure regions. Check server logs.")


@router.post("/fetch_regions/gcp", summary="Fetch GCP Regions")
def fetch_regions_gcp(force_fetch: bool = False):
    """
    Fetches the latest list of available Google Cloud regions.
    
    ---------------
    - **`WARNING`**: fetching GCP regions takes about 5-10 minutes!!!!!
    ---------------
    
    - **Cache Duration**: 30 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from GCP.
    
    **Returns**: A dictionary mapping region codes (e.g., `us-central1`) to human-readable names.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.GCP_REGIONS_FILE_PATH, max_age_days=30):
            logger.info("✅ Using cached GCP regions data")
            return load_json_file(CONSTANTS.GCP_REGIONS_FILE_PATH)

        logger.info("🔄 Fetching fresh GCP regions...")
        return initial_fetch_google.fetch_region_map(force_update=True)
    except FileNotFoundError as e:
        logger.error(f"Regions file not found: {e}")
        raise HTTPException(status_code=404, detail="GCP regions data not available. Run refresh first.")
    except Exception as e:
        logger.error(f"Error fetching GCP regions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch GCP regions. Check server logs.")
