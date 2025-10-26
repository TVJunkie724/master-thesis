import json
from google.cloud import billing_v1
from py.logger import logger
import py.utils as utils
from py.config_loader import load_gcp_credentials, load_credentials_file
from py.constants import GCP_REGIONS_FILE_PATH, GCP_SERVICES_FILE_PATH


def fetch_gcp_regions():
    """
    Fetch all GCP regions from the Cloud Billing Catalog API and save to gcp_regions.json.
    """
    logger.info("---------------------------------------------------")
    logger.info("Fetching GCP regions from Cloud Billing Catalog API")
    
    try:
        credentials = load_gcp_credentials()
        client = billing_v1.CloudCatalogClient(credentials=credentials)

        regions_set = set()

        logger.info("Fetching GCP regions from Cloud Billing Catalog API")
        for service in client.list_services():
            for sku in client.list_skus(parent=service.name):
                if sku.service_regions:
                    for region in sku.service_regions:
                        regions_set.add(region)

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
        regions = utils.load_json_file(GCP_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted

def fetch_gcp_services():
    """
    Fetch all GCP services and their SKUs from the Cloud Billing Catalog API and save to gcp_skus.json.
    """
    logger.info("---------------------------------------------------")
    logger.info("Fetching GCP services and SKUs from Cloud Billing Catalog API")
    
    try:
        credentials = load_gcp_credentials()
        client = billing_v1.CloudCatalogClient(credentials=credentials)

        service_sku_map = {}

        for service in client.list_services():
            service_name = service.display_name
            service_sku_map[service_name] = {}

            for sku in client.list_skus(parent=service.name):
                cat = sku.category
                if cat:
                    friendly_name = f"{cat.resource_group} / {cat.usage_type}"
                else:
                    friendly_name = sku.description
                service_sku_map[service_name][friendly_name] = sku.name

        with open(GCP_SERVICES_FILE_PATH, "w") as f:
            json.dump(service_sku_map, f, indent=2)

        services_sorted = dict(sorted(service_sku_map.items()))

        logger.info(f"Saved {len(services_sorted)} GCP SKUs to {GCP_SERVICES_FILE_PATH}")
        return services_sorted
    except Exception as e:
        logger.error(f"Failed to fetch GCP services and SKUs: {e}")
        if not utils.file_exists(GCP_SERVICES_FILE_PATH):
            logger.error("No local GCP services file found. Cannot proceed.")
            raise e
        logger.warning("Loading GCP services from local file as fallback.")
        services = utils.load_json_file(GCP_SERVICES_FILE_PATH)
        services_sorted = dict(sorted(services.items()))
        return services_sorted