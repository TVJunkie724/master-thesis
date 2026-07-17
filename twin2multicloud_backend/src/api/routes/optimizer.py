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
from sqlalchemy.orm import Session
from typing import Any

from src.models.database import get_db
from src.models.user import User
from src.api.dependencies import get_current_user
from src.clients.optimizer_client import OptimizerClient
from src.services.pricing_review_state_service import build_pricing_review_state_response
from src.schemas.pricing_review import PricingReviewStateResponse
from src.schemas.pricing_health import PricingHealthResponse
from src.schemas.optimizer_calculation import OptimizerCalculationParams
from src.repositories.twin_repository import TwinRepository
from src.services.aws_twinmaker_pricing_context_service import (
    AwsTwinMakerPricingContextService,
)
from src.services.pricing_catalog_context_service import PricingCatalogContextService
from src.services.optimizer_calculation_service import OptimizerCalculationService
from src.services.optimizer_pricing_catalog_service import OptimizerPricingCatalogService
from src.services.optimizer_pricing_refresh_service import OptimizerPricingRefreshService
from src.services.optimizer_pricing_stream_service import OptimizerPricingStreamService
from src.services.optimizer_status_service import OptimizerStatusService
from src.services.cloud_access_inventory_service import CloudAccessInventoryService
from src.services.pricing_health_service import build_pricing_health_response
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.errors import (
    ExternalServiceError,
    ExternalServiceUnavailable,
    OptimizerContractError,
    PricingCatalogUnavailable,
)
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

def _optimizer_status_service() -> OptimizerStatusService:
    """Build the optimizer status service for this request."""
    return OptimizerStatusService()


def _optimizer_calculation_service(db: Session) -> OptimizerCalculationService:
    """Build the optimizer calculation service for this request."""
    optimizer_client = OptimizerClient()
    return OptimizerCalculationService(
        optimizer_client=optimizer_client,
        aws_twinmaker_contexts=AwsTwinMakerPricingContextService(db),
        pricing_catalog_contexts=PricingCatalogContextService(
            db,
            optimizer_client=optimizer_client,
        ),
    )


def _pricing_catalog_context_service(
    db: Session,
) -> PricingCatalogContextService:
    """Build the owner-scoped catalog context resolver."""
    return PricingCatalogContextService(db)


def _optimizer_pricing_catalog_service() -> OptimizerPricingCatalogService:
    """Build the authenticated exact-catalog diagnostic service."""
    return OptimizerPricingCatalogService()


def _optimizer_pricing_refresh_service(db: Session) -> OptimizerPricingRefreshService:
    """Build the optimizer pricing refresh service for this request."""
    return OptimizerPricingRefreshService(db=db, twin_repository=TwinRepository(db))


def _optimizer_pricing_stream_service(db: Session) -> OptimizerPricingStreamService:
    """Build the optimizer pricing stream service for this request."""
    return OptimizerPricingStreamService(db=db, twin_repository=TwinRepository(db))


def _raise_downstream_http_error(exc: DownstreamServiceError) -> None:
    """Map typed downstream service errors to the existing HTTP contract."""
    raise HTTPException(exc.status_code, exc.public_detail) from exc


async def _owner_pricing_statuses(
    db: Session,
    user_id: str,
) -> dict[str, dict[str, Any]]:
    try:
        return await _pricing_catalog_context_service(db).status_for_user(
            user_id
        )
    except (ExternalServiceError, ExternalServiceUnavailable) as exc:
        _raise_downstream_http_error(map_optimizer_client_error(exc))
    except OptimizerContractError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


# ============================================================================
# Data Freshness Endpoints
# ============================================================================

