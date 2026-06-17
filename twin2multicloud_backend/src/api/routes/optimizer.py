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
import httpx
import asyncio
import json

from src.models.database import get_db
from src.models.twin import DigitalTwin
from src.models.user import User
from src.api.dependencies import get_current_user
from src.config import settings
from src.services.twin_helpers import get_user_twin
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed
from src.services.cloud_access_inventory_service import CloudAccessInventoryService
from src.services.pricing_health_service import build_pricing_health_response
from src.services.pricing_review_state_service import build_pricing_review_state_response
from src.schemas.pricing_health import PricingHealthResponse
from src.schemas.pricing_review import PricingReviewStateResponse
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

# Use environment variable or fallback to docker service name
OPTIMIZER_URL = getattr(settings, 'OPTIMIZER_URL', 'http://master-thesis-2twin2clouds-1:8000')



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
        async with httpx.AsyncClient(timeout=30.0) as client:
            aws = await client.get(f"{OPTIMIZER_URL}/pricing_age/aws")
            azure = await client.get(f"{OPTIMIZER_URL}/pricing_age/azure")
            gcp = await client.get(f"{OPTIMIZER_URL}/pricing_age/gcp")
        return {
            "aws": aws.json() if aws.status_code == 200 else {"error": "Failed to fetch"},
            "azure": azure.json() if azure.status_code == 200 else {"error": "Failed to fetch"},
            "gcp": gcp.json() if gcp.status_code == 200 else {"error": "Failed to fetch"}
        }
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")


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
        "- `can_calculate`: true when fresh, stale, or last-known-good pricing can be used\n"
        "- `calculation_source`: source used by calculations (`fresh`, `stale`, `last_known_good`, `fallback_static`, `unavailable`)\n"
        "- `review_reasons`: structured reasons such as missing keys or failed Optimizer status"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Cannot connect to Optimizer service"},
    }
)
async def get_pricing_review_state(
    twin_id: Optional[str] = Query(
        default=None,
        description="Twin ID used to resolve last-known-good pricing snapshots",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get typed pricing review state for Flutter and Management API consumers.

    This keeps pricing refresh logs diagnostic-only. UI should render this
    contract rather than parsing SSE log text.
    """
    config = None
    if twin_id:
        twin = await get_user_twin(twin_id, current_user, db)
        config = twin.optimizer_config

    try:
        optimizer_statuses = await _get_optimizer_pricing_statuses()
        return build_pricing_review_state_response(
            optimizer_statuses,
            saved_snapshots=_pricing_snapshots_from_config(config),
            saved_timestamps=_pricing_timestamps_from_config(config),
        )
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")


@router.get(
    "/pricing-health",
    response_model=PricingHealthResponse,
    operation_id="getPricingHealth",
    summary="Get dashboard-ready pricing health for all providers",
    description=(
        "**Purpose:** Expose provider pricing readiness for Dashboard cards.\n\n"
        "**Response fields per provider:**\n"
        "- `state`: `fresh`, `stale`, `review_required`, `missing`, or `failed`\n"
        "- `severity`: dashboard severity (`success`, `warning`, `error`, `info`)\n"
        "- `source_label`: user-facing provider account/project/public API label\n"
        "- `credential_summary`: secret-free pricing access metadata\n"
        "- `primary_message`: concise user-actionable status text"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        502: {"description": "Optimizer service request failed"},
        503: {"description": "Cannot connect to Optimizer service"},
        504: {"description": "Optimizer service timed out"},
    },
)
async def get_pricing_health(
    twin_id: Optional[str] = Query(
        default=None,
        description="Twin ID used to resolve last-known-good pricing snapshots",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = None
    if twin_id:
        twin = await get_user_twin(twin_id, current_user, db)
        config = twin.optimizer_config

    try:
        optimizer_statuses = await _get_optimizer_pricing_statuses()
        review_state = build_pricing_review_state_response(
            optimizer_statuses,
            saved_snapshots=_pricing_snapshots_from_config(config),
            saved_timestamps=_pricing_timestamps_from_config(config),
        )
        cloud_access = CloudAccessInventoryService(db).build_inventory(current_user.id)
        return build_pricing_health_response(review_state, cloud_access)
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")


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
        async with httpx.AsyncClient(timeout=30.0) as client:
            aws = await client.get(f"{OPTIMIZER_URL}/regions_age/aws")
            azure = await client.get(f"{OPTIMIZER_URL}/regions_age/azure")
            gcp = await client.get(f"{OPTIMIZER_URL}/regions_age/gcp")
        return {
            "aws": aws.json() if aws.status_code == 200 else {"error": "Failed to fetch"},
            "azure": azure.json() if azure.status_code == 200 else {"error": "Failed to fetch"},
            "gcp": gcp.json() if gcp.status_code == 200 else {"error": "Failed to fetch"}
        }
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")


async def _get_optimizer_pricing_statuses() -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        aws = await client.get(f"{OPTIMIZER_URL}/pricing_age/aws")
        azure = await client.get(f"{OPTIMIZER_URL}/pricing_age/azure")
        gcp = await client.get(f"{OPTIMIZER_URL}/pricing_age/gcp")
    return {
        "aws": aws.json() if aws.status_code == 200 else {"error": "Failed to fetch"},
        "azure": azure.json() if azure.status_code == 200 else {"error": "Failed to fetch"},
        "gcp": gcp.json() if gcp.status_code == 200 else {"error": "Failed to fetch"},
    }


def _pricing_snapshots_from_config(config) -> dict[str, dict | None]:
    if not config:
        return {}
    return {
        "aws": _safe_json_dict(config.pricing_aws_snapshot),
        "azure": _safe_json_dict(config.pricing_azure_snapshot),
        "gcp": _safe_json_dict(config.pricing_gcp_snapshot),
    }


def _pricing_timestamps_from_config(config) -> dict[str, object | None]:
    if not config:
        return {}
    return {
        "aws": config.pricing_aws_updated_at,
        "azure": config.pricing_azure_updated_at,
        "gcp": config.pricing_gcp_updated_at,
    }


def _safe_json_dict(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(400, f"Invalid provider: {provider}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{OPTIMIZER_URL}/pricing/export/{provider}")
        if response.status_code != 200:
            raise HTTPException(response.status_code, response.text)
        return response.json()
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")


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
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(400, f"Invalid provider: {provider}. Must be aws, azure, or gcp")
    
    try:
        # Azure uses public API - no credentials needed
        if provider == "azure":
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{OPTIMIZER_URL}/fetch_pricing/azure",
                    params={"force_fetch": True}
                )
            if response.status_code != 200:
                raise HTTPException(response.status_code, response.text)
            return response.json()
        
        # AWS/GCP need credentials from the bound CloudConnection.
        twin = await get_user_twin(twin_id, current_user, db)
        try:
            resolved = CredentialResolutionService().resolve_provider_credentials(
                twin,
                current_user.id,
                provider,
            )
        except CredentialResolutionFailed as exc:
            raise HTTPException(400, _credential_resolution_detail(exc)) from exc
        credentials = _optimizer_pricing_payload(provider, resolved.optimizer_payload)
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OPTIMIZER_URL}/fetch_pricing_with_credentials/{provider}",
                json=credentials
            )
        
        if response.status_code != 200:
            raise HTTPException(response.status_code, response.text)
        
        return response.json()
        
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")


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
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(400, f"Invalid provider: {provider}")

    async def event_generator():
        def emit(msg: str, event_type: str = "log"):
            return f"event: {event_type}\ndata: {json.dumps({'message': msg, 'type': event_type})}\n\n"

        yield emit(f"Starting {provider.upper()} pricing refresh...")
        await asyncio.sleep(0.1)  # Allow client to receive

        try:
            # Prepare credentials (Management API responsibility - security boundary)
            credentials = {}
            
            if provider == "azure":
                yield emit("Azure uses public API - no credentials needed")
            else:
                # AWS/GCP need credentials from the bound CloudConnection.
                yield emit("Loading Cloud Connection credentials...")
                await asyncio.sleep(0.1)
                
                twin = await get_user_twin(twin_id, current_user, db)
                try:
                    resolved = CredentialResolutionService().resolve_provider_credentials(
                        twin,
                        current_user.id,
                        provider,
                    )
                except CredentialResolutionFailed as exc:
                    detail = _credential_resolution_detail(exc)
                    yield emit(f"Error: {detail['message']}", "error")
                    return

                credentials = _optimizer_pricing_payload(provider, resolved.optimizer_payload)
                yield emit(f"{provider.upper()} Cloud Connection credentials loaded")

            await asyncio.sleep(0.1)
            yield emit(f"Connecting to Optimizer service for {provider.upper()} pricing...")

            # Relay SSE stream from Optimizer
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{OPTIMIZER_URL}/stream/fetch_pricing/{provider}",
                    json=credentials,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    if response.status_code != 200:
                        yield emit(f"❌ Optimizer error: {response.status_code}", "error")
                        return
                    
                    # Relay SSE events from Optimizer
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        # Process complete SSE events (delimited by double newline)
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            if event_str.strip():
                                yield event_str + "\n\n"

        except httpx.ConnectError:
            yield emit("❌ Error: Cannot connect to Optimizer service", "error")
        except httpx.TimeoutException:
            yield emit("❌ Error: Optimizer service timed out", "error")
        except Exception as e:
            yield emit(f"❌ Error: {str(e)}", "error")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


def _credential_resolution_detail(exc: CredentialResolutionFailed) -> dict:
    return {
        "code": "CREDENTIAL_RESOLUTION_FAILED",
        "message": exc.message,
        "errors": exc.errors,
    }


def _optimizer_pricing_payload(provider: str, optimizer_payload: dict) -> dict:
    if provider != "gcp":
        return optimizer_payload
    payload = {
        "gcp_service_account_json": optimizer_payload.get("gcp_credentials_file"),
        "gcp_region": optimizer_payload.get("gcp_region"),
    }
    return {key: value for key, value in payload.items() if value}


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
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                f"{OPTIMIZER_URL}/calculate",
                json=params.model_dump()
            )
        
        if response.status_code != 200:
            raise HTTPException(response.status_code, response.text)
        
        return response.json()
        
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Optimizer service")
    except httpx.TimeoutException:
        raise HTTPException(504, "Optimizer service timed out")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Request failed: {type(e).__name__}")
