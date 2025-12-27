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

@router.post("/fetch_pricing/aws", summary="Fetch AWS Pricing")
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
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/fetch_pricing/azure", summary="Fetch Azure Pricing")
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
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/fetch_pricing/gcp", summary="Fetch GCP Pricing")
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
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})


# --------------------------------------------------
# Currency Endpoint
# --------------------------------------------------

@router.post("/fetch_currency", summary="Fetch Currency Rates")
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


# --------------------------------------------------
# Pricing Export (for snapshotting)
# --------------------------------------------------

import os
from datetime import datetime, timezone

@router.get("/pricing/export/{provider}", summary="Export Pricing for Snapshot")
def export_pricing(provider: str):
    """
    Export full pricing JSON for a provider (for snapshotting).
    
    Used by Management API to capture the exact pricing data used
    during a calculation for audit trail purposes.
    
    **Returns**: Provider name, last update timestamp, and full pricing data.
    """
    if provider not in ["aws", "azure", "gcp"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    file_map = {
        "aws": CONSTANTS.AWS_PRICING_FILE_PATH,
        "azure": CONSTANTS.AZURE_PRICING_FILE_PATH,
        "gcp": CONSTANTS.GCP_PRICING_FILE_PATH,
    }
    
    cache_file = file_map[provider]
    if not os.path.exists(cache_file):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No cached pricing for {provider}")
    
    data = load_json_file(cache_file)
    mtime = os.path.getmtime(cache_file)
    updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    
    return {
        "provider": provider,
        "updated_at": updated_at,
        "pricing": data
    }


# --------------------------------------------------
# Credential-based Pricing Endpoint (for Management API)
# --------------------------------------------------

from fastapi import Body
from pydantic import BaseModel
from typing import Optional


class CredentialRequest(BaseModel):
    """Credentials for pricing fetch."""
    # AWS
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "eu-central-1"
    # GCP
    gcp_service_account_json: Optional[str] = None
    gcp_region: Optional[str] = "europe-west1"


@router.post("/fetch_pricing_with_credentials/{provider}", summary="Fetch Pricing with Credentials")
def fetch_pricing_with_credentials(
    provider: str,
    credentials: CredentialRequest = Body(...),
    force_fetch: bool = True
):
    """
    Fetch pricing using credentials from request body (for Management API integration).
    
    This endpoint is used by the Management API to refresh pricing data using
    credentials stored in the twin configuration (from Step 1).
    
    - **provider**: aws, azure, or gcp
    - **credentials**: Provider-specific credentials
    - **force_fetch**: Always fetch fresh data (default: True)
    
    **Credential Requirements:**
    - AWS: aws_access_key_id, aws_secret_access_key, aws_region
    - Azure: None (public API)
    - GCP: gcp_service_account_json, gcp_region
    """
    if provider not in ["aws", "azure", "gcp"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": f"Invalid provider: {provider}"})
    
    try:
        # Azure uses public API - no credentials needed
        if provider == "azure":
            if not force_fetch and is_file_fresh(CONSTANTS.AZURE_PRICING_FILE_PATH, max_age_days=7):
                logger.info("✅ Using cached Azure pricing data")
                return load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
            logger.info("🔄 Fetching fresh Azure pricing...")
            return calculate_up_to_date_pricing("azure", additional_debug=False)
        
        # AWS/GCP need credentials
        from backend.fetch_data.calculate_up_to_date_pricing import (
            calculate_up_to_date_pricing_with_credentials
        )
        
        creds_dict = credentials.model_dump()
        return calculate_up_to_date_pricing_with_credentials(provider, creds_dict)
        
    except Exception as e:
        logger.error(f"Error fetching {provider} pricing with credentials: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})
