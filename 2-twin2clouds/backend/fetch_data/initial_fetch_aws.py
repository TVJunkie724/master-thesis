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
def fetch_region_map() -> Dict[str, str]:
    """
    Fetch a mapping of AWS region codes to their Pricing API 'location' names.
    Example:
        {
            "eu-central-1": "EU (Frankfurt)",
            "us-east-1": "US East (N. Virginia)"
        }
    """
    # Check if we have a fresh local file
    if utils.is_file_fresh(CONSTANTS.AWS_REGIONS_FILE_PATH, max_age_days=7):
        logger.info(f"✅ Using cached AWS regions from {CONSTANTS.AWS_REGIONS_FILE_PATH}")
        return config_loader.load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)

    logger.info("---------------------------------------------------")
    logger.info("Fetching AWS region map from Pricing API")
    try:
        client_args = config_loader.load_aws_credentials()
        region_map = {}

        # NOTE: The Pricing API is only available in specific regions (e.g., eu-central-1)
        pricing_client = boto3.client("pricing", region_name="eu-central-1", **client_args)
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
        if not utils.file_exists(CONSTANTS.AWS_REGIONS_FILE_PATH):
            logger.error("No local AWS regions file found. Cannot proceed.")
            raise e
        logger.warning("Loading AWS region map from local file as fallback.")
        regions = config_loader.load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted