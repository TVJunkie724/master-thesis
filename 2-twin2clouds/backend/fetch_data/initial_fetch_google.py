import json
from google.cloud import billing_v1
import json
from google.cloud import billing_v1
from backend.logger import logger
import backend.utils as utils
import backend.config_loader as config_loader
from backend.constants import GCP_REGIONS_FILE_PATH
from typing import Dict


def fetch_region_map(force_update: bool = False) -> Dict[str, str]:
    """
    Fetch all GCP regions from the Cloud Billing Catalog API and save to gcp_regions.json.
    
    Args:
        force_update (bool): If True, forces a fresh API fetch. 
                             If False, attempts to load from local file.
                             
    Returns:
        Dict[str, str]: Map of region codes.
        
    Raises:
        FileNotFoundError: If force_update is False and the local file is missing.
    """
    # 1. Try loading from file if not forced
    if not force_update:
        if utils.file_exists(GCP_REGIONS_FILE_PATH):
            logger.info(f"✅ Loading GCP regions from {GCP_REGIONS_FILE_PATH}")
            return config_loader.load_json_file(GCP_REGIONS_FILE_PATH)
        else:
            raise FileNotFoundError(f"GCP regions file not found at {GCP_REGIONS_FILE_PATH}. Call with force_update=True to fetch.")

    # 2. Fetch from API
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
        raise e