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
from src.utils.crypto import decrypt

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

# Use environment variable or fallback to docker service name
OPTIMIZER_URL = getattr(settings, 'OPTIMIZER_URL', 'http://master-thesis-2twin2clouds-1:8000')


# ============================================================================
# Helper
# ============================================================================

async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    """Verify twin ownership and return twin."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin


# ============================================================================
# Data Freshness Endpoints
# ============================================================================

@router.get("/pricing-status")
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


@router.get("/regions-status")
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


# ============================================================================
# Pricing Export (for snapshotting)
# ============================================================================

@router.get("/pricing/export/{provider}")
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


# ============================================================================
# Pricing Refresh Endpoints
# ============================================================================

@router.post("/refresh-pricing/{provider}")
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
        
        # AWS/GCP need credentials from twin config
        twin = await get_user_twin(twin_id, current_user, db)
        config = twin.configuration
        
        if not config:
            raise HTTPException(400, "Twin has no configuration. Complete Step 1 first.")
        
        credentials = {}
        if provider == "aws":
            if not config.aws_access_key_id:
                raise HTTPException(400, "AWS credentials not configured in Step 1")
            credentials = {
                "aws_access_key_id": decrypt(config.aws_access_key_id, current_user.id, twin_id),
                "aws_secret_access_key": decrypt(config.aws_secret_access_key, current_user.id, twin_id),
                "aws_region": config.aws_region or "eu-central-1"
            }
        elif provider == "gcp":
            if not config.gcp_service_account_json:
                raise HTTPException(400, "GCP credentials not configured in Step 1")
            credentials = {
                "gcp_service_account_json": decrypt(config.gcp_service_account_json, current_user.id, twin_id),
                "gcp_region": config.gcp_region or "europe-west1"
            }
        
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


@router.get("/stream/refresh-pricing/{provider}")
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
            return f"event: {event_type}\ndata: {json.dumps({'message': msg})}\n\n"

        yield emit(f"Starting {provider.upper()} pricing refresh...")
        await asyncio.sleep(0.1)  # Allow client to receive

        try:
            # Azure uses public API - no credentials needed
            if provider == "azure":
                yield emit("Azure uses public API - no credentials needed")
                await asyncio.sleep(0.1)
                
                yield emit(f"Calling Azure pricing API (this may take 30-60 seconds)...")
                
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        f"{OPTIMIZER_URL}/fetch_pricing/azure",
                        params={"force_fetch": True}
                    )
                
                if response.status_code == 200:
                    yield emit(f"✅ Successfully refreshed Azure pricing!", "complete")
                else:
                    yield emit(f"❌ Error: {response.text}", "error")
                return
            
            # AWS/GCP need credentials from twin config
            yield emit("Loading twin credentials...")
            await asyncio.sleep(0.1)
            
            twin = await get_user_twin(twin_id, current_user, db)
            config = twin.configuration
            
            if not config:
                yield emit("❌ Error: Twin has no configuration. Complete Step 1 first.", "error")
                return

            credentials = {}
            if provider == "aws":
                if not config.aws_access_key_id:
                    yield emit("❌ Error: AWS credentials not configured in Step 1", "error")
                    return
                credentials = {
                    "aws_access_key_id": decrypt(config.aws_access_key_id, current_user.id, twin_id),
                    "aws_secret_access_key": decrypt(config.aws_secret_access_key, current_user.id, twin_id),
                    "aws_region": config.aws_region or "eu-central-1"
                }
                yield emit("AWS credentials loaded and decrypted")
            elif provider == "gcp":
                if not config.gcp_service_account_json:
                    yield emit("❌ Error: GCP credentials not configured in Step 1", "error")
                    return
                credentials = {
                    "gcp_service_account_json": decrypt(config.gcp_service_account_json, current_user.id, twin_id),
                    "gcp_region": config.gcp_region or "europe-west1"
                }
                yield emit("GCP credentials loaded and decrypted")

            await asyncio.sleep(0.1)
            yield emit(f"Calling {provider.upper()} pricing API (this may take 30-60 seconds)...")

            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{OPTIMIZER_URL}/fetch_pricing_with_credentials/{provider}",
                    json=credentials
                )

            if response.status_code == 200:
                yield emit(f"✅ Successfully refreshed {provider.upper()} pricing!", "complete")
            else:
                yield emit(f"❌ Error: {response.text}", "error")

        except httpx.ConnectError:
            yield emit("❌ Error: Cannot connect to Optimizer service", "error")
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


@router.put("/calculate")
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
