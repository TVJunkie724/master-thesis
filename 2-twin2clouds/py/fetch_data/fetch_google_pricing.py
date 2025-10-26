from fastapi import APIRouter, Query
from typing import Literal, Dict
from google.cloud import billing_v1
from google.oauth2 import service_account
import py.config_loader as config_loader
from py.logger import logger
import py.constants as CONSTANTS
from py.config_loader import load_json_file

router = APIRouter(prefix="/api/gcp", tags=["GCP Pricing"])

def load_gcp_regions_file() -> Dict[str, str]:
    """
    Load GCP regions from the local file.
    """
    logger.info("Loading GCP regions from local file")
    try:
        regions = load_json_file(CONSTANTS.GCP_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted
    except Exception as e:
        logger.error(f"Failed to load GCP regions from file: {e}")
        raise e
    
def load_gcp_service_names_file() -> Dict[str, str]:
    """
    Load GCP service names from the local file.
    """
    logger.info("Loading GCP service names from local file")
    try:
        services = load_json_file(CONSTANTS.GCP_SERVICES_FILE_PATH)
        services_sorted = dict(sorted(services.items()))
        return services_sorted
    except Exception as e:
        logger.error(f"Failed to load GCP service names from file: {e}")
        raise e

# --------------------------------------------------------------------
# Build Client
# --------------------------------------------------------------------
def get_gcp_client():
    """
    Create a Google Cloud Billing Catalog client using service account credentials.
    """
    credentials = config_loader.load_gcp_credentials()
    client = billing_v1.CloudCatalogClient(credentials=credentials)
    return client
    
# --------------------------------------------------------------------
# Fetch GCP pricing for a given service and region
# --------------------------------------------------------------------
def fetch_gcp_pricing(service_id: str, region_id: str):
    """
    Fetch the first SKU for a given service and region.
    """
    client = get_gcp_client()
    try:
        for sku in client.list_skus(parent=f"services/{service_id}"):
            if region_id in sku.service_regions:
                pricing_info = sku.pricing_info[0] if sku.pricing_info else None
                usd_price = 0.0
                if pricing_info and pricing_info.pricing_expression:
                    # Example: use base unit price in USD
                    usd_price = float(pricing_info.pricing_expression.base_unit_price.units)
                return {
                    "service_id": service_id,
                    "region_id": region_id,
                    "sku_id": sku.name,
                    "description": sku.description,
                    "unit": sku.pricing_info[0].pricing_expression.base_unit if sku.pricing_info else "",
                    "price_usd": usd_price,
                    "raw": sku._pb,  # raw protobuf
                }
        raise ValueError(f"No SKU found for service {service_id} in region {region_id}")
    except Exception as e:
        logger.error(f"Error fetching GCP pricing for {service_id} in {region_id}: {e}")
        return {"error": str(e)}

