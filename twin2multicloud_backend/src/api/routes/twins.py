"""Digital Twin Management API endpoints.

This module provides CRUD operations for Digital Twins, including deployment
and destroy operations, log tracing, and IoT simulator downloads.

**Key endpoints:**
- CRUD: Create, Read, Update, Delete twins
- Deployment: Deploy/Destroy infrastructure via SSE streaming
- Log Trace: Real-time cloud log verification
- Simulator: Download IoT simulator packages
"""
import os
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
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/twins", tags=["twins"])

@router.get(
    "/", 
    response_model=List[TwinResponse],
    operation_id="listDigitalTwins",
    summary="List all digital twins for current user",
    description="Returns all non-inactive twins belonging to the authenticated user.",
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
    description="Creates a twin in DRAFT state. Name must be unique per user.",
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
    description="Updates name and/or state. Name changes blocked for deployed twins.",
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
    import asyncio
    import json
    
    errors = []
    
    # === STEP 1: Local validation (Management API domain) ===
    if not twin.name or not twin.name.strip():
        errors.append({
            "step": 1, 
            "code": "EMPTY_NAME", 
            "field": "twin_name", 
            "message": "Twin name is required"
        })
    
    # Check at least one provider has credentials
    config = twin.configuration if twin.configuration else None
    has_creds = False
    if config:
        has_creds = any([
            config.aws_access_key_id,
            config.azure_subscription_id,
            config.gcp_project_id or config.gcp_billing_account
        ])
    if not has_creds:
        errors.append({
            "step": 1,
            "code": "MISSING_CREDENTIALS",
            "field": "credentials",
            "message": "At least one cloud provider credentials required"
        })
    
    # === STEP 2 & 3: Call Optimizer and Deployer APIs in parallel ===
    optimizer_config = twin.optimizer_config
    deployer_config = twin.deployer_config
    
    # Build request payloads
    optimizer_payload = {
        "params": json.loads(optimizer_config.params) if optimizer_config and optimizer_config.params else None,
        "result": json.loads(optimizer_config.result_json) if optimizer_config and optimizer_config.result_json else None
    }
    
    # Parse cheapest path from result for deployer context
    # Deployer expects dict format {L1: "aws", L2: "azure", ...}
    # Optimizer returns this as 'calculationResult', not 'cheapestPath' (which is an array)
    cheapest_path = {}
    if optimizer_payload["result"]:
        cheapest_path = optimizer_payload["result"].get("calculationResult", {})
    
    deployer_payload = {
        "deployer_digital_twin_name": deployer_config.deployer_digital_twin_name if deployer_config else None,
        "config_events": deployer_config.config_events_json if deployer_config else None,
        "config_iot_devices": deployer_config.config_iot_devices_json if deployer_config else None,
        "payloads": deployer_config.payloads_json if deployer_config else None,
        "processors": json.loads(deployer_config.processor_contents) if deployer_config and deployer_config.processor_contents else None,
        "event_feedback": deployer_config.event_feedback_content if deployer_config else None,
        "event_actions": json.loads(deployer_config.event_action_contents) if deployer_config and deployer_config.event_action_contents else None,
        "hierarchy": deployer_config.hierarchy_content if deployer_config else None,
        "scene_config": deployer_config.scene_config_content if deployer_config else None,
        "scene_glb_uploaded": deployer_config.scene_glb_uploaded if deployer_config else False,
        "state_machine": deployer_config.state_machine_content if deployer_config else None,
        "user_config": deployer_config.user_config_content if deployer_config else None,
        "optimizer_params": json.loads(optimizer_config.params) if optimizer_config and optimizer_config.params else None,
        "cheapest_path": cheapest_path
    }
    
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Call both APIs in parallel
        optimizer_task = client.post(
            f"{OPTIMIZER_API_URL}/validate/optimizer-config",
            json=optimizer_payload
        )
        deployer_task = client.post(
            f"{DEPLOYER_API_URL}/validate/deployer-complete",
            json=deployer_payload
        )
        
        results = await asyncio.gather(optimizer_task, deployer_task, return_exceptions=True)
        
        # Process Optimizer response
        opt_result = results[0]
        if isinstance(opt_result, Exception):
            errors.append({
                "step": 2,
                "code": "OPTIMIZER_UNAVAILABLE",
                "field": "optimizer",
                "message": f"Optimizer API error: {str(opt_result)}"
            })
        elif opt_result.status_code == 200:
            opt_data = opt_result.json()
            if not opt_data.get("valid"):
                for err in opt_data.get("errors", []):
                    errors.append({"step": 2, **err})
        else:
            errors.append({
                "step": 2,
                "code": "OPTIMIZER_ERROR",
                "field": "optimizer",
                "message": f"Optimizer validation failed: {opt_result.text}"
            })
        
        # Process Deployer response
        dep_result = results[1]
        if isinstance(dep_result, Exception):
            errors.append({
                "step": 3,
                "code": "DEPLOYER_UNAVAILABLE",
                "field": "deployer",
                "message": f"Deployer API error: {str(dep_result)}"
            })
        elif dep_result.status_code == 200:
            dep_data = dep_result.json()
            if not dep_data.get("valid"):
                for err in dep_data.get("errors", []):
                    errors.append({"step": 3, **err})
        else:
            errors.append({
                "step": 3,
                "code": "DEPLOYER_ERROR",
                "field": "deployer",
                "message": f"Deployer validation failed: {dep_result.text}"
            })
    
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_FAILED",
                "message": f"Cannot mark as configured: {len(errors)} validation errors",
                "errors": errors
            }
        )

