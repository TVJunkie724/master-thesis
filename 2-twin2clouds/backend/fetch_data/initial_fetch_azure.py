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
def fetch_region_map() -> Dict[str, str]:
    """
    Fetch all unique Azure region codes (armRegionName) and their display names (armRegionNameDisplay).
    """
    # Check if we have a fresh local file
    if utils.is_file_fresh(CONSTANTS.AZURE_REGIONS_FILE_PATH, max_age_days=7):
        logger.info(f"✅ Using cached Azure regions from {CONSTANTS.AZURE_REGIONS_FILE_PATH}")
        return config_loader.load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)

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
        if not utils.file_exists(CONSTANTS.AZURE_REGIONS_FILE_PATH):
            logger.error("No local Azure regions file found. Cannot proceed.")
            raise e
        logger.warning("Loading Azure regions from local file as fallback.")
        regions = config_loader.load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))  
        return regions_sorted
        
