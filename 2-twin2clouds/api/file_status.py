"""
File Status API endpoints for checking age and validity of cached data files.

This module provides endpoints for checking whether cached pricing and region data
is fresh or stale. Agents should use these endpoints before running calculations
to determine if pricing data needs to be refreshed.

**Freshness thresholds:**
- Pricing data: 7 days
- AWS/Azure regions: 7 days
- GCP regions: 30 days (due to slow fetch time)
"""
import os
from fastapi import APIRouter

from backend.logger import logger
from backend.utils import get_file_age_string, is_file_fresh
from backend.config_loader import load_json_file
import backend.constants as CONSTANTS
from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["File Status"])

# Freshness thresholds (days) - must match values used in pricing.py and regions.py
PRICING_THRESHOLD_DAYS = 7
REGIONS_THRESHOLD_AWS = 7
REGIONS_THRESHOLD_AZURE = 7
REGIONS_THRESHOLD_GCP = 30


# --------------------------------------------------
# Pricing Age Endpoints
# --------------------------------------------------

@router.get(
    "/pricing_age/aws",
    operation_id="getAwsPricingStatus",
    summary="Check age and validity of cached AWS pricing data",
    description=(
        "**Purpose:** Check if AWS pricing data is fresh and valid before running calculations.\n\n"
        "**Use this to decide:** Should I call `refreshAwsPricing` before `calculateOptimalCloudDistribution`?\n\n"
        "**Response fields:**\n"
        "- `is_fresh`: true if data aged < 7 days\n"
        "- `status`: 'valid', 'incomplete', 'missing', or 'error'\n"
        "- `missing_keys`: service keys that are missing if incomplete"
    ),
    responses={
        200: {
            "description": "Pricing file status",
            "content": {"application/json": {"example": {
                "age": "3 days",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": True,
                "threshold_days": 7
            }}}
        }
    }
)
def get_pricing_age_aws():
    """
    Checks the age and validity of the local AWS pricing data file.
    """
    age = get_file_age_string(CONSTANTS.AWS_PRICING_FILE_PATH)
    status = "missing"
    missing_keys = []
    
    if os.path.isfile(CONSTANTS.AWS_PRICING_FILE_PATH):
        try:
            from backend.pricing_utils import validate_pricing_schema
            data = load_json_file(CONSTANTS.AWS_PRICING_FILE_PATH)
            validation = validate_pricing_schema("aws", data)
            status = validation["status"]
            missing_keys = validation["missing_keys"]
        except Exception as e:
            logger.error(f"Failed to validate AWS pricing: {e}")
            status = "error"
            
    return {
        "age": age,
        "status": status,
        "missing_keys": missing_keys,
        "is_fresh": is_file_fresh(CONSTANTS.AWS_PRICING_FILE_PATH, PRICING_THRESHOLD_DAYS),
        "threshold_days": PRICING_THRESHOLD_DAYS
    }


@router.get(
    "/pricing_age/azure",
    operation_id="getAzurePricingStatus",
    summary="Check age and validity of cached Azure pricing data",
    description=(
        "**Purpose:** Check if Azure pricing data is fresh and valid before running calculations.\n\n"
        "**Use this to decide:** Should I call `refreshAzurePricing` before `calculateOptimalCloudDistribution`?"
    ),
    responses={
        200: {
            "description": "Pricing file status",
            "content": {"application/json": {"example": {
                "age": "1 day",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": True,
                "threshold_days": 7
            }}}
        }
    }
)
def get_pricing_age_azure():
    """
    Checks the age and validity of the local Azure pricing data file.
    """
    age = get_file_age_string(CONSTANTS.AZURE_PRICING_FILE_PATH)
    status = "missing"
    missing_keys = []
    
    if os.path.isfile(CONSTANTS.AZURE_PRICING_FILE_PATH):
        try:
            from backend.pricing_utils import validate_pricing_schema
            data = load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
            validation = validate_pricing_schema("azure", data)
            status = validation["status"]
            missing_keys = validation["missing_keys"]
        except Exception as e:
            logger.error(f"Failed to validate Azure pricing: {e}")
            status = "error"
            
    return {
        "age": age,
        "status": status,
        "missing_keys": missing_keys,
        "is_fresh": is_file_fresh(CONSTANTS.AZURE_PRICING_FILE_PATH, PRICING_THRESHOLD_DAYS),
        "threshold_days": PRICING_THRESHOLD_DAYS
    }


