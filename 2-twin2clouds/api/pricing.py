"""
Pricing API endpoints for fetching cloud provider pricing data.

This module provides endpoints for refreshing and retrieving cloud pricing data
from AWS, Azure, and GCP. Pricing data is cached locally for 7 days and can be
force-refreshed when needed. The data is used by the calculation engine to
determine optimal cloud provider distribution.
"""
import asyncio
import logging
import os
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.requests import Request

from backend.logger import logger
from backend.fetch_data.calculate_up_to_date_pricing import calculate_up_to_date_pricing
from backend.calculation_v2.pricing_source_inventory import pricing_source_inventory
from backend.pricing_catalog_models import (
    PricingCatalogContractError,
    canonicalize_pricing_region,
)
from backend.secret_redaction import credential_strings, redact_secret_like_text
from backend.pricing_catalog_refresh_service import PricingCatalogRefreshService
from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRegionMismatchError,
    PricingCatalogRefreshInProgressError,
    PricingCatalogStaleError,
    PricingCatalogStorageError,
    PricingCatalogTamperedError,
    get_pricing_catalog_repository,
)
from backend.aws_twinmaker_pricing_plan import AwsTwinMakerPricingPlanError
from backend.fetch_data.cloud_price_fetcher_aws import (
    TwinMakerPricingCatalogError,
)
from backend.sse_utils import (
    PricingOperationFilter,
    ThreadSafeSseHandler,
    emit_sse,
    pricing_operation_id,
)
from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["Pricing"])

LOCAL_CREDENTIAL_FILE_CHECKS_ENV = "ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS"


def _require_local_credential_file_checks_enabled() -> None:
    if os.getenv(LOCAL_CREDENTIAL_FILE_CHECKS_ENV, "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "LOCAL_CREDENTIAL_FILE_CHECKS_DISABLED",
                "message": "File-based pricing refresh is disabled for this runtime.",
                "fix_suggestion": (
                    "Use /fetch_pricing_with_credentials/{provider} with request-body "
                    "credentials or start the explicit local-cloud Compose override."
                ),
                "http_status": 403,
            },
        )


def _pricing_error_detail(
    error_code: str,
    message: str,
    fix_suggestion: str,
    http_status: int,
) -> dict:
    return {
        "error_code": error_code,
        "message": message,
        "fix_suggestion": fix_suggestion,
        "http_status": http_status,
    }


def _pricing_catalog_http_error(
    *,
    status_code: int,
    error_code: str,
    message: str,
    fix_suggestion: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=_pricing_error_detail(
            error_code,
            message,
            fix_suggestion,
            status_code,
        ),
    )


def _cached_refresh_result(
    provider: str,
    pricing_region: str,
) -> dict | None:
    pricing_region = _validate_pricing_region(provider, pricing_region)
    repository = get_pricing_catalog_repository()
    try:
        repository.resolve_published(
            provider,
            pricing_region,
            require_fresh=True,
        )
    except (PricingCatalogNotFoundError, PricingCatalogStaleError):
        return None
    return PricingCatalogRefreshService(repository).cached_result(
        provider,
        pricing_region,
    )


class PricingSourceRecordResponse(BaseModel):
    record_id: str
    intent_id: str
    provider: str
    layer: str
    service_key: str
    field_id: str
    key_path: List[str]
    aliases: List[List[str]]
    canonical_unit: str
    source_unit: str
    quantity_basis: str
    normalizer: Optional[str]
    primary_source_type: str
    refreshability: str
    failure_behavior: str
    evidence: str
    review_state: str
    emergency_fallback_source_type: Optional[str]
    emergency_fallback_allowed: bool


class PricingSourceInventoryResponse(BaseModel):
    schema_version: str = "pricing-source-inventory.v1"
    objective: str = "cost"
    provider: Optional[str] = None
    summary: Dict[str, int]
    records: List[PricingSourceRecordResponse]


