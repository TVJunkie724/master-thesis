from typing import Dict
import requests
import json
from backend.logger import logger
import backend.utils as utils
import backend.config_loader as config_loader
import backend.constants as CONSTANTS

# ---------------------------------------------------------------
# 1. Fetch all Azure regions
# ---------------------------------------------------------------
def fetch_region_map(force_update: bool = False) -> Dict[str, str]:
    """
    Fetch all unique Azure region codes (armRegionName) and their display names (armRegionNameDisplay).
    
    Args:
        force_update (bool): If True, forces a fresh API fetch. 
                             If False, attempts to load from local file.
                             
    Returns:
        Dict[str, str]: Map of region codes to display names.
        
    Raises:
        FileNotFoundError: If force_update is False and the local file is missing.
    """
    # 1. Try loading from file if not forced
    if not force_update:
        if utils.file_exists(CONSTANTS.AZURE_REGIONS_FILE_PATH):
            logger.info(f"✅ Loading Azure regions from {CONSTANTS.AZURE_REGIONS_FILE_PATH}")
            return config_loader.load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)
        else:
            raise FileNotFoundError(f"Azure regions file not found at {CONSTANTS.AZURE_REGIONS_FILE_PATH}. Call with force_update=True to fetch.")

    # 2. Fetch from API
    logger.info("---------------------------------------------------")
    logger.info("Fetching Azure regions from Retail Prices API")
    try:
        response = requests.get(f"{CONSTANTS.AZURE_RETAIL_PRICES_URL}?$top=1000", timeout=10)
        response.raise_for_status()
        data = response.json()
        regions = {}
        for item in data.get("Items", []):
            code = item.get("armRegionName")
            name = item.get("armRegionNameDisplay") or code
            if code:
                regions[code] = name
        if not regions:
            raise ValueError("No Azure regions found in API response.")
            
        regions_sorted = dict(sorted(regions.items()))

        with open(CONSTANTS.AZURE_REGIONS_FILE_PATH, "w") as f:
            json.dump(regions_sorted, f, indent=2)

        logger.info(f"Saved {len(regions_sorted)} Azure regions to {CONSTANTS.AZURE_REGIONS_FILE_PATH}")
        return regions_sorted
    except Exception as e:
        logger.error(f"Failed to fetch Azure regions: {e}")
        raise e
        