@router.get(
    "/pricing_age/gcp",
    operation_id="getGcpPricingStatus",
    summary="Check age and validity of cached GCP pricing data",
    description=(
        "**Purpose:** Check if GCP pricing data is fresh and valid before running calculations.\n\n"
        "**Use this to decide:** Should I call `refreshGcpPricing` before `calculateOptimalCloudDistribution`?"
    ),
    responses={
        200: {
            "description": "Pricing file status",
            "content": {"application/json": {"example": {
                "age": "5 days",
                "status": "valid",
                "missing_keys": [],
                "is_fresh": True,
                "threshold_days": 7
            }}}
        }
    }
)
def get_pricing_age_gcp():
    """
    Checks the age and validity of the local GCP pricing data file.
    """
    age = get_file_age_string(CONSTANTS.GCP_PRICING_FILE_PATH)
    status = "missing"
    missing_keys = []
    
    if os.path.isfile(CONSTANTS.GCP_PRICING_FILE_PATH):
        try:
            from backend.pricing_utils import validate_pricing_schema
            data = load_json_file(CONSTANTS.GCP_PRICING_FILE_PATH)
            validation = validate_pricing_schema("gcp", data)
            status = validation["status"]
            missing_keys = validation["missing_keys"]
        except Exception as e:
            logger.error(f"Failed to validate GCP pricing: {e}")
            status = "error"
            
    return {
        "age": age,
        "status": status,
        "missing_keys": missing_keys,
        "is_fresh": is_file_fresh(CONSTANTS.GCP_PRICING_FILE_PATH, PRICING_THRESHOLD_DAYS),
        "threshold_days": PRICING_THRESHOLD_DAYS
    }


# --------------------------------------------------
# Regions Age Endpoints
# --------------------------------------------------

@router.get(
    "/regions_age/aws",
    operation_id="getAwsRegionsStatus",
    summary="Check age of cached AWS regions data",
    description="Returns the age and freshness of the local AWS regions cache.",
    responses={
        200: {
            "description": "Regions file status",
            "content": {"application/json": {"example": {"age": "2 days", "is_fresh": True, "threshold_days": 7}}}
        }
    }
)
def get_regions_age_aws():
    """Returns the age and freshness of the local AWS regions data file."""
    return {
        "age": get_file_age_string(CONSTANTS.AWS_REGIONS_FILE_PATH),
        "is_fresh": is_file_fresh(CONSTANTS.AWS_REGIONS_FILE_PATH, REGIONS_THRESHOLD_AWS),
        "threshold_days": REGIONS_THRESHOLD_AWS
    }


@router.get(
    "/regions_age/azure",
    operation_id="getAzureRegionsStatus",
    summary="Check age of cached Azure regions data",
    description="Returns the age and freshness of the local Azure regions cache.",
    responses={
        200: {
            "description": "Regions file status",
            "content": {"application/json": {"example": {"age": "4 days", "is_fresh": True, "threshold_days": 7}}}
        }
    }
)
def get_regions_age_azure():
    """Returns the age and freshness of the local Azure regions data file."""
    return {
        "age": get_file_age_string(CONSTANTS.AZURE_REGIONS_FILE_PATH),
        "is_fresh": is_file_fresh(CONSTANTS.AZURE_REGIONS_FILE_PATH, REGIONS_THRESHOLD_AZURE),
        "threshold_days": REGIONS_THRESHOLD_AZURE
    }


@router.get(
    "/regions_age/gcp",
    operation_id="getGcpRegionsStatus",
    summary="Check age of cached GCP regions data",
    description="Returns the age and freshness of the local GCP regions cache (30-day threshold).",
    responses={
        200: {
            "description": "Regions file status",
            "content": {"application/json": {"example": {"age": "15 days", "is_fresh": True, "threshold_days": 30}}}
        }
    }
)
def get_regions_age_gcp():
    """Returns the age and freshness of the local GCP regions data file."""
    return {
        "age": get_file_age_string(CONSTANTS.GCP_REGIONS_FILE_PATH),
        "is_fresh": is_file_fresh(CONSTANTS.GCP_REGIONS_FILE_PATH, REGIONS_THRESHOLD_GCP),
        "threshold_days": REGIONS_THRESHOLD_GCP
    }


# --------------------------------------------------
# Currency Age Endpoint
# --------------------------------------------------

@router.get(
    "/currency_age",
    operation_id="getCurrencyRatesStatus",
    summary="Check age of cached currency exchange rates",
    description="Returns the age of the local currency conversion rates file.",
    responses={
        200: {
            "description": "Currency file age",
            "content": {"application/json": {"example": {"age": "12 hours"}}}
        }
    }
)
def get_currency_age():
    """Returns the age of the local currency conversion rates file."""
    return {"age": get_file_age_string(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)}
