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
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin import TwinCreate, TwinUpdate, TwinResponse
from src.config import settings
from src.services.deployment_service import (
    run_real_deploy_stream,
    run_real_destroy_stream,
    build_deploy_config,
)
from src.repositories.deployment_repository import DeploymentRepository
from src.services.configuration_validation_service import ConfigurationValidationService
from src.services.errors import ConfigurationValidationFailed, CredentialResolutionFailed
from src.api.routes.error_models import ERROR_RESPONSES

logger = logging.getLogger(__name__)

# Test mode: production endpoints delegate to mock implementations
TEST_MODE = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"

router = APIRouter(prefix="/twins", tags=["twins"])

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
    twins = db.query(DigitalTwin).filter(
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).all()
    return twins

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
    # Check for duplicate name (case-insensitive, excluding inactive twins)
    existing = db.query(DigitalTwin).filter(
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.name.ilike(twin.name),
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if existing:
        raise HTTPException(
            status_code=409, 
            detail=f"A twin with the name '{twin.name}' already exists"
        )
    
    new_twin = DigitalTwin(
        name=twin.name,
        user_id=current_user.id,
        state=TwinState.DRAFT
    )
    db.add(new_twin)
    db.commit()
    db.refresh(new_twin)
    return new_twin

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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin

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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Block NAME changes for deployed/deploying/destroying twins (state changes allowed for deploy/destroy flow)
    BLOCKED_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}
    if update.name is not None and update.name != twin.name and twin.state in BLOCKED_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot rename twin in '{twin.state.value}' state"
        )
    
    if update.name is not None and update.name != twin.name:
        # Check for duplicate name (case-insensitive, excluding this twin and inactive twins)
        existing = db.query(DigitalTwin).filter(
            DigitalTwin.user_id == current_user.id,
            DigitalTwin.name.ilike(update.name),
            DigitalTwin.id != twin_id,
            DigitalTwin.state != TwinState.INACTIVE
        ).first()
        if existing:
            raise HTTPException(
                status_code=409, 
                detail=f"A twin with the name '{update.name}' already exists"
            )
        twin.name = update.name
    
    # Validate before allowing state transition to CONFIGURED
    if update.state is not None and update.state == TwinState.CONFIGURED:
        await _validate_configured_transition(twin, db)
    
    if update.state is not None:
        twin.state = update.state
        
    db.commit()
    db.refresh(twin)
    return twin


OPTIMIZER_API_URL = os.getenv("OPTIMIZER_URL", "http://twin2clouds:8000")
DEPLOYER_API_URL = os.getenv("DEPLOYER_URL", "http://3cloud-deployer:8000")


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
                "errors": exc.errors
            }
        )


def _credential_resolution_exception(exc: CredentialResolutionFailed) -> HTTPException:
    """Map credential resolution failures to one stable API error shape."""
    return HTTPException(
        status_code=400,
        detail={
            "code": "CREDENTIAL_RESOLUTION_FAILED",
            "message": exc.message,
            "errors": exc.errors,
        },
    )


def _deployment_summary(deployment) -> dict | None:
    if not deployment:
        return None
    return {
        "id": deployment.id,
        "session_id": deployment.session_id,
        "operation_id": deployment.operation_id,
        "operation_type": deployment.operation_type,
        "status": deployment.status,
        "error_code": deployment.error_code,
        "error_message": deployment.error_message,
        "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
        "completed_at": deployment.completed_at.isoformat() if deployment.completed_at else None,
    }


