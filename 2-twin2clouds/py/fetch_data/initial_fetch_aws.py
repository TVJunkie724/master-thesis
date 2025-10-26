from typing import Dict
import boto3
import json
import requests
from py.logger import logger
import py.config_loader as config_loader
import py.constants as CONSTANTS
import py.utils as utils

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
    logger.info("---------------------------------------------------")
    logger.info("Fetching AWS region map from Pricing API")
    try:
        client_args = config_loader.get_aws_credentials()
        region_map = {}

        # NOTE: The Pricing API is only available in specific regions (e.g., us-east-1)
        pricing_client = boto3.client("pricing", region_name="us-east-1", **client_args)
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
        regions = utils.load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted


# --------------------------------------------------------------------
# Service Codes
# --------------------------------------------------------------------
def fetch_aws_service_codes() -> Dict[str, str]:
    """
    Fetch all AWS service codes from the Pricing API index and return a friendly name mapping.
    Example:
        {
            "ec2": "AmazonEC2",
            "s3": "AmazonS3",
            ...
        }
    """
    logger.info("---------------------------------------------------")
    logger.info("Fetching AWS service codes from Pricing API index")
    try:
        resp = requests.get(CONSTANTS.AWS_PRICING_API_URL, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        offers = data.get("offers", {})

        service_codes_map = {}
        for svc_code in offers.keys():
            friendly = (
                svc_code.lower()
                .replace("amazon", "")
                .replace("aws", "")
                .replace(".", "_")
                .strip("_")
            )
            service_codes_map[friendly] = svc_code

        service_dict_sorted = dict(sorted(service_codes_map.items()))
        

        with open(CONSTANTS.AWS_SERVICE_CODES_FILE_PATH, "w") as f:
            json.dump(service_dict_sorted, f, indent=2)

        logger.info(f"Saved {len(service_dict_sorted)} AWS services to {CONSTANTS.AWS_SERVICE_CODES_FILE_PATH}")
        return service_dict_sorted
    except Exception as e:
        logger.error(f"Failed to fetch AWS service codes: {e}")
        if not utils.file_exists(CONSTANTS.AWS_SERVICE_CODES_FILE_PATH):
            logger.error("No local AWS service codes file found. Cannot proceed.")
            raise e
        logger.warning("Loading AWS service codes from local file as fallback.")
        services = utils.load_json_file(CONSTANTS.AWS_SERVICE_CODES_FILE_PATH)
        services_sorted = dict(sorted(services.items()))
        return services_sorted