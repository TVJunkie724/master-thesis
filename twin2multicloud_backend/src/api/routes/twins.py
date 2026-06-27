"""Digital Twin Management API endpoints.

This module provides CRUD operations for Digital Twins, including deployment
and destroy operations, log tracing, and IoT simulator downloads.

**Key endpoints:**
- CRUD: Create, Read, Update, Delete twins
- Deployment: Deploy/Destroy infrastructure via SSE streaming
- Log Trace: Real-time cloud log verification
- Simulator: Download IoT simulator packages
"""
import json
import logging
import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin import TwinCreate, TwinUpdate, TwinResponse
from src.schemas.management_contracts import (
    DeploymentHistoryResponse,
    DeploymentOutputsResponse,
    DeploymentStatusResponse,
    MessageResponse,
    OperationSessionResponse,
    RedeployReadinessResponse,
)
from src.repositories.twin_repository import TwinRepository
from src.services.configuration_validation_service import ConfigurationValidationService
from src.services.deployment_orchestrator import DeploymentOrchestrator
from src.services.errors import (
    ConfigurationValidationFailed,
    ExternalServiceError,
    ExternalServiceUnavailable,
)
from src.services.secret_redaction import redact_secret_like_text
from src.services.twin_export_service import TwinExportService
from src.services.twin_lifecycle_service import TwinLifecycleService, TwinReadService
from src.services.service_errors import ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError
from src.api.routes.error_models import ERROR_RESPONSES

logger = logging.getLogger(__name__)

# Test mode: production endpoints delegate to mock implementations
TEST_MODE = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"

router = APIRouter(prefix="/twins", tags=["twins"])


def _deployment_orchestrator(db: Session) -> DeploymentOrchestrator:
    """Build the deployment workflow orchestrator for this request."""
    test_deploy_stream_runner = None
    test_destroy_stream_runner = None
    if TEST_MODE:
        from src.api.routes.test_endpoints import _run_test_deploy_stream, _run_test_destroy_stream

        test_deploy_stream_runner = _run_test_deploy_stream
        test_destroy_stream_runner = _run_test_destroy_stream

    return DeploymentOrchestrator.from_session(
        db,
        test_deploy_stream_runner=test_deploy_stream_runner,
        test_destroy_stream_runner=test_destroy_stream_runner,
    )


def _twin_export_service(db: Session) -> TwinExportService:
    """Build the redacted twin export service for this request."""
    return TwinExportService(db=db, twin_repository=TwinRepository(db))


def _twin_read_service(db: Session) -> TwinReadService:
    """Build the read-side twin service for this request."""
    return TwinReadService(twin_repository=TwinRepository(db))


def _twin_lifecycle_service(db: Session) -> TwinLifecycleService:
    """Build the write-side twin lifecycle service for this request."""
    return TwinLifecycleService(db=db, twin_repository=TwinRepository(db))


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing route-level HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, DownstreamServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.public_detail) from exc
    raise exc