@router.get(
    "/pricing-status",
    operation_id="getPricingStatus",
    summary="Get active pricing catalog status for all providers",
    description=(
        "**Purpose:** Check the exact immutable catalog selected for each provider before calculations.\n\n"
        "**When to call:** Before `calculateOptimalDistribution` to decide if `refreshPricing` is needed.\n\n"
        "**Response fields per provider:**\n"
        "- `age`: Human-readable age (e.g., '3 days')\n"
        "- `is_fresh`: Boolean, true only while the catalog is calculation-eligible\n"
        "- `active_reference`: Exact provider, region, version, timestamp, and digest identity"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        502: {"description": "Optimizer contract or request failed"},
        503: {"description": "Cannot connect to Optimizer service"},
        504: {"description": "Optimizer service timed out"},
    }
)
async def get_pricing_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get owner-scoped immutable pricing catalog status for all providers.
    
    Returns the exact catalog identity and freshness status
    for AWS, Azure, and GCP.
    """
    return await _owner_pricing_statuses(db, current_user.id)


@router.get(
    "/pricing-review-state",
    response_model=PricingReviewStateResponse,
    operation_id="getPricingReviewState",
    summary="Get typed pricing review state for all providers",
    description=(
        "**Purpose:** Expose pricing quality/freshness as typed state for UI and calculation guards.\n\n"
        "**When to call:** Before calculation and after pricing refresh.\n\n"
        "**Response fields per provider:**\n"
        "- `state`: `fresh`, `stale`, `review_required`, `missing`, or `failed`\n"
        "- `review_required`: true when user-visible review/action is needed\n"
        "- `can_calculate`: true only when an exact published catalog is fresh\n"
        "- `calculation_source`: immutable catalog source or `unavailable`\n"
        "- `review_reasons`: structured reasons such as missing keys or failed Optimizer status"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        502: {"description": "Optimizer contract or request failed"},
        503: {"description": "Cannot connect to Optimizer service"},
        504: {"description": "Optimizer service timed out"},
    }
)
async def get_pricing_review_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get typed pricing review state for Flutter and Management API consumers.

    This keeps pricing refresh logs diagnostic-only. UI should render this
    contract rather than parsing SSE log text.
    """
    optimizer_statuses = await _owner_pricing_statuses(db, current_user.id)
    return build_pricing_review_state_response(optimizer_statuses)


@router.get(
    "/pricing-health",
    response_model=PricingHealthResponse,
    operation_id="getPricingHealth",
    summary="Get dashboard-ready pricing health for all providers",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        502: {"description": "Optimizer service request failed"},
        503: {"description": "Cannot connect to Optimizer service"},
        504: {"description": "Optimizer service timed out"},
    },
)
async def get_pricing_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    optimizer_statuses = await _owner_pricing_statuses(db, current_user.id)

    review_state = build_pricing_review_state_response(
        optimizer_statuses,
    )
    cloud_access = CloudAccessInventoryService(db).build_inventory(current_user.id)
    return build_pricing_health_response(review_state, cloud_access)


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
# Exact pricing catalog diagnostics
# ============================================================================

@router.get(
    "/pricing/catalogs/{provider}/{pricing_region}/snapshots/{snapshot_id}",
    operation_id="getExactPricingCatalogSnapshot",
    summary="Inspect one exact immutable pricing catalog snapshot",
    description=(
        "Returns one explicitly identified, size-bounded provider-region "
        "snapshot for authenticated diagnostics. Calculations and persistence "
        "use references only."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: {"description": "Exact pricing catalog does not exist"},
        502: {"description": "Optimizer contract or request failed"},
        503: {"description": "Cannot connect to Optimizer service"},
        504: {"description": "Optimizer service timed out"},
    }
)
async def get_exact_pricing_catalog_snapshot(
    provider: str,
    pricing_region: str,
    snapshot_id: str,
    current_user: User = Depends(get_current_user)
):
    """Proxy one exact diagnostic snapshot without exposing a latest alias."""
    try:
        return await _optimizer_pricing_catalog_service().get_exact_snapshot(
            provider,
            pricing_region,
            snapshot_id,
        )
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
    summary="Refresh pricing using a bound CloudConnection",
    description=(
        "**Purpose:** Fetch fresh pricing data from cloud provider APIs using a bound CloudConnection.\n\n"
        "**Prerequisites:**\n"
        "- AWS: Requires an AWS CloudConnection bound to the twin\n"
        "- Azure: No credentials needed (uses public Retail Prices API)\n"
        "- GCP: Requires a GCP CloudConnection bound to the twin\n\n"
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
    Refresh pricing using credentials resolved from the twin's CloudConnection.
    
    - AWS: Requires an AWS CloudConnection
    - Azure: No credentials needed (public API)
    - GCP: Requires a GCP CloudConnection
    
    Credentials are decrypted from CloudConnection storage and forwarded to Optimizer.
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
    params: OptimizerCalculationParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        return await _optimizer_calculation_service(db).calculate(
            params.to_optimizer_payload(),
            current_user.id,
        )
    except PricingCatalogUnavailable as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": exc.error_code,
                "message": exc.message,
            },
        ) from exc
    except OptimizerContractError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except DownstreamServiceError as exc:
        _raise_downstream_http_error(exc)
