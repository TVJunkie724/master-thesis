"""
Optimizer API proxy routes.
Proxies all Optimizer (port 5003) calls through Management API (port 5005).

This module provides:
- Data freshness endpoints (pricing/regions age)
- Credential-forwarded pricing refresh
- Calculation endpoint proxy
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from src.models.database import get_db
from src.models.user import User
from src.api.dependencies import get_current_user
from src.repositories.twin_repository import TwinRepository
from src.services.optimizer_calculation_service import OptimizerCalculationService
from src.services.optimizer_pricing_export_service import OptimizerPricingExportService
from src.services.optimizer_pricing_refresh_service import OptimizerPricingRefreshService
from src.services.optimizer_pricing_stream_service import OptimizerPricingStreamService
from src.services.optimizer_status_service import OptimizerStatusService
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

def _optimizer_status_service() -> OptimizerStatusService:
    """Build the optimizer status service for this request."""
    return OptimizerStatusService()


def _optimizer_calculation_service() -> OptimizerCalculationService:
    """Build the optimizer calculation service for this request."""
    return OptimizerCalculationService()


def _optimizer_pricing_export_service() -> OptimizerPricingExportService:
    """Build the optimizer pricing export service for this request."""
    return OptimizerPricingExportService()


def _optimizer_pricing_refresh_service(db: Session) -> OptimizerPricingRefreshService:
    """Build the optimizer pricing refresh service for this request."""
    return OptimizerPricingRefreshService(db=db, twin_repository=TwinRepository(db))


def _optimizer_pricing_stream_service(db: Session) -> OptimizerPricingStreamService:
    """Build the optimizer pricing stream service for this request."""
    return OptimizerPricingStreamService(db=db, twin_repository=TwinRepository(db))


def _raise_downstream_http_error(exc: DownstreamServiceError) -> None:
    """Map typed downstream service errors to the existing HTTP contract."""
    raise HTTPException(exc.status_code, exc.public_detail) from exc


# ============================================================================
# Data Freshness Endpoints
# ============================================================================

@router.get(
    "/pricing-status",
    operation_id="getPricingStatus",
    summary="Get pricing cache status for all providers",
    description=(
        "**Purpose:** Check freshness of cached pricing data before calculations.\n\n"
        "**When to call:** Before `calculateOptimalDistribution` to decide if `refreshPricing` is needed.\n\n"
        "**Response fields per provider:**\n"
        "- `age`: Human-readable age (e.g., '3 days')\n"
        "- `is_fresh`: Boolean, true if cached data < 7 days old\n"
        "- `status`: 'valid', 'incomplete', 'missing', or 'error'"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        503: {"description": "Cannot connect to Optimizer service"},
    }
)
async def get_pricing_status(current_user: User = Depends(get_current_user)):
    """
    Get pricing file age/status for all providers.
    
    Returns the age and freshness status of cached pricing data
    for AWS, Azure, and GCP.
    """
    try:
        return await _optimizer_status_service().get_pricing_status()
    except DownstreamServiceError as exc:
        _raise_downstream_http_error(exc)


@router.get(
    "/regions-status",
    operation_id="getRegionsStatus",
    summary="Get regions cache status for all providers",
    description=(
        "**Purpose:** Check freshness of cached region/location data.\n\n"
        "**When to call:** Before calculations if region availability matters.\n\n"
        "**Response fields per provider:**\n"
        "- `age`: Human-readable age\n"
        "- `is_fresh`: Boolean (AWS/Azure: 7 days, GCP: 30 days threshold)"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        503: {"description": "Cannot connect to Optimizer service"},
    }
)
async def get_regions_status(current_user: User = Depends(get_current_user)):
    """
    Get regions file age for all providers.
    
    Returns the age and freshness status of cached region data
    for AWS, Azure, and GCP.
    """
    try:
        return await _optimizer_status_service().get_regions_status()
    except DownstreamServiceError as exc:
        _raise_downstream_http_error(exc)


# ============================================================================
# Pricing Export (for snapshotting)
# ============================================================================

@router.get(
    "/pricing/export/{provider}",
    operation_id="exportPricingSnapshot",
    summary="Export pricing data for snapshotting",
    description=(
        "**Purpose:** Export full pricing data for a provider to store as snapshot with calculation results.\n\n"
        "**When to call:** After `calculateOptimalDistribution` to preserve the pricing data used.\n\n"
        "**Path parameter:** provider = 'aws', 'azure', or 'gcp'"
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        503: {"description": "Cannot connect to Optimizer service"},
    }
)
async def proxy_pricing_export(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """Proxy to Optimizer service for pricing export (for snapshotting)."""
    try:
        return await _optimizer_pricing_export_service().export_pricing_snapshot(provider)
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except DownstreamServiceError as exc:
        _raise_downstream_http_error(exc)


# ============================================================================
# Pricing Refresh Endpoints
# ============================================================================

@router.post(
    "/refresh-pricing/{provider}",
    operation_id="refreshPricing",
    summary="Refresh pricing using twin's stored credentials",
    description=(
        "**Purpose:** Fetch fresh pricing data from cloud provider APIs using stored credentials.\n\n"
        "**Prerequisites:**\n"
        "- AWS: Requires `aws_access_key_id` and `aws_secret_access_key` stored in twin config\n"
        "- Azure: No credentials needed (uses public Retail Prices API)\n"
        "- GCP: Requires `gcp_service_account_json` stored in twin config\n\n"
        "**When to call:** When `getPricingStatus` shows `is_fresh: false`.\n\n"
        "**Query parameter:** `twin_id` - The twin whose credentials to use"
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Cannot connect to Optimizer service"},
    }
)
async def refresh_pricing(
    provider: str,
    twin_id: str = Query(..., description="Twin ID to get credentials from"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Refresh pricing using twin's stored credentials.
    
    - AWS: Requires aws_access_key_id, aws_secret_access_key from twin config
    - Azure: No credentials needed (public API)
    - GCP: Requires gcp_service_account_json from twin config
    
    Credentials are decrypted from TwinConfiguration and forwarded to Optimizer.
    """
    try:
        return await _optimizer_pricing_refresh_service(db).refresh_pricing(
            provider=provider,
            twin_id=twin_id,
            user_id=current_user.id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except DownstreamServiceError as exc:
        _raise_downstream_http_error(exc)


@router.get(
    "/stream/refresh-pricing/{provider}",
    operation_id="streamRefreshPricing",
    summary="SSE stream for pricing refresh with real-time logs",
    description=(
        "**Purpose:** Same as `refreshPricing` but with real-time progress via Server-Sent Events.\n\n"
        "**Event types:**\n"
        "- `log`: Progress message (e.g., 'Loading credentials...', 'Calling AWS API...')\n"
        "- `complete`: Final success message\n"
        "- `error`: Error occurred, includes error details\n\n"
        "**When to use:** When UI needs live progress feedback during 30-60 second refresh operation."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def stream_refresh_pricing(
    provider: str,
    twin_id: str = Query(..., description="Twin ID to get credentials from"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SSE stream for pricing refresh with real-time logs.
    
    Event types:
    - log: Regular progress message
    - complete: Refresh completed successfully
    - error: An error occurred
    """
    try:
        event_generator = _optimizer_pricing_stream_service(db).build_refresh_stream(
            provider=provider,
            twin_id=twin_id,
            user_id=current_user.id,
        )
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ============================================================================
# Calculation Endpoint
# ============================================================================

class CalcParams(BaseModel):
    """All 26 calculation parameters matching Optimizer API."""
    # Core IoT (required)
    numberOfDevices: int = Field(..., gt=0, description="Number of IoT devices")
    deviceSendingIntervalInMinutes: float = Field(..., gt=0, description="Sending interval in minutes")
    averageSizeOfMessageInKb: float = Field(..., gt=0, description="Average message size in KB")
    
    # Storage durations (required)
    hotStorageDurationInMonths: int = Field(..., ge=1, description="Hot storage duration (months)")
    coolStorageDurationInMonths: int = Field(..., ge=1, description="Cool storage duration (months)")
    archiveStorageDurationInMonths: int = Field(..., ge=6, description="Archive storage duration (months)")
    
    # 3D model settings
    needs3DModel: bool = Field(..., description="Whether 3D model is needed")
    entityCount: int = Field(0, ge=0, description="Number of 3D entities")
    average3DModelSizeInMB: float = Field(100.0, gt=0, description="Average 3D model size in MB")
    
    # Dashboard settings
    amountOfActiveEditors: int = Field(0, ge=0, description="Monthly active editors")
    amountOfActiveViewers: int = Field(0, ge=0, description="Monthly active viewers")
    dashboardRefreshesPerHour: int = Field(0, ge=0, description="Dashboard refresh rate")
    dashboardActiveHoursPerDay: int = Field(0, ge=0, le=24, description="Active hours per day")
    
    # Supporter services
    useEventChecking: bool = False
    triggerNotificationWorkflow: bool = False
    returnFeedbackToDevice: bool = False
    integrateErrorHandling: bool = False
    
    # Numeric parameters
    orchestrationActionsPerMessage: int = Field(3, ge=1)
    eventsPerMessage: int = Field(1, ge=1)
    apiCallsPerDashboardRefresh: int = Field(1, ge=1)
    
    # Enhanced calculation
    numberOfDeviceTypes: int = Field(1, ge=1, description="Number of device types")
    numberOfEventActions: int = Field(0, ge=0, description="Number of event actions")
    eventTriggerRate: float = Field(0.1, ge=0.0, le=1.0, description="Event trigger rate (0-1)")
    
    # GCP self-hosted (always False - not implemented)
    allowGcpSelfHostedL4: bool = False
    allowGcpSelfHostedL5: bool = False
    
    # Currency
    currency: str = Field("USD", description="Currency code (USD or EUR)")


@router.put(
    "/calculate",
    operation_id="calculateOptimalDistribution",
    summary="Proxy calculation request to Optimizer",
    description=(
        "**Purpose:** Calculate optimal cross-cloud distribution for a Digital Twin based on 26 parameters.\n\n"
        "**Prerequisites:** Call `getPricingStatus` first - if `is_fresh: false`, call `refreshPricing`.\n\n"
        "**Response includes:**\n"
        "- `awsCosts`, `azureCosts`, `gcpCosts`: Per-layer cost breakdowns\n"
        "- `cheapestPath`: Optimal provider selection per layer (L1-L5)\n"
        "- `combinationTables`: Detailed cost analysis matrices\n"
        "- `transferCosts`: Cross-cloud data transfer estimates"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        422: ERROR_RESPONSES[422],
        503: {"description": "Cannot connect to Optimizer service"},
    }
)
async def calculate(
    params: CalcParams,
    current_user: User = Depends(get_current_user)
):
    """
    Proxy calculation request to Optimizer.
    
    Accepts all calculation parameters and forwards to the Optimizer service.
    Returns the full optimization result including:
    - awsCosts, azureCosts, gcpCosts
    - cheapestPath
    - Optimization overrides (l1, l2, l3, l4)
    - Combination tables
    - Transfer costs
    """
    try:
        return await _optimizer_calculation_service().calculate(params.model_dump())
    except DownstreamServiceError as exc:
        _raise_downstream_http_error(exc)