@router.delete(
    "/{twin_id}",
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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Cleanup GLB file if exists
    glb_path = Path(settings.UPLOAD_DIR) / twin_id / "scene.glb"
    glb_path.unlink(missing_ok=True)
    try:
        (Path(settings.UPLOAD_DIR) / twin_id).rmdir()
    except OSError:
        pass  # Directory not empty or doesn't exist
    
    twin.state = TwinState.INACTIVE
    # Rename to free up the name for reuse (unique constraint)
    twin.name = f"_deleted_{twin_id}_{twin.name}"
    db.commit()
    return {"message": "Twin deleted"}


# ============================================================
# Deployment Cooldown Check
# ============================================================


@router.get(
    "/{twin_id}/can-redeploy",
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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Get deployer config to check if GCP Firestore is used
    uses_gcp_firestore = False
    if twin.deployer_config and twin.deployer_config.layer_3_hot_provider:
        uses_gcp_firestore = twin.deployer_config.layer_3_hot_provider == "google"
    
    # If no destroyed_at or not using GCP Firestore, always ready
    if not twin.destroyed_at or not uses_gcp_firestore:
        return {"ready": True, "remaining_seconds": 0}
    
    # Proxy to Deployer API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DEPLOYER_API_URL}/infrastructure/cooldown-check",
                params={
                    "destroyed_at": twin.destroyed_at.isoformat() + "Z",
                    "uses_gcp_firestore": str(uses_gcp_firestore).lower()
                },
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Deployer API error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Deployer API unavailable")


# ============================================================
# Deployment Operations
# ============================================================

@router.post(
    "/{twin_id}/deploy",
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
    from datetime import datetime
    
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Validate state allows deployment
    allowed_states = [TwinState.CONFIGURED, TwinState.DESTROYED, TwinState.ERROR]
    if twin.state not in allowed_states:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot deploy twin in '{twin.state}' state. Must be configured, destroyed, or error."
        )
    
    # Check for concurrent deployment
    if twin.state == TwinState.DEPLOYING:
        raise HTTPException(
            status_code=409,
            detail="Deployment already in progress"
        )
    
    # Update state to deploying (NOTE: resource_name and provider now extracted after prepare step)
    twin.state = TwinState.DEPLOYING
    twin.last_error = None
    db.commit()
    
    # Create SSE session and spawn background task
    import asyncio
    import uuid
    from src.api.routes.sse import create_session, get_active_sessions_for_twin
    from src.services.deployment_service import prepare_project_for_deployment
    from sqlalchemy.orm import joinedload
    
    # Check for concurrent deployment
    active_sessions = await get_active_sessions_for_twin(twin_id)
    if active_sessions:
        twin.state = TwinState.CONFIGURED  # Rollback
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Deployment already in progress for this twin"
        )
    
    # TEST MODE: delegate to mock deployment
    if TEST_MODE:
        from src.api.routes.test_endpoints import _run_test_deploy_stream
        session_id = str(uuid.uuid4())
        await create_session(twin_id, session_id, operation_type="test")
        asyncio.create_task(_run_test_deploy_stream(
            session_id=session_id, twin_id=twin_id,
            twin_name=twin.name, duration=30, should_fail=False
        ))
        return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}
    
    # Reload twin with ALL related configurations for ZIP building
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),  # Contains cloud credentials
    ).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
    ).first()
    
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found during reload")
    
    # Prepare project in Deployer (build ZIP and upload) before streaming
    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except CredentialResolutionFailed as e:
        logger.warning(
            "Credential resolution failed while preparing deploy for twin '%s' (%s): %s",
            twin.name,
            twin_id,
            e.errors,
        )
        twin.state = TwinState.CONFIGURED
        db.commit()
        raise _credential_resolution_exception(e) from e
    except HTTPException as e:
        logger.error(f"Deploy preparation failed for twin '{twin.name}' ({twin_id}): {e.detail}")
        twin.state = TwinState.CONFIGURED  # Rollback state on failure
        db.commit()
        raise e
    except Exception as e:
        logger.error(f"Deploy preparation failed for twin '{twin.name}' ({twin_id}): {e}", exc_info=True)
        twin.state = TwinState.CONFIGURED  # Rollback state on failure
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to prepare project: {str(e)}")
    
    # Determine provider - use L1 provider as the main deployment target
    provider = "aws"  # default
    if twin.optimizer_config and twin.optimizer_config.cheapest_l1:
        provider = twin.optimizer_config.cheapest_l1.lower()
    
    # Create SSE session
    session_id = str(uuid.uuid4())
    await create_session(twin_id, session_id, operation_type="deploy")
    
    # Spawn background task for streaming logs from Deployer
    asyncio.create_task(run_real_deploy_stream(
        session_id=session_id,
        twin_id=twin_id,
        resource_name=resource_name,
        provider=provider
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


@router.post(
    "/{twin_id}/destroy",
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
    from datetime import datetime
    
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Validate state allows destruction
    allowed_states = [TwinState.DEPLOYED, TwinState.ERROR]
    if twin.state not in allowed_states:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot destroy twin in '{twin.state}' state. Must be deployed or error."
        )
    
    # Check for concurrent operation
    if twin.state == TwinState.DESTROYING:
        raise HTTPException(
            status_code=409,
            detail="Destroy operation already in progress"
        )
    
    # Update state to destroying
    twin.state = TwinState.DESTROYING
    twin.last_error = None
    db.commit()
    
    # Create SSE session and spawn background task
    import asyncio
    import uuid
    from src.api.routes.sse import create_session, get_active_sessions_for_twin
    from src.services.deployment_service import prepare_project_for_deployment, get_resource_name
    from sqlalchemy.orm import joinedload
    
    # Check for concurrent operation
    active_sessions = await get_active_sessions_for_twin(twin_id)
    if active_sessions:
        twin.state = TwinState.DEPLOYED  # Rollback
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Destroy operation already in progress for this twin"
        )
    
    # TEST MODE: delegate to mock destruction
    if TEST_MODE:
        from src.api.routes.test_endpoints import _run_test_destroy_stream
        session_id = str(uuid.uuid4())
        await create_session(twin_id, session_id, operation_type="destroy")
        asyncio.create_task(_run_test_destroy_stream(
            session_id=session_id, twin_id=twin_id,
            twin_name=twin.name, duration=20, should_fail=False
        ))
        return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}
    
    # Reload twin with ALL related configurations (for project preparation)
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),
    ).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
    ).first()
    
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found during reload")
    
    # Get resource name (DRY: use helper)
    resource_name = get_resource_name(twin)
    
    # Prepare project in Deployer (ensures terraform state is accessible)
    try:
        await prepare_project_for_deployment(twin, current_user.id)
    except CredentialResolutionFailed as e:
        logger.warning(
            "Credential resolution failed while preparing destroy for twin '%s' (%s): %s",
            twin.name,
            twin_id,
            e.errors,
        )
        twin.state = TwinState.DEPLOYED
        db.commit()
        raise _credential_resolution_exception(e) from e
    except Exception as e:
        # Log but don't fail - destroy should work even if project prep fails
        logger.warning(f"Project preparation failed during destroy: {e}")
    
    # Determine provider - use L1 provider as the main deployment target
    provider = "aws"  # default
    if twin.optimizer_config and twin.optimizer_config.cheapest_l1:
        provider = twin.optimizer_config.cheapest_l1.lower()
    
    # Create SSE session
    session_id = str(uuid.uuid4())
    await create_session(twin_id, session_id, operation_type="destroy")
    
    # Spawn background task
    asyncio.create_task(run_real_destroy_stream(
        session_id=session_id,
        twin_id=twin_id,
        resource_name=resource_name,
        provider=provider
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


@router.get(
    "/{twin_id}/deployment-status",
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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Check for active SSE session (for reconnection after navigation)
    from src.api.routes.sse import get_active_sessions_for_twin
    active_session = None
    if twin.state in (TwinState.DEPLOYING, TwinState.DESTROYING):
        sessions = await get_active_sessions_for_twin(twin_id)
        if sessions:
            s = sessions[0]
            active_session = {
                "session_id": s.session_id,
                "sse_url": f"/sse/deploy/{s.session_id}",
                "operation_type": s.operation_type,
            }

    latest_deployment = DeploymentRepository(db).get_latest_for_twin(twin_id)

    return {
        "state": twin.state,
        "last_error": twin.last_error,
        "deployed_at": twin.deployed_at.isoformat() if twin.deployed_at else None,
        "destroyed_at": twin.destroyed_at.isoformat() if twin.destroyed_at else None,
        "active_session": active_session,
        "latest_deployment": _deployment_summary(latest_deployment),
    }

@router.get(
    "/{twin_id}/outputs",
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
    from src.models.deployment import Deployment
    
    # Verify twin belongs to user
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Get most recent successful deployment
    deployment = db.query(Deployment).filter(
        Deployment.twin_id == twin_id,
        Deployment.status == "success",
        Deployment.operation_type.in_(["deploy", "test"])  # Both real and test deploys
    ).order_by(Deployment.completed_at.desc()).first()
    
    if not deployment:
        return {"outputs": None, "deployed_at": None}
    
    return {
        "outputs": deployment.terraform_outputs,
        "deployed_at": deployment.completed_at.isoformat() if deployment.completed_at else None
    }


@router.get(
    "/{twin_id}/deployments",
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
    # Verify twin belongs to user
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    deployments = DeploymentRepository(db).list_for_twin(twin_id, limit)
    
    return {
        "deployments": [
            {
                "id": d.id,
                "session_id": d.session_id,
                "operation_id": d.operation_id,
                "operation_type": d.operation_type,
                "status": d.status,
                "started_at": d.started_at.isoformat() if d.started_at else None,
                "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                "error_code": d.error_code,
                "error_message": d.error_message,
            }
            for d in deployments
        ]
    }



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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
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
    from sqlalchemy.orm import joinedload
    
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),  # Contains cloud credentials
    ).filter(DigitalTwin.id == twin_id).first()
    
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found during reload")
    
    # Prepare project in Deployer (ensures credentials are current for log queries)
    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except CredentialResolutionFailed as e:
        raise _credential_resolution_exception(e) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare project for log trace: {str(e)}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{DEPLOYER_API_URL}/logs/trace/start",
                params={"project_name": resource_name}
            )
            
            if response.status_code == 429:
                # Rate limited - pass through the message
                raise HTTPException(status_code=429, detail=response.json().get("detail", "Rate limited"))
            
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Deployer API error: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail="Deployer API unavailable")


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
    
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Get resource name for Deployer API
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "GET",
                    f"{DEPLOYER_API_URL}/logs/trace/stream/{trace_id}",
                    params={"project_name": resource_name}
                ) as response:
                    async for line in response.aiter_lines():
                        # SSE lines come pre-formatted, just pass through
                        # Only add newline if line doesn't end with one
                        if line:
                            if line.endswith('\n'):
                                yield line
                            else:
                                yield f"{line}\n"
                        else:
                            # Empty line is SSE event separator
                            yield "\n"
        except Exception as e:
            yield f"event: error\ndata: {{\"message\": \"Stream error: {str(e)}\"}}\n\n"
    
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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Must be deployed to verify infrastructure
    if twin.state != TwinState.DEPLOYED:
        raise HTTPException(
            status_code=400,
            detail=f"Twin must be deployed to verify infrastructure (current state: {twin.state})"
        )
    
    # TEST MODE: return mock verification data
    if TEST_MODE:
        return {
            "checks": [
                {"name": "L0 Setup resources", "status": "pass", "provider": "", "detail": "12 resources found", "layer": "L0"},
                {"name": "L0 Glue functions", "status": "pass", "provider": "", "detail": "cold-writer, hot-reader", "layer": "L0"},
                {"name": "IoT endpoint", "status": "pass", "provider": "AWS", "detail": "endpoint active", "layer": "L1"},
                {"name": "IoT devices registered", "status": "pass", "provider": "AWS", "detail": "2 device(s)", "layer": "L1"},
                {"name": "Functions deployed", "status": "pass", "provider": "AWS", "detail": "5 resources", "layer": "L2"},
                {"name": "Hot storage", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Cold storage", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Archive storage", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Hot→Cold mover", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Cold→Archive mover", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "TwinMaker workspace", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L4"},
                {"name": "TwinMaker entities", "status": "pass", "provider": "AWS", "detail": "2 entities created", "layer": "L4"},
                {"name": "ADT twins", "status": "skip", "provider": "", "detail": "L4 not Azure", "layer": "L4"},
                {"name": "Grafana workspace", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L5"},
            ],
            "summary": dict(pass_count=13, fail_count=0, skip_count=1, total=14, healthy=True)
        }
    
    # Reload twin with configs for credential sync
    from src.services.deployment_service import prepare_project_for_deployment
    from sqlalchemy.orm import joinedload
    
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),
    ).filter(DigitalTwin.id == twin_id).first()
    
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found during reload")
    
    # Prepare project in Deployer (ensures credentials are current)
    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except CredentialResolutionFailed as e:
        raise _credential_resolution_exception(e) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare project: {str(e)}")
    
    # Determine provider for Deployer API
    provider = "aws"
    if twin.optimizer_config and twin.optimizer_config.cheapest_l1:
        provider = twin.optimizer_config.cheapest_l1.lower()
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{DEPLOYER_API_URL}/infrastructure/verify",
                params={"project_name": resource_name, "provider": provider}
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Deployer API error: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Deployer API unavailable: {str(e)}")