def _review_state(record: Dict[str, object]) -> str:
    failure_behavior = record["failure_behavior"]
    if failure_behavior == "mark_unsupported":
        return "unsupported"
    if failure_behavior == "require_review":
        return "review_required"
    if failure_behavior in {"reject_field", "use_reviewed_decision", "derive_from_usage_model"}:
        return "ready"
    return "failed"


def _summarize_records(records: List[Dict[str, object]]) -> Dict[str, int]:
    summary = {
        "total": len(records),
        "ready": 0,
        "review_required": 0,
        "unsupported": 0,
        "failed": 0,
    }
    for record in records:
        summary[_review_state(record)] += 1
    return summary


@router.get(
    "/pricing/source_inventory",
    operation_id="getPricingSourceInventory",
    response_model=PricingSourceInventoryResponse,
    summary="Return pricing source inventory and review state",
    description=(
        "Returns the pricing source governance contract used by the Optimizer. "
        "Management API and UI clients can use this to display which pricing "
        "fields are dynamic, static, derived, review-required, or unsupported."
    ),
    responses={
        200: {"description": "Pricing source inventory"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    },
)
def get_pricing_source_inventory(provider: Optional[str] = None):
    allowed_providers = {"aws", "azure", "gcp"}
    normalized_provider = provider.lower() if provider else None
    if normalized_provider and normalized_provider not in allowed_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    try:
        records = [record.as_dict() for record in pricing_source_inventory()]
        if normalized_provider:
            records = [
                record
                for record in records
                if record["provider"] == normalized_provider
            ]
        for record in records:
            record["review_state"] = _review_state(record)

        return {
            "schema_version": "pricing-source-inventory.v1",
            "objective": "cost",
            "provider": normalized_provider,
            "summary": _summarize_records(records),
            "records": records,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building pricing source inventory: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to build pricing source inventory. Check server logs.",
        )


# --------------------------------------------------
# Pricing Fetching Endpoints
# --------------------------------------------------

@router.post(
    "/fetch_pricing/aws",
    operation_id="refreshAwsPricing",
    summary="Refresh AWS pricing data from Price List API",
    description=(
        "**Purpose:** Fetches current AWS pricing data and caches it locally for use in cost calculations.\n\n"
        "**When to use:**\n"
        "- Before running calculations if pricing data is stale (>7 days old)\n"
        "- Debug/local-cloud mode when you need guaranteed fresh pricing data from mounted credential files\n"
        "- After AWS announces pricing changes\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- Fresh file-based refresh requires `ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true`\n"
        "- App flows should use `/fetch_pricing_with_credentials/aws`\n"
        "- May take 30-60 seconds for a full refresh"
    ),
    responses={
        200: {"description": "Pricing data (cached or freshly fetched)"},
        403: ERROR_RESPONSES[403],
        401: ERROR_RESPONSES[401],
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_aws(
    additional_debug: bool = False,
    force_fetch: bool = False,
    pricing_region: str = "eu-central-1",
):
    """
    Fetches the latest AWS pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the AWS Price List API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for AWS services.
    """
    try:
        if not force_fetch:
            cached = _cached_refresh_result("aws", pricing_region)
            if cached is not None:
                logger.info("Using cached AWS pricing catalog")
                return cached

        _require_local_credential_file_checks_enabled()
        logger.info("Fetching fresh AWS pricing catalog")
        return calculate_up_to_date_pricing(
            "aws",
            additional_debug,
            pricing_region=pricing_region,
        )
    except PricingCatalogContractError as e:
        raise _pricing_catalog_http_error(
            status_code=400,
            error_code="PRICING_CATALOG_REFERENCE_INVALID",
            message=str(e),
            fix_suggestion="Provide a canonical AWS pricing region.",
        ) from e
    except PricingCatalogRefreshInProgressError as e:
        raise _pricing_catalog_http_error(
            status_code=409,
            error_code=e.code,
            message=str(e),
            fix_suggestion="Wait for the active regional refresh to finish.",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching AWS pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AWS pricing. Check server logs.")


@router.post(
    "/fetch_pricing/azure",
    operation_id="refreshAzurePricing",
    summary="Refresh Azure pricing data from Retail Prices API",
    description=(
        "**Purpose:** Fetches current Azure pricing data and caches it locally.\n\n"
        "**When to use:**\n"
        "- Before running calculations if pricing data is stale\n"
        "- The Azure Retail Prices API is public - no credentials required\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- No authentication required (public API)"
    ),
    responses={
        200: {"description": "Pricing data (cached or freshly fetched)"},
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_azure(
    additional_debug: bool = False,
    force_fetch: bool = False,
    pricing_region: str = "westeurope",
):
    """
    Fetches the latest Azure pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Azure Retail Prices API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for Azure services.
    """
    try:
        if not force_fetch:
            cached = _cached_refresh_result("azure", pricing_region)
            if cached is not None:
                logger.info("Using cached Azure pricing catalog")
                return cached

        logger.info("Fetching fresh Azure pricing catalog")
        return calculate_up_to_date_pricing(
            "azure",
            additional_debug,
            pricing_region=pricing_region,
        )
    except PricingCatalogContractError as e:
        raise _pricing_catalog_http_error(
            status_code=400,
            error_code="PRICING_CATALOG_REFERENCE_INVALID",
            message=str(e),
            fix_suggestion="Provide a canonical Azure pricing region.",
        ) from e
    except PricingCatalogRefreshInProgressError as e:
        raise _pricing_catalog_http_error(
            status_code=409,
            error_code=e.code,
            message=str(e),
            fix_suggestion="Wait for the active regional refresh to finish.",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Azure pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Azure pricing. Check server logs.")


@router.post(
    "/fetch_pricing/gcp",
    operation_id="refreshGcpPricing",
    summary="Refresh GCP pricing data from Cloud Billing API",
    description=(
        "**Purpose:** Fetches current Google Cloud pricing data and caches it locally.\n\n"
        "**When to use:**\n"
        "- Before running calculations if pricing data is stale (>7 days old)\n"
        "- Debug/local-cloud mode when mounted GCP service account credentials are available\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- Fresh file-based refresh requires `ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true`\n"
        "- App flows should use `/fetch_pricing_with_credentials/gcp`"
    ),
    responses={
        200: {"description": "Pricing data (cached or freshly fetched)"},
        403: ERROR_RESPONSES[403],
        401: ERROR_RESPONSES[401],
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_gcp(
    additional_debug: bool = False,
    force_fetch: bool = False,
    pricing_region: str = "europe-west1",
):
    """
    Fetches the latest Google Cloud Platform (GCP) pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Google Cloud Billing API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for GCP services.
    """
    try:
        if not force_fetch:
            cached = _cached_refresh_result("gcp", pricing_region)
            if cached is not None:
                logger.info("Using cached GCP pricing catalog")
                return cached

        _require_local_credential_file_checks_enabled()
        logger.info("Fetching fresh GCP pricing catalog")
        return calculate_up_to_date_pricing(
            "gcp",
            additional_debug,
            pricing_region=pricing_region,
        )
    except PricingCatalogContractError as e:
        raise _pricing_catalog_http_error(
            status_code=400,
            error_code="PRICING_CATALOG_REFERENCE_INVALID",
            message=str(e),
            fix_suggestion="Provide a canonical GCP pricing region.",
        ) from e
    except PricingCatalogRefreshInProgressError as e:
        raise _pricing_catalog_http_error(
            status_code=409,
            error_code=e.code,
            message=str(e),
            fix_suggestion="Wait for the active regional refresh to finish.",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching GCP pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch GCP pricing. Check server logs.")


# --------------------------------------------------
# Currency Endpoint
# --------------------------------------------------

@router.post(
    "/fetch_currency",
    operation_id="refreshCurrencyRates",
    summary="Refresh currency exchange rates (USD/EUR)",
    description=(
        "**Purpose:** Fetches current currency exchange rates for cost display.\n\n"
        "**When to use:**\n"
        "- The calculation engine uses these rates to convert costs between currencies\n"
        "- Rates are cached for 1 day"
    ),
    responses={
        200: {
            "description": "Current exchange rates",
            "content": {"application/json": {"example": {"USD": 1.0, "EUR": 0.92}}}
        },
        500: ERROR_RESPONSES[500],
    }
)
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
        raise HTTPException(status_code=500, detail="Failed to fetch currency rates. Check server logs.")


# --------------------------------------------------
# Immutable pricing catalog inspection
# --------------------------------------------------

@router.get(
    "/pricing/catalogs/baseline/{provider}",
    operation_id="getPricingCatalogBaseline",
    summary="Return the pinned reviewed baseline reference",
    description=(
        "Returns only the immutable reference for the source-controlled reviewed "
        "provider baseline. Use the exact snapshot endpoint to inspect its payload."
    ),
    responses={
        200: {"description": "Pinned baseline reference"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
    }
)
def get_pricing_catalog_baseline(provider: str):
    _validate_provider(provider)
    try:
        snapshot = get_pricing_catalog_repository().resolve_baseline(
            provider,
            require_fresh=False,
        )
        return snapshot.reference.to_http_dict()
    except PricingCatalogNotFoundError as exc:
        raise _pricing_catalog_http_error(
            status_code=404,
            error_code=exc.code,
            message=str(exc),
            fix_suggestion="Restore or regenerate the pinned provider baseline.",
        ) from exc
    except (PricingCatalogTamperedError, PricingCatalogStorageError) as exc:
        logger.error("Pricing catalog baseline lookup failed: %s", exc.code)
        raise _pricing_catalog_http_error(
            status_code=500,
            error_code=exc.code,
            message="Pricing catalog storage failed integrity validation.",
            fix_suggestion="Restore the catalog volume from a verified baseline or backup.",
        ) from exc


@router.get(
    "/pricing/catalogs/{provider}/{pricing_region}/published",
    operation_id="getPublishedPricingCatalog",
    summary="Return the active provider-region pricing reference",
    responses={
        200: {"description": "Active immutable catalog reference"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
    },
)
def get_published_pricing_catalog(provider: str, pricing_region: str):
    _validate_provider(provider)
    pricing_region = _validate_pricing_region(provider, pricing_region)
    try:
        snapshot = get_pricing_catalog_repository().resolve_published(
            provider,
            pricing_region,
            require_fresh=False,
        )
        return {
            "reference": snapshot.reference.to_http_dict(),
            "isFresh": not get_pricing_catalog_repository().is_stale(
                snapshot.reference
            ),
        }
    except PricingCatalogNotFoundError as exc:
        raise _pricing_catalog_http_error(
            status_code=404,
            error_code=exc.code,
            message=str(exc),
            fix_suggestion="Refresh or publish pricing for the requested provider region.",
        ) from exc
    except (
        PricingCatalogRegionMismatchError,
        PricingCatalogTamperedError,
        PricingCatalogStorageError,
    ) as exc:
        logger.error("Published pricing catalog lookup failed: %s", exc.code)
        raise _pricing_catalog_http_error(
            status_code=500,
            error_code=exc.code,
            message="Pricing catalog storage failed integrity validation.",
            fix_suggestion="Restore the catalog volume from a verified baseline or backup.",
        ) from exc


@router.get(
    "/pricing/catalogs/{provider}/{pricing_region}/snapshots/{snapshot_id}",
    operation_id="getExactPricingCatalogSnapshot",
    summary="Inspect one exact immutable provider pricing snapshot",
    description=(
        "Returns the full pricing and evidence payload only for an explicit "
        "provider, pricing region, and immutable snapshot identity."
    ),
    responses={
        200: {"description": "Exact immutable catalog snapshot"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
    },
)
def get_exact_pricing_catalog_snapshot(
    provider: str,
    pricing_region: str,
    snapshot_id: str,
):
    _validate_provider(provider)
    pricing_region = _validate_pricing_region(provider, pricing_region)
    try:
        snapshot = get_pricing_catalog_repository().resolve_snapshot(
            provider,
            pricing_region,
            snapshot_id,
            require_fresh=False,
        )
        return {
            "reference": snapshot.reference.to_http_dict(),
            "pricing": snapshot.pricing,
        }
    except (PricingCatalogNotFoundError, PricingCatalogRegionMismatchError) as exc:
        raise _pricing_catalog_http_error(
            status_code=404,
            error_code=exc.code,
            message=str(exc),
            fix_suggestion="Use an exact snapshot ID from the requested provider region.",
        ) from exc
    except (PricingCatalogTamperedError, PricingCatalogStorageError) as exc:
        logger.error("Exact pricing catalog lookup failed: %s", exc.code)
        raise _pricing_catalog_http_error(
            status_code=500,
            error_code=exc.code,
            message="Pricing catalog storage failed integrity validation.",
            fix_suggestion="Restore the catalog volume from a verified baseline or backup.",
        ) from exc


def _validate_provider(provider: str) -> None:
    if provider not in {"aws", "azure", "gcp"}:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")


def _validate_pricing_region(provider: str, pricing_region: str) -> str:
    try:
        return canonicalize_pricing_region(provider, pricing_region)
    except PricingCatalogContractError as exc:
        raise _pricing_catalog_http_error(
            status_code=400,
            error_code="PRICING_CATALOG_REFERENCE_INVALID",
            message=str(exc),
            fix_suggestion=(
                "Provide a canonical pricing region for the selected provider."
            ),
        ) from exc


# --------------------------------------------------
# Credential-based Pricing Endpoint (for Management API)
# --------------------------------------------------


class CredentialRequest(BaseModel):
    """Credentials for pricing fetch."""
    model_config = ConfigDict(extra="forbid")

    # AWS
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: Optional[str] = None
    aws_configured_account_id: Optional[str] = Field(
        default=None,
        pattern=r"^\d{12}$",
    )
    # Azure public catalog
    azure_region: Optional[str] = "westeurope"
    # GCP
    gcp_service_account_json: Optional[str] = None
    gcp_project_id: Optional[str] = None
    gcp_billing_account: Optional[str] = None
    gcp_region: Optional[str] = "europe-west1"

    @model_validator(mode="after")
    def require_aws_target_region(self):
        aws_fields_present = any(
            (
                self.aws_access_key_id,
                self.aws_secret_access_key,
                self.aws_session_token,
                self.aws_configured_account_id,
            )
        )
        if aws_fields_present and not self.aws_region:
            raise ValueError("aws_region is required for AWS pricing credentials")
        return self


def _pricing_stream_failure_message(provider: str) -> str:
    """Return a stable, non-secret SSE error message for UI clients."""
    return (
        f"❌ {provider.upper()} pricing fetch failed. "
        "Check Optimizer logs and credential setup, then retry."
    )


def _redact_credential_values(message: str, credentials: CredentialRequest) -> str:
    """Remove known credential values from client-facing error text."""
    return redact_secret_like_text(
        message,
        extra_secrets=credential_strings(credentials.model_dump()),
    )


@router.post(
    "/fetch_pricing_with_credentials/{provider}",
    operation_id="fetchPricingWithCredentials",
    summary="Fetch pricing using twin credentials",
    description=(
        "**Purpose:** Refresh pricing data using credentials from request body.\n\n"
        "**When to call:** Management API integration to refresh pricing with saved twin credentials.\n\n"
        "**Credentials:** AWS needs access keys; Azure uses public API; GCP needs service account JSON."
    ),
    responses={
        200: {"description": "Pricing data fetched"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
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
        raise HTTPException(
            status_code=400,
            detail=_pricing_error_detail(
                "INVALID_PROVIDER",
                f"Invalid provider: {provider}",
                "Use one of: aws, azure, gcp.",
                400,
            ),
        )
    
    try:
        # Azure uses public API - no credentials needed
        if provider == "azure":
            pricing_region = credentials.azure_region or "westeurope"
            if not force_fetch:
                cached = _cached_refresh_result("azure", pricing_region)
                if cached is not None:
                    logger.info("Using cached Azure pricing catalog")
                    return cached
            logger.info("Fetching fresh Azure pricing catalog")
            return calculate_up_to_date_pricing(
                "azure",
                additional_debug=False,
                pricing_region=pricing_region,
            )

        pricing_region = (
            credentials.aws_region
            if provider == "aws"
            else credentials.gcp_region
        )
        if not pricing_region:
            raise ValueError(
                f"{provider.upper()} pricing region is required"
            )
        if not force_fetch:
            cached = _cached_refresh_result(provider, pricing_region)
            if cached is not None:
                logger.info("Using cached %s pricing catalog", provider.upper())
                return cached

        # AWS/GCP need credentials
        from backend.fetch_data.calculate_up_to_date_pricing import (
            calculate_up_to_date_pricing_with_credentials
        )
        
        creds_dict = credentials.model_dump()
        return calculate_up_to_date_pricing_with_credentials(provider, creds_dict)

    except AwsTwinMakerPricingPlanError as e:
        status = {
            "AWS_TWINMAKER_PLAN_AUTHENTICATION_FAILED": 401,
            "AWS_TWINMAKER_PLAN_PERMISSION_DENIED": 403,
            "AWS_TWINMAKER_PLAN_ACCOUNT_MISMATCH": 409,
            "AWS_TWINMAKER_PLAN_THROTTLED": 429,
            "AWS_TWINMAKER_PLAN_RESPONSE_INVALID": 502,
        }.get(e.code, 502)
        logger.warning("AWS TwinMaker plan observation failed: %s", e.code)
        raise HTTPException(
            status_code=status,
            detail=_pricing_error_detail(
                e.code,
                e.public_message,
                (
                    "Validate the AWS pricing connection, account scope, target "
                    "region, and iottwinmaker:GetPricingPlan permission."
                ),
                status,
            ),
        )
    except TwinMakerPricingCatalogError as e:
        logger.warning("AWS TwinMaker catalog refresh failed: %s", e.code)
        raise HTTPException(
            status_code=502,
            detail=_pricing_error_detail(
                e.code,
                e.public_message,
                (
                    "Retry after verifying AWS Price List API availability and "
                    "the regional TwinMaker catalog contract."
                ),
                502,
            ),
        )
    except HTTPException:
        raise
    except ValueError as e:
        redacted_message = _redact_credential_values(str(e), credentials)
        logger.warning("Invalid %s pricing credential request: %s", provider, redacted_message)
        raise HTTPException(
            status_code=400,
            detail=_pricing_error_detail(
                "PRICING_CREDENTIAL_REQUEST_INVALID",
                redacted_message,
                (
                    "Provide complete request-body credentials for the selected provider. "
                    "AWS requires access key and secret key; GCP requires service account JSON."
                ),
                400,
            ),
        )
    except PricingCatalogRefreshInProgressError as e:
        raise HTTPException(
            status_code=409,
            detail=_pricing_error_detail(
                "PRICING_REFRESH_IN_PROGRESS",
                str(e),
                "Wait for the active provider refresh to finish, then retry.",
                409,
            ),
        )
    except Exception as e:
        safe_error = _redact_credential_values(str(e), credentials)
        logger.error("Error fetching %s pricing with credentials: %s", provider, safe_error)
        raise HTTPException(
            status_code=500,
            detail=_pricing_error_detail(
                "PRICING_REFRESH_FAILED",
                f"Failed to fetch {provider} pricing.",
                "Check Optimizer logs and retry after fixing provider API or credential issues.",
                500,
            ),
        )


# --------------------------------------------------
# SSE Streaming Endpoint
# --------------------------------------------------

@router.post(
    "/stream/fetch_pricing/{provider}",
    operation_id="streamFetchPricing",
    summary="SSE stream for pricing fetch with real-time logs",
    description=(
        "**Purpose:** Stream real-time logs during pricing data fetch via Server-Sent Events.\n\n"
        "**Event types:**\n"
        "- `log`: Progress message from pricing fetch operations\n"
        "- `heartbeat`: Keep-alive signal (every 10s during long operations)\n"
        "- `complete`: Pricing fetch completed successfully\n"
        "- `error`: An error occurred during fetch\n\n"
        "**Dual Output:** Logs appear in both SSE stream AND container logs."
    ),
    responses={
        200: {"description": "SSE stream of log events"},
        400: ERROR_RESPONSES[400],
    }
)
async def stream_fetch_pricing(
    provider: str,
    request: Request,
    credentials: CredentialRequest = Body(default=CredentialRequest())
):
    """
    SSE endpoint that streams logger output during pricing fetch.
    
    Uses log handler capture pattern to stream all logger.info() calls
    from the pricing fetch functions to the SSE stream, while also
    writing them to container logs (dual output).
    """
    if provider not in ["aws", "azure", "gcp"]:
        return StreamingResponse(
            iter([emit_sse(f"Invalid provider: {provider}. Must be aws, azure, or gcp.", "error")]),
            media_type="text/event-stream"
        )
    
    async def event_generator():
        loop = asyncio.get_event_loop()
        queue = asyncio.Queue(maxsize=100)
        operation_id = uuid4().hex
        handler = ThreadSafeSseHandler(queue, loop)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.INFO)
        handler.addFilter(PricingOperationFilter(operation_id))
        logger.addHandler(handler)
        
        try:
            yield emit_sse(f"Starting {provider.upper()} pricing fetch...")
            
            # Import pricing functions
            from backend.fetch_data.calculate_up_to_date_pricing import (
                calculate_up_to_date_pricing_with_credentials
            )
            
            def run_refresh():
                token = pricing_operation_id.set(operation_id)
                try:
                    if provider == "azure":
                        return calculate_up_to_date_pricing(
                            provider,
                            False,
                            pricing_region=(
                                credentials.azure_region or "westeurope"
                            ),
                        )
                    return calculate_up_to_date_pricing_with_credentials(
                        provider, credentials.model_dump(), False
                    )
                finally:
                    pricing_operation_id.reset(token)

            task = loop.run_in_executor(None, run_refresh)
            
            # Yield logs as they arrive, check for disconnect
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    return
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield emit_sse(msg)
                except asyncio.TimeoutError:
                    yield emit_sse("⏳", "heartbeat")
            
            # Drain remaining logs from queue
            while not queue.empty():
                try:
                    msg = queue.get_nowait()
                    yield emit_sse(msg)
                except asyncio.QueueEmpty:
                    break
            
            # Check if task raised an exception
            try:
                await task
                yield emit_sse(f"✅ {provider.upper()} pricing fetch complete!", "complete")
            except Exception as e:
                logger.error("Pricing fetch failed for %s (%s)", provider, type(e).__name__)
                yield emit_sse(_pricing_stream_failure_message(provider), "error")
            
        except Exception as e:
            logger.error("Pricing stream failed for %s (%s)", provider, type(e).__name__)
            yield emit_sse(_pricing_stream_failure_message(provider), "error")
        finally:
            logger.removeHandler(handler)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
