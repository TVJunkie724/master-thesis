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
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.logger import logger
from backend.utils import get_file_age_string, is_file_fresh
from backend.pricing_catalog_models import PricingCatalogContractError, canonicalize_pricing_region
from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRepositoryError,
    get_pricing_catalog_repository,
)
from backend.pricing_schema import validate_pricing_payload
import backend.constants as CONSTANTS

router = APIRouter(tags=["File Status"])

# Freshness thresholds (days) - must match values used in pricing.py and regions.py
PRICING_THRESHOLD_DAYS = 7
REGIONS_THRESHOLD_AWS = 7
REGIONS_THRESHOLD_AZURE = 7
REGIONS_THRESHOLD_GCP = 30


def _pricing_status_response(
    provider: str,
    pricing_region: str,
    threshold_days: int,
) -> dict:
    try:
        pricing_region = canonicalize_pricing_region(provider, pricing_region)
    except PricingCatalogContractError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "PRICING_CATALOG_REFERENCE_INVALID",
                "message": str(exc),
                "fix_suggestion": (
                    "Provide a canonical pricing region for the selected provider."
                ),
                "http_status": 400,
            },
        ) from exc
    repository = get_pricing_catalog_repository()
    try:
        snapshot = repository.resolve_published(
            provider,
            pricing_region,
            require_fresh=False,
        )
    except PricingCatalogNotFoundError:
        return _missing_pricing_status(provider, pricing_region, threshold_days)
    except PricingCatalogRepositoryError as exc:
        logger.error(
            "Failed to resolve %s pricing catalog: %s",
            provider.upper(),
            exc.code,
        )
        return {
            **_missing_pricing_status(provider, pricing_region, threshold_days),
            "status": "error",
        }

    validation = validate_pricing_payload(provider, snapshot.pricing)
    age = datetime.now(timezone.utc) - snapshot.reference.fetched_at
    return {
        "provider": provider,
        "pricing_region": snapshot.reference.pricing_region,
        "age": _format_age(age.total_seconds()),
        "schema_version": validation.get("schema_version"),
        "contract_version": validation.get("contract_version"),
        "status": validation["status"],
        "missing_keys": validation["missing_keys"],
        "quality_status": validation.get("quality_status", "unavailable"),
        "review_required": bool(validation.get("review_required", False)),
        "fallback_fields": validation.get("fallback_fields", []),
        "unsupported_fields": validation.get("unsupported_fields", []),
        "is_fresh": not repository.is_stale(snapshot.reference),
        "threshold_days": threshold_days,
        "active_reference": snapshot.reference.to_http_dict(),
    }


def _missing_pricing_status(
    provider: str,
    pricing_region: str,
    threshold_days: int,
) -> dict:
    return {
        "provider": provider,
        "pricing_region": pricing_region,
        "age": "missing",
        "schema_version": None,
        "contract_version": None,
        "status": "missing",
        "missing_keys": [],
        "quality_status": "review_required",
        "review_required": True,
        "fallback_fields": [],
        "unsupported_fields": [],
        "is_fresh": False,
        "threshold_days": threshold_days,
        "active_reference": None,
    }


def _format_age(total_seconds: float) -> str:
    if total_seconds < 3600:
        return f"{max(0, int(total_seconds // 60))} minutes"
    if total_seconds < 86400:
        return f"{int(total_seconds // 3600)} hours"
    return f"{int(total_seconds // 86400)} days"


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
def get_pricing_age_aws(pricing_region: str = "eu-central-1"):
    """
    Checks the age and validity of the local AWS pricing data file.
    """
    return _pricing_status_response(
        "aws", pricing_region, PRICING_THRESHOLD_DAYS
    )


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
def get_pricing_age_azure(pricing_region: str = "westeurope"):
    """
    Checks the age and validity of the local Azure pricing data file.
    """
    return _pricing_status_response(
        "azure", pricing_region, PRICING_THRESHOLD_DAYS
    )


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
def get_pricing_age_gcp(pricing_region: str = "europe-west1"):
    """
    Checks the age and validity of the local GCP pricing data file.
    """
    return _pricing_status_response(
        "gcp", pricing_region, PRICING_THRESHOLD_DAYS
    )


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