# ============================================================
# Data Flow Verification
# ============================================================

async def _proxy_dataflow_sse(
    session_id: str,
    resource_name: str,
    payload: dict,
):
    """Background task that proxies Deployer data flow SSE to our session."""
    from src.api.routes.sse import get_session

    session = await get_session(session_id)
    if not session:
        return

    try:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/dataflow/verify",
                params={"project_name": resource_name},
                json={"payload": payload},
            ) as response:
                last_data = None
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        msg = line[6:]
                        last_data = msg
                        await session.push_log(msg)
                    elif line.startswith("event: done"):
                        # Next data line is the summary
                        pass

        # Parse done event to determine success
        verification_ok = True
        summary_msg = "Data flow verification complete"
        if last_data:
            try:
                summary = json.loads(last_data)
                fail_count = summary.get("fail_count", 0)
                verification_ok = fail_count == 0
                if not verification_ok:
                    failed_phase = summary.get("failed_phase", "unknown")
                    summary_msg = f"Verification failed at: {failed_phase}"
            except (json.JSONDecodeError, TypeError):
                pass
        session.on_complete(success=verification_ok, message=summary_msg)

    except Exception as e:
        await session.push_log(json.dumps({
            "timestamp": "",
            "message": f"✗ Verification error: {e}",
            "status": "fail",
        }))
        session.on_complete(success=False, message=str(e))


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
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    if twin.state != TwinState.DEPLOYED:
        raise HTTPException(
            status_code=400,
            detail=f"Twin must be deployed to verify data flow (current state: {twin.state})"
        )
    
    # Validate payload
    payload = body.get("payload", {})
    if not payload or "iotDeviceId" not in payload:
        raise HTTPException(
            status_code=400,
            detail="Request body must contain 'payload' with 'iotDeviceId' field"
        )
    
    # TEST MODE: return mock SSE session
    if TEST_MODE:
        session_id = str(uuid.uuid4())
        from src.api.routes.sse import create_session
        await create_session(twin_id, session_id, operation_type="verify_dataflow")
        return {
            "session_id": session_id,
            "sse_url": f"/sse/deploy/{session_id}",
        }
    
    # Reload twin with configs for credential sync
    from src.services.deployment_service import prepare_project_for_deployment
    from sqlalchemy.orm import joinedload
    
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),
    ).filter(DigitalTwin.id == twin_id).first()
    
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found during reload")
    
    # Prepare project (sync credentials)
    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except CredentialResolutionFailed as e:
        raise _credential_resolution_exception(e) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare project: {str(e)}")
    
    # Create SSE session
    import uuid, asyncio
    session_id = str(uuid.uuid4())
    from src.api.routes.sse import create_session
    await create_session(twin_id, session_id, operation_type="verify_dataflow")
    
    # Start background SSE proxy
    asyncio.create_task(_proxy_dataflow_sse(
        session_id=session_id,
        resource_name=resource_name,
        payload=payload,
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}",
    }


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
    import io
    from fastapi.responses import StreamingResponse
    from src.models.optimizer_config import OptimizerConfiguration
    
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(404, "Twin not found")
    
    if twin.state != TwinState.DEPLOYED:
        raise HTTPException(400, f"Simulator only available for deployed twins. Current: {twin.state.value}")
    
    # TEST MODE: delegate to mock simulator download
    if TEST_MODE:
        from src.api.routes.test_endpoints import test_download_simulator
        return await test_download_simulator(twin_id, db=db, current_user=current_user)
    
    # Reload twin with all configs for project preparation
    from src.services.deployment_service import prepare_project_for_deployment
    from sqlalchemy.orm import joinedload
    
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),
    ).filter(DigitalTwin.id == twin_id).first()
    
    if not twin:
        raise HTTPException(404, "Twin not found during reload")
    
    if not twin.optimizer_config or not twin.optimizer_config.cheapest_l1:
        raise HTTPException(404, "Optimization not configured. Complete Step 2 first.")
    
    l1_provider = twin.optimizer_config.cheapest_l1.lower()
    
    # Prepare project in Deployer (ensures simulator config is current)
    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except CredentialResolutionFailed as e:
        raise _credential_resolution_exception(e) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to prepare project for simulator download: {str(e)}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{DEPLOYER_API_URL}/projects/{resource_name}/simulator/{l1_provider}/download",
                timeout=60.0
            )
        except httpx.RequestError as e:
            raise HTTPException(502, f"Failed to connect to Deployer: {str(e)}")
        
        if resp.status_code == 404:
            raise HTTPException(404, "Simulator not available. Ensure L1 deployed.")
        elif resp.status_code != 200:
            raise HTTPException(resp.status_code, f"Deployer error: {resp.text}")
        
        return StreamingResponse(
            io.BytesIO(resp.content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=simulator_{resource_name}_{l1_provider}.zip"}
        )


@router.get(
    "/{twin_id}/export",
    operation_id="exportTwinConfiguration",
    summary="Export twin configuration as ZIP",
    description=(
        "**Purpose:** Downloads the twin configuration as a Deployer-compatible ZIP file.\n\n"
        "**Use case:** Debugging, backup, or manual deployment verification.\n\n"
        "**Contents:** config.json, config_providers.json, config_credentials.json (decrypted), "
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
    from src.services.deployment_service import build_project_zip
    from sqlalchemy.orm import joinedload
    from fastapi.responses import StreamingResponse
    
    twin = db.query(DigitalTwin).options(
        joinedload(DigitalTwin.deployer_config),
        joinedload(DigitalTwin.optimizer_config),
        joinedload(DigitalTwin.configuration),
    ).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
    ).first()
    
    if not twin:
        raise HTTPException(404, "Twin not found")
    
    # Reuse the same ZIP building logic
    zip_data = build_project_zip(twin, current_user.id)
    
    filename = f"{twin.name.lower().replace(' ', '-')}_config.zip"
    
    return StreamingResponse(
        zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