@router.delete(
    "/{twin_id}",
    operation_id="deleteDigitalTwin",
    summary="Soft-delete a digital twin",
    description="Sets twin to INACTIVE state and cleans up GLB files.",
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
    description="Checks GCP Firestore 5-min cooldown. Zero cloud costs - pure calculation.",
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
    description="Starts async deployment via SSE streaming. Twin must be configured/destroyed/error state.",
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
    
    # Get resource name and provider from config
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
    # Determine provider - use L1 provider as the main deployment target
    provider = "aws"  # default
    if twin.optimizer_config and twin.optimizer_config.layer_1_provider:
        provider = twin.optimizer_config.layer_1_provider.lower()
    
    # Update state to deploying
    twin.state = TwinState.DEPLOYING
    twin.last_error = None
    db.commit()
    
    # Create SSE session and spawn background task
    import asyncio
    import uuid
    from src.api.routes.sse import create_session, get_active_sessions_for_twin
    
    # Check for concurrent deployment
    active_sessions = await get_active_sessions_for_twin(twin_id)
    if active_sessions:
        twin.state = TwinState.CONFIGURED  # Rollback
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Deployment already in progress for this twin"
        )
    
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
    description="Starts async destruction via SSE streaming. Twin must be deployed/error state.",
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
    
    # Get resource name from deployer config
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
    # Determine provider - use L1 provider as the main deployment target
    provider = "aws"  # default
    if twin.optimizer_config and twin.optimizer_config.layer_1_provider:
        provider = twin.optimizer_config.layer_1_provider.lower()
    
    # Update state to destroying
    twin.state = TwinState.DESTROYING
    twin.last_error = None
    db.commit()
    
    # Create SSE session and spawn background task
    import asyncio
    import uuid
    from src.api.routes.sse import create_session, get_active_sessions_for_twin
    
    # Check for concurrent operation
    active_sessions = await get_active_sessions_for_twin(twin_id)
    if active_sessions:
        twin.state = TwinState.DEPLOYED  # Rollback
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Destroy operation already in progress for this twin"
        )
    
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
    description="Returns state, timestamps, and last error. Used for polling fallback when SSE unavailable.",
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
    
    return {
        "state": twin.state,
        "last_error": twin.last_error,
        "deployed_at": twin.deployed_at.isoformat() if twin.deployed_at else None,
        "destroyed_at": twin.destroyed_at.isoformat() if twin.destroyed_at else None,
    }

@router.get(
    "/{twin_id}/outputs",
    operation_id="getDigitalTwinTerraformOutputs",
    summary="Get Terraform outputs from most recent deployment",
    description="Returns outputs stored in Deployment table. Used after terminal closed or page refresh.",
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
    description="Returns list of historical deployments ordered by most recent first.",
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
    from src.models.deployment import Deployment
    
    # Verify twin belongs to user
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    deployments = db.query(Deployment).filter(
        Deployment.twin_id == twin_id
    ).order_by(Deployment.started_at.desc()).limit(limit).all()
    
    return {
        "deployments": [
            {
                "id": d.id,
                "session_id": d.session_id,
                "operation_type": d.operation_type,
                "status": d.status,
                "started_at": d.started_at.isoformat() if d.started_at else None,
                "completed_at": d.completed_at.isoformat() if d.completed_at else None,
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
    description="Sends test message with unique trace_id to verify cloud log flow. Only for deployed twins.",
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
    
    # Get resource name for Deployer API
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
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
    description="Proxies to Deployer API. Events: log (prefix, timestamp, message), error, done.",
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
# IoT Simulator Download
# ============================================================

@router.get(
    "/{twin_id}/simulator/download",
    operation_id="downloadIoTSimulator",
    summary="Download IoT simulator package for L1 provider",
    description="Extracts L1 from OptimizerConfiguration and proxies to Deployer API. Only for deployed twins.",
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
    
    opt_config = db.query(OptimizerConfiguration).filter_by(twin_id=twin_id).first()
    if not opt_config or not opt_config.cheapest_l1:
        raise HTTPException(404, "Optimization not configured. Complete Step 2 first.")
    
    l1_provider = opt_config.cheapest_l1.lower()
    
    # Get resource name from deployer config (same pattern as deploy/destroy)
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
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

