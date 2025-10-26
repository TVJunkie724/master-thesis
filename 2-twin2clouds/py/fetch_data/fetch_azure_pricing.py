from fastapi import APIRouter, Query
from typing import Literal, Dict, List
import requests
from py.logger import logger
import json
import py.constants as CONSTANTS
from py.config_loader import load_json_file

def load_azure_regions_file() -> Dict[str, str]:
    """
    Load Azure regions from the local file.
    """
    logger.info("Loading Azure regions from local file")
    try:
        regions = load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted
    except Exception as e:
        logger.error(f"Failed to load Azure regions from file: {e}")
        raise e

def load_azure_service_names_file() -> Dict[str, str]:
    """
    Load Azure service names from the local file.
    """
    logger.info("Loading Azure service names from local file")
    try:
        services = load_json_file(CONSTANTS.AZURE_SERVICE_CODES_FILE_PATH)
        services_sorted = dict(sorted(services.items()))
        return services_sorted
    except Exception as e:
        logger.error(f"Failed to load Azure service names from file: {e}")
        raise e


# ---------------------------------------------------------------
# Fetch Azure pricing for a given service and region
# ---------------------------------------------------------------
def fetch_azure_pricing(service_name: str, region_name: str):
    """
    Fetch one matching Azure retail price record using the Azure Retail Prices API.
    """
    logger.info(f"Fetching Azure pricing for service='{service_name}', region='{region_name}'")
    filter_expr = f"serviceName eq '{service_name}' and armRegionName eq '{region_name}'"
    url = f"{CONSTANTS.AZURE_RETAIL_PRICES_URL}?$filter={filter_expr}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    items = data.get("Items", [])
    if not items:
        raise ValueError(f"No Azure pricing data found for service '{service_name}' in region '{region_name}'.")
    first = items[0]
    return {
        "service": first.get("serviceName"),
        "skuName": first.get("skuName"),
        "region": first.get("armRegionName"),
        "unitPriceUSD": first.get("unitPrice"),
        "currencyCode": first.get("currencyCode"),
        "meterName": first.get("meterName"),
        "productName": first.get("productName"),
        "effectiveStartDate": first.get("effectiveStartDate"),
        "raw": first,
    }

