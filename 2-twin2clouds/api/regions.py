"""
Regions API endpoints for fetching cloud provider region lists.

This module provides endpoints for retrieving available regions from AWS, Azure, 
and GCP. Region data is cached locally and can be force-refreshed when needed.
Regions are used by the calculation engine and deployer for valid location selection.
"""
from fastapi import APIRouter, HTTPException

from backend.logger import logger
from backend.utils import is_file_fresh
from backend.config_loader import load_json_file
from backend.fetch_data import initial_fetch_aws, initial_fetch_azure, initial_fetch_google
import backend.constants as CONSTANTS
from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["Regions"])


# --------------------------------------------------
# Region Fetching Endpoints
# --------------------------------------------------

@router.post(
    "/fetch_regions/aws",
    operation_id="refreshAwsRegions",
    summary="Refresh list of available AWS regions",
    description=(
        "**Purpose:** Fetches the current list of AWS regions and caches them locally.\n\n"
        "**When to use:**\n"
        "- To populate region selection dropdowns\n"
        "- Before calculating costs to ensure valid regions\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- Returns map of region codes to display names"
    ),
    responses={
        200: {
            "description": "Map of region codes to names",
            "content": {"application/json": {"example": {"us-east-1": "US East (N. Virginia)", "eu-west-1": "EU (Ireland)"}}}
        },
        500: ERROR_RESPONSES[500],
    }
)
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


@router.post(
    "/fetch_regions/azure",
    operation_id="refreshAzureRegions",
    summary="Refresh list of available Azure regions",
    description=(
        "**Purpose:** Fetches the current list of Azure regions and caches them locally.\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- Returns map of region codes to display names"
    ),
    responses={
        200: {
            "description": "Map of region codes to names",
            "content": {"application/json": {"example": {"westeurope": "West Europe", "eastus": "East US"}}}
        },
        500: ERROR_RESPONSES[500],
    }
)
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


@router.post(
    "/fetch_regions/gcp",
    operation_id="refreshGcpRegions",
    summary="Refresh list of available GCP regions (SLOW: 5-10 minutes)",
    description=(
        "**Purpose:** Fetches the current list of GCP regions and caches them locally.\n\n"
        "**WARNING:** This operation takes 5-10 minutes due to GCP API pagination!\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 30 days old (unless force_fetch=true)\n"
        "- Only force_fetch if absolutely necessary due to long runtime"
    ),
    responses={
        200: {
            "description": "Map of region codes to names",
            "content": {"application/json": {"example": {"us-central1": "Council Bluffs, Iowa", "europe-west1": "St. Ghislain, Belgium"}}}
        },
        500: ERROR_RESPONSES[500],
    }
)
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