@router.get(
    "/", 
    response_model=List[TwinResponse],
    operation_id="listDigitalTwins",
    summary="List all digital twins for current user",
    description=(
        "**Purpose:** Retrieve all Digital Twins owned by the authenticated user.\n\n"
        "**When to call:** Dashboard load, twin list view, or any UI needing twin overview.\n\n"
        "**Response:** Array of TwinResponse objects excluding INACTIVE (soft-deleted) twins.\n\n"
        "**Fields per twin:** id, name, state, created_at, deployed_at, destroyed_at."
    ),
    responses={
        401: ERROR_RESPONSES[401],
    }
)
async def list_twins(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all twins for current user."""
    return _twin_read_service(db).list_twins(current_user.id)

@router.post(
    "/", 
    response_model=TwinResponse,
    operation_id="createDigitalTwin",
    summary="Create a new digital twin",
    description=(
        "**Purpose:** Create a new Digital Twin in DRAFT state.\n\n"
        "**When to call:** User clicks 'Create New Twin' or 'Add' button.\n\n"
        "**Request body:** `{name: string}` - Must be unique (case-insensitive) for this user.\n\n"
        "**Response:** Created twin with auto-generated UUID, state=DRAFT, timestamps.\n\n"
        "**Error 409:** Name already in use by another active twin."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        409: {"description": "Twin with this name already exists"},
    }
)
async def create_twin(
    twin: TwinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new digital twin."""
    try:
        return _twin_lifecycle_service(db).create_twin(twin.name, current_user.id)
    except ConflictError as exc:
        _raise_service_http_error(exc)

@router.get(
    "/{twin_id}", 
    response_model=TwinResponse,
    operation_id="getDigitalTwin",
    summary="Get a specific digital twin by ID",
    description=(
        "**Purpose:** Retrieve complete details for a single Digital Twin.\n\n"
        "**When to call:** Loading twin detail/edit screen, wizard navigation.\n\n"
        "**Response fields:** id, name, state, all timestamps, related configs via lazy load.\n\n"
        "**Error 404:** Twin not found or belongs to different user."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific twin."""
    try:
        return _twin_read_service(db).get_twin(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)

@router.put(
    "/{twin_id}", 
    response_model=TwinResponse,
    operation_id="updateDigitalTwin",
    summary="Update a digital twin",
    description=(
        "**Purpose:** Update twin name and/or state.\n\n"
        "**When to call:** Rename twin, or transition state (draft→configured).\n\n"
        "**Request body:**\n"
        "- `name`: New unique name (blocked for DEPLOYED/DEPLOYING/DESTROYING twins)\n"
        "- `state`: New state (validated transitions only)\n\n"
        "**State transitions:**\n"
        "- To 'configured': Triggers distributed validation (Optimizer + Deployer APIs)\n"
        "- Other transitions: Local state machine rules apply\n\n"
        "**Error 409:** New name already in use."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: {"description": "Twin with this name already exists"},
    }
)
async def update_twin(
    twin_id: str,
    update: TwinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a twin."""
    try:
        return await _twin_lifecycle_service(db).update_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            name=update.name,
            state=update.state,
            configured_validator=_validate_configured_transition,
        )
    except (ConflictError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


async def _validate_configured_transition(twin: DigitalTwin, db: Session):
    """
    Orchestrates distributed validation before allowing 'configured' state.
    
    Validates:
    - Step 1: Twin name, credentials (local)
    - Step 2: Optimizer params/result (calls Optimizer API)
    - Step 3: Deployer config files (calls Deployer API)
    
    Raises HTTPException(400) with structured errors if validation fails.
    """
    try:
        await ConfigurationValidationService().validate_configured_transition(twin)
    except ConfigurationValidationFailed as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_FAILED",
                "message": exc.message,
                "errors": exc.errors,
            },
        ) from exc

@router.delete(
    "/{twin_id}",
    response_model=MessageResponse,
    operation_id="deleteDigitalTwin",
    summary="Soft-delete a digital twin",
    description=(
        "**Purpose:** Mark a twin as inactive (soft delete).\n\n"
        "**When to call:** User confirms delete in UI.\n\n"
        "**Behavior:**\n"
        "- Sets state to INACTIVE (hidden from list queries)\n"
        "- Renames to '_deleted_{id}_{name}' to free unique constraint\n"
        "- Cleans up uploaded GLB scene files\n\n"
        "**Note:** Does NOT destroy cloud infrastructure. Call /destroy first for deployed twins."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def delete_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft delete a twin (set to inactive). Also cleans up GLB files."""
    try:
        return _twin_lifecycle_service(db).delete_twin(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


# ============================================================
# Deployment Cooldown Check
# ============================================================


@router.get(
    "/{twin_id}/can-redeploy",
    response_model=RedeployReadinessResponse,
    operation_id="checkRedeploymentCooldown",
    summary="Check if twin can be redeployed",
    description=(
        "**Purpose:** Check if redeployment is allowed after destroy (GCP Firestore cooldown).\n\n"
        "**When to call:** Before showing 'Deploy' button for a DESTROYED twin.\n\n"
        "**Why needed:** GCP Firestore has a 5-minute cooldown after database deletion.\n\n"
        "**Response fields:**\n"
        "- `ready`: Boolean - true if cooldown elapsed\n"
        "- `remaining_seconds`: Seconds until ready (0 if ready)\n\n"
        "**Note:** Returns `ready: true` for twins not using GCP Firestore."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Deployer API unavailable"},
    }
)
async def can_redeploy(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if twin can be redeployed (GCP Firestore 5-min cooldown elapsed).
    
    Proxies to Deployer API's /infrastructure/cooldown-check endpoint.
    Zero cloud costs - pure calculation.
    """
    try:
        return await _deployment_orchestrator(db).can_redeploy(twin_id, current_user.id)
    except (EntityNotFoundError, DownstreamServiceError) as exc:
        _raise_service_http_error(exc)


# ============================================================
# Deployment Operations
# ============================================================

@router.post(
    "/{twin_id}/deploy",
    response_model=OperationSessionResponse,
    operation_id="deployDigitalTwin",
    summary="Deploy twin infrastructure to cloud providers",
    description=(
        "**Purpose:** Start infrastructure deployment to selected cloud providers.\n\n"
        "**When to call:** User clicks 'Deploy' button in Step 4.\n\n"
        "**Prerequisites:**\n"
        "- Twin must be in CONFIGURED, DESTROYED, or ERROR state\n"
        "- All credentials validated\n"
        "- Optimizer calculation complete (cheapest_path set)\n\n"
        "**Response fields:**\n"
        "- `session_id`: UUID for this deployment session\n"
        "- `sse_url`: Connect to `/sse/deploy/{session_id}` for real-time logs\n\n"
        "**Side effects:** Sets twin state to DEPLOYING, creates Deployment record."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: {"description": "Deployment already in progress"},
    }
)
async def deploy_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deploy a twin's infrastructure to cloud providers.
    
    Prerequisites:
    - Twin must be in 'configured', 'destroyed', or 'error' state
    - All configurations must be saved
    
    Returns:
    - deployment_id: unique deployment session ID
    - sse_url: URL for SSE streaming of logs
    """
    try:
        return await _deployment_orchestrator(db).deploy_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.post(
    "/{twin_id}/destroy",
    response_model=OperationSessionResponse,
    operation_id="destroyDigitalTwinInfrastructure",
    summary="Destroy twin's deployed cloud infrastructure",
    description=(
        "**Purpose:** Tear down all deployed cloud infrastructure for this twin.\n\n"
        "**When to call:** User clicks 'Destroy Infrastructure' button.\n\n"
        "**Prerequisites:** Twin must be in DEPLOYED or ERROR state.\n\n"
        "**Response fields:**\n"
        "- `session_id`: UUID for this destroy session\n"
        "- `sse_url`: Connect to `/sse/deploy/{session_id}` for real-time logs\n\n"
        "**Side effects:**\n"
        "- Sets twin state to DESTROYING\n"
        "- Runs `terraform destroy` via Deployer\n"
        "- On success: state → DESTROYED, destroyed_at timestamp set"
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: {"description": "Destroy operation already in progress"},
    }
)
async def destroy_twin_infrastructure(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Destroy a twin's deployed infrastructure.
    
    Prerequisites:
    - Twin must be in 'deployed' or 'error' state
    
    Returns:
    - sse_url: URL for SSE streaming of logs
    """
    try:
        return await _deployment_orchestrator(db).destroy_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/deployment-status",
    response_model=DeploymentStatusResponse,
    operation_id="getDigitalTwinDeploymentStatus",
    summary="Get current deployment status",
    description=(
        "**Purpose:** Get deployment state and timestamps for polling fallback.\n\n"
        "**When to call:** When SSE is unavailable or as periodic health check.\n\n"
        "**Response fields:**\n"
        "- `state`: Current TwinState (DEPLOYING, DEPLOYED, etc.)\n"
        "- `last_error`: Error message if state is ERROR\n"
        "- `deployed_at`: ISO timestamp of last successful deploy\n"
        "- `destroyed_at`: ISO timestamp of last destroy\n\n"
        "**Note:** Prefer SSE streaming for real-time updates during operations."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_deployment_status(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current deployment status and recent logs.
    
    Used for polling fallback when SSE is unavailable.
    """
    from src.api.routes.sse import get_active_sessions_for_twin

    try:
        return await _deployment_orchestrator(db).get_status(
            twin_id=twin_id,
            user_id=current_user.id,
            active_session_provider=get_active_sessions_for_twin,
        )
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)

@router.get(
    "/{twin_id}/outputs",
    response_model=DeploymentOutputsResponse,
    operation_id="getDigitalTwinTerraformOutputs",
    summary="Get Terraform outputs from most recent deployment",
    description=(
        "**Purpose:** Retrieve Terraform outputs from the last successful deployment.\n\n"
        "**When to call:** Step 4 after deployment complete, or page refresh to restore outputs.\n\n"
        "**Response fields:**\n"
        "- `outputs`: Object with provider-specific outputs (endpoints, ARNs, resource IDs)\n"
        "- `deployed_at`: ISO timestamp of the deployment\n\n"
        "**Use case:** Display IoT endpoint URLs, function ARNs, storage bucket names to user."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_deployment_outputs(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get terraform outputs from most recent successful deployment.
    
    Returns the outputs stored in the Deployment table for this twin.
    Used to display outputs after the terminal is closed or on page refresh.
    """
    try:
        return _deployment_orchestrator(db).get_outputs(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/deployments",
    response_model=DeploymentHistoryResponse,
    operation_id="getDigitalTwinDeploymentHistory",
    summary="Get deployment history for a twin",
    description=(
        "**Purpose:** Retrieve historical deployment records for audit and troubleshooting.\n\n"
        "**When to call:** Deployment history view, debugging failed deployments.\n\n"
        "**Query params:** `limit` (1-50, default 10)\n\n"
        "**Response:** Array of deployment records with:\n"
        "- id, session_id, operation_type (deploy/destroy/test)\n"
        "- status (pending/running/success/failed)\n"
        "- started_at, completed_at, error_message"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_deployment_history(
    twin_id: str,
    limit: int = Query(10, ge=1, le=50, description="Max number of deployments to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get deployment history for a twin.
    
    Returns a list of historical deployments ordered by most recent first.
    """
    try:
        return _deployment_orchestrator(db).get_history(twin_id, current_user.id, limit)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)



# ============================================================
# Log Trace Endpoints (Proxy to Deployer API)
# ============================================================

@router.post(
    "/{twin_id}/log-trace/start",
    operation_id="startLogTrace",
    summary="Start a log trace with test IoT message",
    description=(
        "**Purpose:** Send a test IoT message and track it through the deployed infrastructure.\n\n"
        "**When to call:** User clicks 'Send Test IoT Message' button in Step 4.\n\n"
        "**Prerequisites:** Twin must be in DEPLOYED state.\n\n"
        "**Response fields:**\n"
        "- `trace_id`: UUID embedded in the test message for tracking\n"
        "- `providers`: List of cloud providers that will be queried (aws, azure, gcp)\n\n"
        "**Next step:** Connect to SSE endpoint `/log-trace/stream/{trace_id}` to see logs."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        429: {"description": "Rate limited"},
        503: {"description": "Deployer API unavailable"},
    }
)
async def start_log_trace(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start a log trace by sending a test IoT message with a unique trace_id.
    
    Proxies to Deployer API /logs/trace/start endpoint.
    Only works for deployed twins.
    
    Returns:
        trace_id: Unique identifier to track in logs
        providers: List of cloud providers that will be queried
    """
    twin = TwinRepository(db).get_with_configs_for_user(twin_id, current_user.id)
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Must be deployed to trace logs
    if twin.state != TwinState.DEPLOYED:
        raise HTTPException(
            status_code=400,
            detail=f"Twin must be deployed to trace logs (current state: {twin.state})"
        )
    
    # TEST MODE: delegate to mock log trace
    if TEST_MODE:
        import asyncio
        import uuid
        from datetime import datetime, timezone
        from src.api.routes.sse import create_session
        from src.api.routes.test_endpoints import _run_test_log_trace_stream

        providers = ["aws"]  # default
        if twin.optimizer_config:
            oc = twin.optimizer_config
            unique = {p.lower() for p in filter(None, [
                oc.cheapest_l1, oc.cheapest_l2, oc.cheapest_l3_hot
            ])}
            if unique:
                providers = list(unique)

        trace_id = f"TRACE-{uuid.uuid4().hex[:8].upper()}"
        session_id = str(uuid.uuid4())
        await create_session(twin_id, session_id, operation_type="log_trace")
        asyncio.create_task(_run_test_log_trace_stream(
            session_id=session_id, twin_id=twin_id,
            trace_id=trace_id, providers=providers,
            duration=30, should_fail=False
        ))
        return {
            "trace_id": trace_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "l1_provider": providers[0],
            "providers": providers,
            "message": f"Test message sent to {providers[0]} IoT endpoint",
            "session_id": session_id,
            "sse_url": f"/sse/deploy/{session_id}"
        }
    
    # Reload twin with all configs (especially credentials for log querying)
    from src.services.deployment_service import prepare_project_for_deployment

    twin = TwinRepository(db).get_with_configs_for_user(twin_id, current_user.id)
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found during reload")
    
    # Prepare project in Deployer (ensures credentials are current for log queries)
    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare project for log trace: {str(e)}")
    
    try:
        return await DeployerClient().start_log_trace(resource_name)
    except ExternalServiceError as e:
        detail = redact_secret_like_text(e.public_detail)
        if e.upstream_status_code == 429:
            try:
                parsed = json.loads(detail)
                detail = parsed.get("detail", "Rate limited") if isinstance(parsed, dict) else "Rate limited"
            except json.JSONDecodeError:
                detail = "Rate limited"
        raise HTTPException(
            status_code=e.upstream_status_code or 502,
            detail=detail if e.upstream_status_code == 429 else f"Deployer API error: {detail}",
        ) from e
    except ExternalServiceUnavailable as e:
        raise HTTPException(status_code=503, detail="Deployer API unavailable") from e


@router.get(
    "/{twin_id}/log-trace/stream/{trace_id}",
    operation_id="streamLogTrace",
    summary="SSE endpoint for streaming log trace results",
    description=(
        "**Purpose:** Real-time SSE stream of log entries matching the trace_id.\n\n"
        "**When to call:** After `startLogTrace` returns, connect to this SSE endpoint.\n\n"
        "**SSE event types:**\n"
        "- `log`: Individual log entry {prefix, timestamp, message, layer, provider}\n"
        "- `error`: Error during trace {message}\n"
        "- `done`: Trace complete {summary with counts per provider/layer}\n\n"
        "**Timeout:** Stream closes after ~30s or when 'done' event is sent."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Deployer API unavailable"},
    }
)
async def stream_log_trace(
    twin_id: str,
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SSE endpoint for streaming log trace results.
    
    Proxies to Deployer API /logs/trace/stream/{trace_id} endpoint.
    
    Events:
    - "log": {prefix, timestamp, message, layer, provider}
    - "error": {message}
    - "done": {summary}
    """
    from starlette.responses import StreamingResponse
    
    twin = TwinRepository(db).get_with_configs_for_user(twin_id, current_user.id)
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Get resource name for Deployer API
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
    async def event_generator():
        try:
            async for line in DeployerClient().stream_log_trace(resource_name, trace_id):
                # SSE lines come pre-formatted, just pass through.
                if line:
                    yield line if line.endswith("\n") else f"{line}\n"
                else:
                    yield "\n"
        except (ExternalServiceError, ExternalServiceUnavailable) as e:
            safe_error = redact_secret_like_text(str(e))
            logger.error("Log trace stream error: %s", safe_error)
            yield "event: error\ndata: {\"message\": \"Deployer log trace stream failed\"}\n\n"
        except Exception as e:
            safe_error = redact_secret_like_text(str(e))
            logger.error("Log trace stream error: %s", safe_error)
            yield "event: error\ndata: {\"message\": \"Deployer log trace stream failed\"}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================
# Deployment Verification Endpoints
# ============================================================

@router.post(
    "/{twin_id}/verify/infrastructure",
    operation_id="verifyInfrastructure",
    summary="Run structured infrastructure health check",
    description=(
        "**Purpose:** Verify all deployed cloud resources across layers L0–L5.\n\n"
        "**When to call:** After deployment, to confirm all resources are healthy.\n\n"
        "**Prerequisites:** Twin must be in DEPLOYED state.\n\n"
        "**Response:** Structured JSON with pass/fail/skip per check and summary.\n\n"
        "**Duration:** 5-30 seconds (cloud SDK calls).\n"
        "**Cost:** None (read-only API calls)."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Deployer API unavailable"},
    }
)
async def verify_infrastructure(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run structured infrastructure verification.
    
    Proxies to Deployer API /infrastructure/verify endpoint.
    Only works for deployed twins.
    
    Returns:
        checks: List of {name, status, provider, detail, layer}
        summary: {pass_count, fail_count, skip_count, total, healthy}
    """
    try:
        return await _deployment_orchestrator(db).verify_infrastructure(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


# ============================================================
# Data Flow Verification
# ============================================================

@router.post(
    "/{twin_id}/verify/dataflow",
    operation_id="verifyDataFlow",
    summary="Verify end-to-end data flow through deployed pipeline",
    description=(
        "**Purpose:** Send a test IoT message and verify it propagates through the entire "
        "deployed pipeline (ingestion → processing → storage → digital twin → event flow).\n\n"
        "**When to call:** After infrastructure verification passes.\n\n"
        "**Prerequisites:** Twin must be in DEPLOYED state.\n\n"
        "**Request body:** `{payload: {iotDeviceId: ..., ...}}` — test IoT payload.\n\n"
        "**Response:** `{session_id, sse_url}` — connect to SSE for real-time results.\n\n"
        "**Duration:** 1-15 minutes depending on cold starts."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Deployer API unavailable"},
    }
)
async def verify_dataflow(
    twin_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify data flow through deployed pipeline via SSE.
    
    Sends payload to Deployer which orchestrates 4-phase verification:
    1. Send IoT message
    2. Poll hot-reader for data propagation
    3. Check digital twin update (TwinMaker/ADT)
    4. Verify event flow via cloud logs
    
    Returns session_id and sse_url for SSE streaming.
    """
    try:
        return await _deployment_orchestrator(db).start_dataflow_verification(
            twin_id=twin_id,
            user_id=current_user.id,
            body=body,
            test_mode=TEST_MODE,
        )
    except (DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


# ============================================================
# IoT Simulator Download
# ============================================================

@router.get(
    "/{twin_id}/simulator/download",
    operation_id="downloadIoTSimulator",
    summary="Download IoT simulator package for L1 provider",
    description=(
        "**Purpose:** Download a ready-to-run IoT device simulator package.\n\n"
        "**When to call:** User clicks 'Download Simulator' button in Step 4.\n\n"
        "**Prerequisites:**\n"
        "- Twin must be in DEPLOYED state\n"
        "- Optimizer calculation complete (cheapest_l1 set)\n\n"
        "**Response:** ZIP file containing:\n"
        "- Provider-specific simulator code (Python)\n"
        "- Pre-configured credentials and endpoints\n"
        "- requirements.txt and run instructions\n\n"
        "**Filename:** `simulator_{twin_name}_{l1_provider}.zip`"
    ),
    tags=["twins"],
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        502: {"description": "Failed to connect to Deployer"},
    }
)
async def download_simulator(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download IoT simulator package for L1 provider.
    
    Extracts L1 from OptimizerConfiguration.cheapest_path and proxies to
    Deployer API /projects/{name}/simulator/{provider}/download.
    """
    try:
        archive = await _deployment_orchestrator(db).download_simulator(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)

    return StreamingResponse(
        archive.content,
        media_type=archive.media_type,
        headers={"Content-Disposition": f"attachment; filename={archive.filename}"}
    )


@router.get(
    "/{twin_id}/export",
    operation_id="exportTwinConfiguration",
    summary="Export twin configuration as ZIP",
    description=(
        "**Purpose:** Downloads the twin configuration as a redacted ZIP file.\n\n"
        "**Use case:** Debugging, backup, or manual deployment verification.\n\n"
        "**Contents:** config.json, config_providers.json, config_credentials.json (redacted), "
        "state machine, hierarchy, user functions, scene assets, and simulator payloads."
    ),
    responses={
        200: {"description": "ZIP file", "content": {"application/zip": {}}},
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def export_twin_configuration(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export twin configuration as downloadable ZIP."""
    try:
        archive = _twin_export_service(db).export_twin(twin_id=twin_id, user_id=current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)

    return StreamingResponse(
        archive.content,
        media_type=archive.media_type,
        headers={"Content-Disposition": f'attachment; filename="{archive.filename}"'}
    )
