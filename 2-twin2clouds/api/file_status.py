"""
File Status API endpoints for checking age and validity of cached data files.
"""
import os
from fastapi import APIRouter

from backend.logger import logger
from backend.utils import get_file_age_string, is_file_fresh
from backend.config_loader import load_json_file
import backend.constants as CONSTANTS

router = APIRouter(tags=["File Status"])

# Freshness thresholds (days) - must match values used in pricing.py and regions.py
PRICING_THRESHOLD_DAYS = 7
REGIONS_THRESHOLD_AWS = 7
REGIONS_THRESHOLD_AZURE = 7
REGIONS_THRESHOLD_GCP = 30


# --------------------------------------------------
# Pricing Age Endpoints
# --------------------------------------------------

@router.get("/pricing_age/aws", summary="Get AWS Pricing File Status")
def get_pricing_age_aws():
    """
    Checks the age and validity of the local AWS pricing data file.
    
    **Returns**:
    - **age**: Time since last update (e.g., "3 days").
    - **status**: Validation status (`valid`, `incomplete`, `missing`, `error`).
    - **missing_keys**: List of missing service keys if status is `incomplete`.
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


@router.get("/pricing_age/azure", summary="Get Azure Pricing File Status")
def get_pricing_age_azure():
    """
    Checks the age and validity of the local Azure pricing data file.
    
    **Returns**:
    - **age**: Time since last update.
    - **status**: Validation status (`valid`, `incomplete`, `missing`, `error`).
    - **missing_keys**: List of missing service keys if status is `incomplete`.
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


@router.get("/pricing_age/gcp", summary="Get GCP Pricing File Status")
def get_pricing_age_gcp():
    """
    Checks the age and validity of the local GCP pricing data file.
    
    **Returns**:
    - **age**: Time since last update.
    - **status**: Validation status (`valid`, `incomplete`, `missing`, `error`).
    - **missing_keys**: List of missing service keys if status is `incomplete`.
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

@router.get("/regions_age/aws", summary="Get AWS Regions File Age")
def get_regions_age_aws():
    """
    Returns the age and freshness of the local AWS regions data file.
    
    **Returns**: age, is_fresh (bool), threshold_days (int).
    """
    return {
        "age": get_file_age_string(CONSTANTS.AWS_REGIONS_FILE_PATH),
        "is_fresh": is_file_fresh(CONSTANTS.AWS_REGIONS_FILE_PATH, REGIONS_THRESHOLD_AWS),
        "threshold_days": REGIONS_THRESHOLD_AWS
    }


@router.get("/regions_age/azure", summary="Get Azure Regions File Age")
def get_regions_age_azure():
    """
    Returns the age and freshness of the local Azure regions data file.
    
    **Returns**: age, is_fresh (bool), threshold_days (int).
    """
    return {
        "age": get_file_age_string(CONSTANTS.AZURE_REGIONS_FILE_PATH),
        "is_fresh": is_file_fresh(CONSTANTS.AZURE_REGIONS_FILE_PATH, REGIONS_THRESHOLD_AZURE),
        "threshold_days": REGIONS_THRESHOLD_AZURE
    }


@router.get("/regions_age/gcp", summary="Get GCP Regions File Age")
def get_regions_age_gcp():
    """
    Returns the age and freshness of the local GCP regions data file.
    
    **Returns**: age, is_fresh (bool), threshold_days (int=30).
    """
    return {
        "age": get_file_age_string(CONSTANTS.GCP_REGIONS_FILE_PATH),
        "is_fresh": is_file_fresh(CONSTANTS.GCP_REGIONS_FILE_PATH, REGIONS_THRESHOLD_GCP),
        "threshold_days": REGIONS_THRESHOLD_GCP
    }


# --------------------------------------------------
# Currency Age Endpoint
# --------------------------------------------------

@router.get("/currency_age", summary="Get Currency File Age")
def get_currency_age():
    """
    Returns the age of the local currency conversion rates file.
    
    **Returns**: A JSON object with the `age` string.
    """
    return {"age": get_file_age_string(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)}
