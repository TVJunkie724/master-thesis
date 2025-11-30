import json
from google.cloud import billing_v1
from backend.logger import logger
import backend.utils as utils
import backend.config_loader as config_loader
from backend.constants import GCP_REGIONS_FILE_PATH


def fetch_region_map():
    """
    Fetch all GCP regions from the Cloud Billing Catalog API and save to gcp_regions.json.
    """
    # Check if we have a fresh local file
    if utils.is_file_fresh(GCP_REGIONS_FILE_PATH, max_age_days=30):
        logger.info(f"✅ Using cached GCP regions from {GCP_REGIONS_FILE_PATH}")
        return config_loader.load_json_file(GCP_REGIONS_FILE_PATH)

    logger.info("---------------------------------------------------")
    logger.info("Fetching GCP regions from Cloud Billing Catalog API")
    
    try:
        credentials = config_loader.load_gcp_credentials()
        client = billing_v1.CloudCatalogClient(credentials=credentials)

        regions_set = set()
        logger.info("Fetching .... This can take about 5-10 minutes")
        service_counter = 0
        for service in client.list_services():
            logger.debug(f"Processing service ({service_counter}): {service.name}")
            service_counter += 1
            for sku in client.list_skus(parent=service.name):
                if sku.service_regions:
                    for region in sku.service_regions:
                        regions_set.add(region)
                        logger.debug(f"Found region ({len(regions_set)}): {region}")

        regions_dict = {r: r for r in sorted(regions_set)}

        with open(GCP_REGIONS_FILE_PATH, "w") as f:
            json.dump(regions_dict, f, indent=2)

        logger.info(f"Saved {len(regions_dict)} GCP regions to {GCP_REGIONS_FILE_PATH}")
        return regions_dict
    except Exception as e:
        logger.error(f"Failed to fetch GCP regions: {e}")
        if not utils.file_exists(GCP_REGIONS_FILE_PATH):
            logger.error("No local GCP regions file found. Cannot proceed.")
            raise e
        logger.warning("Loading GCP regions from local file as fallback.")
        regions = config_loader.load_json_file(GCP_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted