from typing import Dict
import boto3
import json
import requests
from backend.logger import logger
import backend.config_loader as config_loader
from typing import Dict
import boto3
import json
import requests
from backend.logger import logger
import backend.config_loader as config_loader
import backend.constants as CONSTANTS
import backend.utils as utils

# --------------------------------------------------------------------
# Regions
# --------------------------------------------------------------------
def fetch_region_map(force_update: bool = False) -> Dict[str, str]:
    """
    Fetch a mapping of AWS region codes to their Pricing API 'location' names.
    
    Args:
        force_update (bool): If True, forces a fresh API fetch. 
                             If False, attempts to load from local file.
                             
    Returns:
        Dict[str, str]: Map of region codes to location names.
        
    Raises:
        FileNotFoundError: If force_update is False and the local file is missing.
    """
    # 1. Try loading from file if not forced
    if not force_update:
        if utils.file_exists(CONSTANTS.AWS_REGIONS_FILE_PATH):
            logger.info(f"✅ Loading AWS regions from {CONSTANTS.AWS_REGIONS_FILE_PATH}")
            return config_loader.load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
        else:
            raise FileNotFoundError(f"AWS regions file not found at {CONSTANTS.AWS_REGIONS_FILE_PATH}. Call with force_update=True to fetch.")

    # 2. Fetch from API
    logger.info("---------------------------------------------------")
    logger.info("Fetching AWS region map from Pricing API")
    try:
        client_args = config_loader.load_aws_credentials()
        region_map = {}

        # NOTE: The Pricing API is only available in specific regions (e.g., eu-central-1)
        pricing_client = boto3.client("pricing", **client_args)
        response = pricing_client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[{"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"}],
            MaxResults=100,
        )

        for price_item in response.get("PriceList", []):
            product = json.loads(price_item)
            attrs = product.get("product", {}).get("attributes", {})
            region = attrs.get("regionCode")
            location = attrs.get("location")
            if region and location:
                region_map[region] = location

        regions_sorted = dict(sorted(region_map.items()))

        with open(CONSTANTS.AWS_REGIONS_FILE_PATH, "w") as f:
            json.dump(regions_sorted, f, indent=2)

        logger.info(f"Saved {len(regions_sorted)} AWS regions to {CONSTANTS.AWS_REGIONS_FILE_PATH}")
        return regions_sorted
    except Exception as e:
        logger.error(f"Failed to fetch AWS region map: {e}")
        raise e