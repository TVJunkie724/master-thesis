from typing import Dict
import requests
import json
from py.logger import logger
import py.utils as utils
import py.constants as CONSTANTS

# ---------------------------------------------------------------
# 1. Fetch all Azure regions
# ---------------------------------------------------------------
def fetch_azure_regions() -> Dict[str, str]:
    """
    Fetch all unique Azure region codes (armRegionName) and their display names (armRegionNameDisplay).
    """
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
        regions = utils.load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))  
        return regions_sorted

# ---------------------------------------------------------------
# 2. Fetch all Azure service names
# ---------------------------------------------------------------
def fetch_azure_service_names() -> Dict[str, str]:
    """
    Fetch all available Azure service names (serviceName) from the Retail Prices API.
    """
    logger.info("---------------------------------------------------")
    logger.info("Fetching Azure service names from Retail Prices API")
    try:
        url = f"{CONSTANTS.AZURE_RETAIL_PRICES_URL}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        services = {}
        items = data.get("Items", [])
        logger.debug(f"Total items fetched from API: {len(items)}")
        for item in items:
            if item.get("reservationTerm"):
                continue
            
            service_family = item.get("serviceFamily", "")
            service_family_key = service_family.lower().replace(" ", "_")
            if not services.get(service_family_key):
                services[service_family_key] = {}
            
            service_name = item.get("serviceName")
            service_name_key = service_name.lower().replace(" ", "_")
            if not services[service_family_key].get(service_name_key):
                services[service_family_key][service_name_key] = {}
                
            product_name = item.get("productName")
            product_name_key = product_name.lower().replace("- ", "").replace(" ", "_")
            if not services[service_family_key][service_name_key].get(product_name_key):
                services[service_family_key][service_name_key][product_name_key] = {}
            
            meter_name = item.get("meterName")
            meter_name_key = meter_name.lower().replace(" ", "_")
                
            services[service_family_key][service_name_key][product_name_key][meter_name_key] = {
                "currency_code": item.get("currencyCode"),
                "tier_minimum_units": item.get("tierMinimumUnits", 0),
                "retail_price": item.get("retailPrice", 0.0),
                "unit_price": item.get("unitPrice", 0.0),
                "arm_region_name": item.get("armRegionName"),
                "unit_of_measure": item.get("unitOfMeasure"),
            }
            
            
            
        if not services:
            raise ValueError("No Azure services found in API response.")
        services_sorted = dict(sorted(services.items()))
        
        with open(CONSTANTS.AZURE_SERVICE_CODES_FILE_PATH, "w") as f:
            json.dump(services_sorted, f, indent=2)

        logger.info(f"Saved {len(services_sorted)} Azure services to {CONSTANTS.AZURE_SERVICE_CODES_FILE_PATH}")
        return services_sorted
    except Exception as e:
        logger.error(f"Failed to fetch Azure service names: {e}")
        if not utils.file_exists(CONSTANTS.AZURE_SERVICE_CODES_FILE_PATH):
            logger.error("No local Azure services file found. Cannot proceed.")
            raise e
        logger.warning("Loading Azure services from local file as fallback.")
        services = utils.load_json_file(CONSTANTS.AZURE_SERVICE_CODES_FILE_PATH)
        services_sorted = dict(sorted(services.items()))
        return services_sorted
        
