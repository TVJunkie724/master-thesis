"""
Pricing API endpoints for fetching cloud provider pricing data.
"""
from fastapi import APIRouter

from backend.logger import logger
from backend.utils import is_file_fresh
from backend.config_loader import load_json_file
from backend.fetch_data.calculate_up_to_date_pricing import calculate_up_to_date_pricing
import backend.constants as CONSTANTS

router = APIRouter(tags=["Pricing"])


# --------------------------------------------------
# Pricing Fetching Endpoints
# --------------------------------------------------

@router.post("/api/fetch_pricing/aws", summary="Fetch AWS Pricing")
def fetch_pricing_aws(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest AWS pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the AWS Price List API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for AWS services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AWS_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached AWS pricing data")
            return load_json_file(CONSTANTS.AWS_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh AWS pricing...")
        return calculate_up_to_date_pricing("aws", additional_debug)
    except Exception as e:
        logger.error(f"Error fetching AWS pricing: {e}")
        return {"error": str(e)}


@router.post("/api/fetch_pricing/azure", summary="Fetch Azure Pricing")
def fetch_pricing_azure(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest Azure pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Azure Retail Prices API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for Azure services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AZURE_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached Azure pricing data")
            return load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh Azure pricing...")
        return calculate_up_to_date_pricing("azure", additional_debug)
    except Exception as e:
        logger.error(f"Error fetching Azure pricing: {e}")
        return {"error": str(e)}


@router.post("/api/fetch_pricing/gcp", summary="Fetch GCP Pricing")
def fetch_pricing_gcp(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest Google Cloud Platform (GCP) pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Google Cloud Billing API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for GCP services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.GCP_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached GCP pricing data")
            return load_json_file(CONSTANTS.GCP_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh GCP pricing...")
        return calculate_up_to_date_pricing("gcp", additional_debug)
    except Exception as e:
        logger.error(f"Error fetching GCP pricing: {e}")
        return {"error": str(e)}


# --------------------------------------------------
# Currency Endpoint
# --------------------------------------------------

@router.post("/api/fetch_currency", summary="Fetch Currency Rates")
def fetch_currency_rates():
    """
    Fetches up-to-date currency exchange rates (USD/EUR).
    
    - **Cache Duration**: 1 day.
    
    **Returns**: A dictionary of currency rates (e.g., `{"USD": 1.0, "EUR": 0.92}`).
    """
    try:
        from backend import pricing_utils
        logger.info("🔄 Fetching fresh currency rates...")
        rates = pricing_utils.get_currency_rates()
        return rates
    except Exception as e:
        logger.error(f"Error fetching currency rates: {e}")
        return {"error": str(e)}
