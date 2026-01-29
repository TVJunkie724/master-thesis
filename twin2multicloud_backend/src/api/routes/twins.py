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

router = APIRouter(prefix="/twins", tags=["twins"])

@router.get("/", response_model=List[TwinResponse])
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

@router.post("/", response_model=TwinResponse)
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

@router.get("/{twin_id}", response_model=TwinResponse)
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

@router.put("/{twin_id}", response_model=TwinResponse)
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

@router.delete("/{twin_id}")
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
    db.commit()
    return {"message": "Twin deleted"}


# ============================================================
# Deployment Cooldown Check
# ============================================================


@router.get("/{twin_id}/can-redeploy")
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

@router.post("/{twin_id}/deploy")
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
    asyncio.create_task(_run_real_deploy_stream(
        session_id=session_id,
        twin_id=twin_id,
        resource_name=resource_name,
        provider=provider
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


@router.post("/{twin_id}/destroy")
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
    asyncio.create_task(_run_real_destroy_stream(
        session_id=session_id,
        twin_id=twin_id,
        resource_name=resource_name,
        provider=provider
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


@router.get("/{twin_id}/deployment-status")
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

@router.get("/{twin_id}/outputs")
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


@router.get("/{twin_id}/deployments")
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
# Test Deployment (UI Testing Only)
# ============================================================

TEST_ENDPOINTS_ENABLED = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"


@router.post("/{twin_id}/test-deploy")
async def test_deploy_twin(
    twin_id: str,
    duration: int = Query(30, ge=5, le=120, description="Simulated duration in seconds"),
    should_fail: bool = Query(False, description="Simulate failure at end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test deployment for UI testing - simulates realistic deployment with SSE logs.
    
    Requires ENABLE_TEST_ENDPOINTS=true environment variable.
    No real cloud resources are created.
    
    Returns session_id for SSE connection to stream logs in real-time.
    
    Args:
        duration: How long the simulated deployment takes (5-120 seconds)
        should_fail: If true, simulate a deployment failure
    """
    if not TEST_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    
    from datetime import datetime
    import asyncio
    import uuid
    from src.api.routes.sse import create_session, get_active_sessions_for_twin
    
    # Validate twin exists
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Check for concurrent deployment
    active_sessions = await get_active_sessions_for_twin(twin_id)
    if active_sessions:
        raise HTTPException(
            status_code=409,
            detail="Deployment already in progress for this twin"
        )
    
    # Update state to deploying
    twin.state = TwinState.DEPLOYING
    twin.last_error = None
    db.commit()
    
    # Create SSE session
    session_id = str(uuid.uuid4())
    session = await create_session(twin_id, session_id, operation_type="test")
    
    # Spawn background task for streaming logs
    asyncio.create_task(_run_test_deploy_stream(
        session_id=session_id,
        twin_id=twin_id,
        twin_name=twin.name,
        duration=duration,
        should_fail=should_fail
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


@router.post("/{twin_id}/test-destroy")
async def test_destroy_twin(
    twin_id: str,
    duration: int = Query(20, ge=5, le=60, description="Simulated duration in seconds"),
    should_fail: bool = Query(False, description="Simulate failure at end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test destroy for UI testing - simulates realistic destruction with SSE logs.
    
    Requires ENABLE_TEST_ENDPOINTS=true environment variable.
    Returns session_id for SSE connection to stream logs in real-time.
    """
    if not TEST_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    
    from datetime import datetime
    import asyncio
    import uuid
    from src.api.routes.sse import create_session, get_active_sessions_for_twin
    
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Check for concurrent operation
    active_sessions = await get_active_sessions_for_twin(twin_id)
    if active_sessions:
        raise HTTPException(
            status_code=409,
            detail="Operation already in progress for this twin"
        )
    
    twin.state = TwinState.DESTROYING
    twin.last_error = None
    db.commit()
    
    # Create SSE session
    session_id = str(uuid.uuid4())
    session = await create_session(twin_id, session_id, operation_type="destroy")
    
    # Spawn background task for streaming logs
    asyncio.create_task(_run_test_destroy_stream(
        session_id=session_id,
        twin_id=twin_id,
        twin_name=twin.name,
        duration=duration,
        should_fail=should_fail
    ))
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


@router.post("/{twin_id}/test-log-trace/start")
async def test_log_trace_start(
    twin_id: str,
    duration: int = Query(30, ge=5, le=90, description="Simulated duration in seconds"),
    should_fail: bool = Query(False, description="Simulate trace failure"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test log trace for UI testing - simulates realistic multi-cloud log streaming.
    
    Requires ENABLE_TEST_ENDPOINTS=true environment variable.
    No real cloud resources are queried.
    
    Returns session_id for SSE connection to stream mock logs in real-time.
    
    Args:
        duration: How long the simulated trace takes (5-90 seconds)
        should_fail: If true, simulate a trace failure
    """
    if not TEST_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    
    import uuid
    import asyncio
    from datetime import datetime, timezone
    from src.api.routes.sse import create_session
    
    # Validate twin exists
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Generate mock trace_id
    trace_id = f"TRACE-{uuid.uuid4().hex[:8].upper()}"
    
    # Get providers from deployer_config (dynamic)
    providers = ["aws"]  # Default fallback
    if twin.deployer_config and hasattr(twin.deployer_config, 'layer_providers'):
        layer_providers = twin.deployer_config.layer_providers or {}
        unique_providers = set()
        for layer in ['layer_1_provider', 'layer_2_provider', 'layer_3_hot_provider']:
            if layer_providers.get(layer):
                unique_providers.add(layer_providers[layer])
        if unique_providers:
            providers = list(unique_providers)
    
    # Create SSE session
    session_id = str(uuid.uuid4())
    session = await create_session(twin_id, session_id, operation_type="log_trace")
    
    # Spawn background task for streaming mock logs
    asyncio.create_task(_run_test_log_trace_stream(
        session_id=session_id,
        twin_id=twin_id,
        trace_id=trace_id,
        providers=providers,
        duration=duration,
        should_fail=should_fail
    ))
    
    return {
        "trace_id": trace_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "l1_provider": providers[0] if providers else "aws",
        "providers": providers,
        "message": f"Test message sent to {providers[0] if providers else 'aws'} IoT endpoint",
        "session_id": session_id,
        "sse_url": f"/sse/deploy/{session_id}"
    }


async def _run_test_log_trace_stream(
    session_id: str,
    twin_id: str,
    trace_id: str,
    providers: list,
    duration: int,
    should_fail: bool
):
    """
    Background task that simulates multi-cloud log streaming via SSE.
    Generates realistic log events based on configured providers.
    """
    import asyncio
    import json
    from datetime import datetime, timezone
    from src.api.routes.sse import get_session
    
    session = await get_session(session_id)
    if not session:
        return
    
    try:
        # Build log steps based on providers
        # Format: (fraction_of_duration, event_type, data_dict)
        steps = []
        
        # Provider-specific storage names
        storage_names = {"aws": "DynamoDB", "azure": "CosmosDB", "gcp": "Firestore"}
        
        # Primary provider (L1) logs
        primary = providers[0] if providers else "aws"
        storage_name = storage_names.get(primary, "Database")
        
        steps.extend([
            (0.02, "log", {"layer": "L1", "provider": primary, "function": "dispatcher",
             "message": f'{{"device_id":"test-sensor","trace_id":"{trace_id}"}}'}),
            (0.02, "log", {"layer": "L1", "provider": primary, "function": "dispatcher",
             "message": "Routing to L2 persister"}),
            (0.05, "log", {"layer": "L2", "provider": primary, "function": "persister",
             "message": "Processing payload for device: test-sensor"}),
            (0.05, "log", {"layer": "L2", "provider": primary, "function": "persister",
             "message": f"PutItem: pk=test-sensor, sk={datetime.now(timezone.utc).isoformat()}"}),
            (0.05, "log", {"layer": "L3", "provider": primary, "function": storage_name,
             "message": "Write succeeded, RCU: 1"}),
        ])
        
        # Secondary provider(s) - cross-cloud via L0 glue
        for idx, prov in enumerate(providers[1:], start=1):
            sec_storage = storage_names.get(prov, "Database")
            steps.extend([
                (0.08, "log", {"layer": "L0", "provider": prov, "function": "l0-ingestion",
                 "message": f"HTTP 200: Ingested from {primary.upper()}, trace_id={trace_id}"}),
                (0.05, "log", {"layer": "L2", "provider": prov, "function": "dispatcher",
                 "message": "Processing cross-cloud payload"}),
                (0.05, "log", {"layer": "L3", "provider": prov, "function": sec_storage,
                 "message": "Write succeeded"}),
            ])
        
        # Add heartbeat at midpoint
        steps.append((0.30, "heartbeat", {"elapsed_seconds": duration // 2}))
        
        # Calculate timing
        total_fraction = sum(s[0] for s in steps)
        log_count = 0
        
        for fraction, event_type, data in steps:
            await asyncio.sleep(duration * fraction / total_fraction)
            
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            if event_type == "log":
                log_count += 1
                # Log events use push_log with JSON data payload
                await session.push_log(json.dumps(data))
            else:
                # Non-log events (heartbeat, etc.) use push_event with proper SSE type
                await session.push_event(event_type, data)
        
        if should_fail:
            error_data = {
                "message": "Simulated trace failure: CloudWatch query timeout",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await session.push_event("error", error_data)
            session.on_complete(success=False, message="Trace failed")
            return
        
        # Done event - use push_event for proper SSE type
        done_data = {
            "message": "Trace complete",
            "log_count": log_count,
            "duration_seconds": duration
        }
        await session.push_event("done", done_data)
        session.on_complete(success=True, message="Trace complete")
        
    except Exception as e:
        session.on_complete(success=False, message=str(e))


# =============================================================================
# SSE Streaming Background Tasks
# =============================================================================

async def _run_test_deploy_stream(
    session_id: str,
    twin_id: str,
    twin_name: str,
    duration: int,
    should_fail: bool
):
    """
    Background task that simulates Terraform deployment and streams logs via SSE.
    Creates its own DB session to avoid session scoping issues.
    """
    import asyncio
    import random
    from datetime import datetime
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    
    session = await get_session(session_id)
    if not session:
        return
    
    # Create Deployment record at start
    from src.models.deployment import Deployment
    db = SessionLocal()
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="deploy",
        status="running"
    )
    db.add(deployment)
    db.commit()
    deployment_id = deployment.id
    db.close()
    
    def _get_mock_terraform_outputs(name: str) -> dict:
        """Generate comprehensive mock terraform outputs matching outputs.tf"""
        return {
            # Core
            "digital_twin_name": name,
            
            # AWS Setup
            "aws_resource_group_name": f"rg-{name}",
            "aws_account_id": "123456789012",
            "aws_region": "us-east-1",
            
            # AWS L0 Glue
            "aws_l0_ingestion_function_name": f"{name}-l0-ingestion",
            "aws_l0_ingestion_url": f"https://{name}-l0-ingestion.lambda-url.us-east-1.on.aws/",
            "aws_l0_hot_writer_url": f"https://{name}-l0-hot-writer.lambda-url.us-east-1.on.aws/",
            "aws_l0_hot_reader_url": f"https://{name}-l0-hot-reader.lambda-url.us-east-1.on.aws/",
            "aws_l0_cold_writer_function_name": f"{name}-l0-cold-writer",
            "aws_l0_cold_writer_url": f"https://{name}-l0-cold-writer.lambda-url.us-east-1.on.aws/",
            "aws_l0_archive_writer_function_name": f"{name}-l0-archive-writer",
            "aws_l0_archive_writer_url": f"https://{name}-l0-archive-writer.lambda-url.us-east-1.on.aws/",
            
            # AWS L1 IoT
            "aws_l1_dispatcher_function_name": f"{name}-l1-dispatcher",
            "aws_iot_topic_rule_name": f"{name}_telemetry_rule",
            "aws_iot_role_arn": f"arn:aws:iam::123456789012:role/{name}-iot-rule",
            "aws_l1_connector_function_name": f"{name}-l1-connector",
            "aws_iot_endpoint": f"a1b2c3d4e5f6g7.iot.us-east-1.amazonaws.com",
            
            # AWS L2 Compute
            "aws_l2_persister_function_name": f"{name}-l2-persister",
            "aws_l2_event_checker_function_name": f"{name}-l2-event-checker",
            "aws_l2_step_function_arn": f"arn:aws:states:us-east-1:123456789012:stateMachine:{name}-workflow",
            
            # AWS L3 Storage
            "aws_dynamodb_table_name": f"{name}-hot-storage",
            "aws_dynamodb_table_arn": f"arn:aws:dynamodb:us-east-1:123456789012:table/{name}-hot-storage",
            "aws_l3_hot_reader_function_name": f"{name}-l3-hot-reader",
            "aws_l3_hot_reader_url": f"https://{name}-l3-hot-reader.lambda-url.us-east-1.on.aws/",
            "aws_s3_cold_bucket": f"{name}-cold-storage-abc123",
            "aws_s3_archive_bucket": f"{name}-archive-storage-def456",
            
            # AWS L4 TwinMaker
            "aws_twinmaker_workspace_id": f"{name}-workspace",
            "aws_twinmaker_workspace_arn": f"arn:aws:iottwinmaker:us-east-1:123456789012:workspace/{name}-workspace",
            "aws_twinmaker_scene_id": f"{name}-scene",
            
            # AWS L5 Grafana
            "aws_grafana_workspace_id": "g-abc123def456",
            "aws_grafana_endpoint": "https://g-abc123def456.grafana-workspace.us-east-1.amazonaws.com",
            "aws_platform_user_email": "user@example.com",
            "aws_sso_available": True,
            "aws_platform_user_created": True,
            
            # Azure Setup
            "azure_resource_group_name": f"rg-{name}-eastus",
            "azure_resource_group_id": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-{name}-eastus",
            "azure_managed_identity_id": f"/subscriptions/.../userAssignedIdentities/{name}-identity",
            "azure_managed_identity_client_id": "11111111-1111-1111-1111-111111111111",
            "azure_storage_account_name": f"{name.replace('-', '')}storage",
            
            # Azure L0 Glue
            "azure_l0_function_app_name": f"{name}-l0-glue",
            "azure_l0_function_app_url": f"https://{name}-l0-glue.azurewebsites.net",
            
            # Azure L1 IoT
            "azure_iothub_name": f"{name}-iothub",
            "azure_iothub_hostname": f"{name}-iothub.azure-devices.net",
            "azure_l1_function_app_name": f"{name}-l1",
            
            # Azure L2 Compute
            "azure_l2_function_app_name": f"{name}-l2",
            "azure_user_functions_app_name": f"{name}-user",
            "azure_dispatcher_url": f"https://{name}-l2.azurewebsites.net/api/dispatcher",
            
            # Azure L3 Storage
            "azure_cosmos_account_name": f"{name}-cosmos",
            "azure_cosmos_endpoint": f"https://{name}-cosmos.documents.azure.com:443/",
            "azure_l3_function_app_name": f"{name}-l3",
            "azure_l3_hot_reader_url": f"https://{name}-l3.azurewebsites.net/api/hot-reader",
            "azure_archive_storage_account": f"{name.replace('-', '')}storage",
            
            # Azure L4 Digital Twins
            "azure_adt_instance_name": f"{name}-adt",
            "azure_adt_endpoint": f"https://{name}-adt.api.eus.digitaltwins.azure.net",
            "azure_3d_scenes_container_url": f"https://{name.replace('-', '')}storage.blob.core.windows.net/scenes",
            "azure_platform_user_created": False,
            
            # Azure L5 Grafana
            "azure_grafana_name": f"{name}-grafana",
            "azure_grafana_endpoint": f"https://{name}-grafana.eus.grafana.azure.com",
            
            # GCP Setup
            "gcp_project_id": f"{name}-project-abc123",
            "gcp_service_account_email": f"functions@{name}-project.iam.gserviceaccount.com",
            "gcp_function_source_bucket": f"{name}-function-source",
            
            # GCP L1 IoT
            "gcp_pubsub_telemetry_topic": f"projects/{name}-project/topics/telemetry",
            "gcp_pubsub_events_topic": f"projects/{name}-project/topics/events",
            "gcp_dispatcher_url": f"https://dispatcher-abc123-uc.a.run.app",
            "gcp_connector_url": f"https://connector-def456-uc.a.run.app",
            
            # GCP L2 Compute
            "gcp_processor_url": f"https://processor-ghi789-uc.a.run.app",
            "gcp_persister_url": f"https://persister-jkl012-uc.a.run.app",
            "gcp_event_checker_url": f"https://event-checker-mno345-uc.a.run.app",
            "gcp_user_functions_url": f"https://user-functions-pqr678-uc.a.run.app",
            "gcp_event_workflow_id": f"projects/{name}-project/locations/us-central1/workflows/event-workflow",
            
            # GCP L3 Storage
            "gcp_firestore_database": "(default)",
            "gcp_cold_bucket": f"{name}-cold-storage",
            "gcp_archive_bucket": f"{name}-archive-storage",
            "gcp_hot_reader_url": f"https://hot-reader-stu901-uc.a.run.app",
            
            # GCP L0 Glue
            "gcp_ingestion_url": f"https://ingestion-vwx234-uc.a.run.app",
            "gcp_hot_writer_url": f"https://hot-writer-yza567-uc.a.run.app",
            "gcp_cold_writer_url": f"https://cold-writer-bcd890-uc.a.run.app",
            "gcp_archive_writer_url": f"https://archive-writer-efg123-uc.a.run.app",
            
            # Cross-Cloud
            "inter_cloud_token": "mock-inter-cloud-token-xyz789",
        }
    
    try:
        # Define deployment steps with relative timing
        steps = [
            (0.02, "=" * 60),
            (0.02, "  TERRAFORM DEPLOYMENT - STARTING (TEST MODE)"),
            (0.02, "=" * 60),
            (0.03, ""),
            (0.04, f"[STEP 0/9] Validating cloud credentials for '{twin_name}'..."),
            (0.02, "  Configured clouds: aws, azure"),
            (0.02, "  ✓ AWS credentials validated"),
            (0.02, "  ✓ Azure credentials validated"),
            (0.03, ""),
            (0.02, "[STEP 0.5/9] Initializing cloud providers for SDK operations..."),
            (0.02, "  ✓ Providers initialized"),
            (0.03, ""),
            (0.02, "[STEP 1/9] Validating project structure..."),
            (0.02, "✓ Project validation passed"),
            (0.03, ""),
            (0.02, "[STEP 2/9] Building function packages..."),
            (0.03, "  Building dispatcher package..."),
            (0.03, "  Building persister package..."),
            (0.02, "✓ All packages built"),
            (0.03, ""),
            (0.02, "[STEP 3/9] Generating tfvars.json..."),
            (0.02, f"✓ Generated: /app/upload/{twin_name}/terraform/generated.tfvars.json"),
            (0.03, ""),
            (0.02, "[STEP 4/9] Terraform init..."),
            (0.03, "Initializing provider plugins..."),
            (0.03, "- Finding hashicorp/aws versions matching ~> 5.0..."),
            (0.03, "- Installing hashicorp/aws v5.31.0..."),
            (0.02, "✓ Terraform initialized"),
            (0.03, ""),
            (0.02, "[STEP 5/9] Terraform apply..."),
            (0.04, f"aws_iot_thing.{twin_name}_thing: Creating..."),
            (0.05, f"aws_dynamodb_table.{twin_name}_hot_storage: Creating..."),
            (0.03, f"aws_iot_thing.{twin_name}_thing: Creation complete after 2s"),
            (0.05, f"aws_dynamodb_table.{twin_name}_hot_storage: Creation complete after 8s"),
            (0.04, f"aws_lambda_function.{twin_name}_dispatcher: Creating..."),
            (0.05, f"aws_lambda_function.{twin_name}_dispatcher: Creation complete after 12s"),
            (0.02, ""),
            (0.02, "Apply complete! Resources: 15 added, 0 changed, 0 destroyed."),
            (0.02, "✓ Terraform outputs: ['aws_iot_endpoint', 'aws_dynamodb_table_name', 'aws_l1_dispatcher_function_name', ...]"),
            (0.03, ""),
            (0.02, "[STEP 6/9] Deploying Azure function code..."),
            (0.02, "  No Azure layers configured, skipping Kudu deployment"),
            (0.03, ""),
            (0.02, "[STEP 7/9] Running post-deployment operations..."),
            (0.03, "  Registering IoT devices..."),
            (0.02, "  ✓ 3 devices registered"),
            (0.03, ""),
        ]
        
        total_fraction = sum(s[0] for s in steps)
        for fraction, msg in steps:
            if msg:  # Skip empty strings for logging but keep delay
                print(msg, flush=True)  # Container logs
                await session.push_log(msg)  # SSE stream
            await asyncio.sleep(duration * fraction / total_fraction)
        
        if should_fail:
            error_msg = "Simulated deployment failure: Terraform apply failed with exit code 1"
            print(f"✗ {error_msg}", flush=True)
            await session.push_log(f"✗ {error_msg}", level="error")
            
            # Update twin state to failed
            db = SessionLocal()
            try:
                twin = db.query(DigitalTwin).get(twin_id)
                if twin:
                    twin.state = TwinState.ERROR
                    twin.last_error = error_msg
                    db.commit()
                
                # Update Deployment record with failure
                from src.models.deployment import Deployment
                deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
                if deployment:
                    deployment.status = "failed"
                    deployment.error_message = error_msg
                    deployment.completed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
            
            session.on_complete(success=False, message=error_msg)
            return
        
        # Success path
        for msg in ["=" * 60, "  TERRAFORM DEPLOYMENT - COMPLETE", "=" * 60]:
            print(msg, flush=True)
            await session.push_log(msg)
        
        # Update twin state in database
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DEPLOYED
                twin.deployed_at = datetime.utcnow()
                db.commit()
            
            # Update Deployment record with success and outputs
            from src.models.deployment import Deployment
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.terraform_outputs = _get_mock_terraform_outputs(twin_name)
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(
            success=True,
            message="Deployment complete (test mode)",
            outputs=_get_mock_terraform_outputs(twin_name)
        )
        
    except Exception as e:
        # Error path: update twin state to failed
        try:
            db = SessionLocal()
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.ERROR
                twin.last_error = str(e)
                db.commit()
            
            # Update Deployment record with failure
            from src.models.deployment import Deployment
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.utcnow()
                db.commit()
            db.close()
        except Exception:
            pass  # Best effort
        session.on_complete(success=False, message=str(e))


async def _run_test_destroy_stream(
    session_id: str,
    twin_id: str,
    twin_name: str,
    duration: int,
    should_fail: bool
):
    """
    Background task that simulates Terraform destruction and streams logs via SSE.
    Creates its own DB session to avoid session scoping issues.
    """
    import asyncio
    from datetime import datetime
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    
    session = await get_session(session_id)
    if not session:
        return
    
    # Create Deployment record at start
    from src.models.deployment import Deployment
    db = SessionLocal()
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="destroy",
        status="running"
    )
    db.add(deployment)
    db.commit()
    db.close()
    
    try:
        steps = [
            (0.05, "=" * 60),
            (0.05, "  TERRAFORM DESTROY - STARTING (TEST MODE)"),
            (0.05, "=" * 60),
            (0.08, ""),
            (0.08, "[STEP 1/2] Terraform destroy..."),
            (0.12, f"aws_lambda_function.{twin_name}_dispatcher: Destroying..."),
            (0.12, f"aws_lambda_function.{twin_name}_dispatcher: Destruction complete after 5s"),
            (0.08, f"aws_dynamodb_table.{twin_name}_hot_storage: Destroying..."),
            (0.12, f"aws_dynamodb_table.{twin_name}_hot_storage: Destruction complete after 10s"),
            (0.05, ""),
            (0.05, "Destroy complete! Resources: 15 destroyed."),
        ]
        
        total_fraction = sum(s[0] for s in steps)
        for fraction, msg in steps:
            if msg:
                print(msg, flush=True)  # Container logs
                await session.push_log(msg)  # SSE stream
            await asyncio.sleep(duration * fraction / total_fraction)
        
        if should_fail:
            error_msg = "Simulated destroy failure: Resource still in use"
            print(f"✗ {error_msg}", flush=True)
            await session.push_log(f"✗ {error_msg}", level="error")
            
            db = SessionLocal()
            try:
                twin = db.query(DigitalTwin).get(twin_id)
                if twin:
                    twin.state = TwinState.ERROR
                    twin.last_error = error_msg
                    db.commit()
                
                # Update Deployment record with failure
                from src.models.deployment import Deployment
                deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
                if deployment:
                    deployment.status = "failed"
                    deployment.error_message = error_msg
                    deployment.completed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
            
            session.on_complete(success=False, message=error_msg)
            return
        
        # Success path
        for msg in ["=" * 60, "  TERRAFORM DESTROY - COMPLETE", "=" * 60]:
            print(msg, flush=True)
            await session.push_log(msg)
        
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DESTROYED
                twin.destroyed_at = datetime.utcnow()
                db.commit()
            
            # Update Deployment record with success
            from src.models.deployment import Deployment
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(success=True, message="Destruction complete (test mode)")
        
    except Exception as e:
        try:
            db = SessionLocal()
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.ERROR
                twin.last_error = str(e)
                db.commit()
            
            # Update Deployment record with failure
            from src.models.deployment import Deployment
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.utcnow()
                db.commit()
            db.close()
        except Exception:
            pass
        session.on_complete(success=False, message=str(e))


# =============================================================================
# Real Deployment/Destroy Stream Functions
# =============================================================================

async def _run_real_deploy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str
):
    """
    Background task that subscribes to Deployer SSE and forwards logs.
    Updates Deployment record on completion.
    """
    from datetime import datetime
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    from src.models.deployment import Deployment
    
    session = await get_session(session_id)
    if not session:
        return
    
    # Create Deployment record at start
    db = SessionLocal()
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="deploy",
        status="running"
    )
    db.add(deployment)
    db.commit()
    db.close()
    
    terraform_outputs = {}
    
    try:
        # Subscribe to Deployer SSE with long timeouts
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/infrastructure/deploy/stream",
                params={"provider": provider, "project_name": resource_name}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        msg = line[6:]  # Remove "data: " prefix
                        print(msg, flush=True)  # Container logs
                        await session.push_log(msg)
                    elif line.startswith("event: complete"):
                        # Next line contains JSON
                        pass
                    elif line.startswith('{"success":'):
                        # Parse completion event
                        import json
                        try:
                            result = json.loads(line)
                            if result.get("success"):
                                terraform_outputs = result.get("outputs", {})
                        except json.JSONDecodeError:
                            pass
        
        # Success path
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DEPLOYED
                twin.deployed_at = datetime.utcnow()
                db.commit()
            
            # Update Deployment record
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.terraform_outputs = terraform_outputs
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(success=True, message="Deployment complete", outputs=terraform_outputs)
        
    except Exception as e:
        # Error path
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.ERROR
                twin.last_error = str(e)
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        await session.push_log(f"✗ Deployment error: {e}", level="error")
        session.on_complete(success=False, message=str(e))


async def _run_real_destroy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str
):
    """
    Background task that subscribes to Deployer destroy SSE and forwards logs.
    """
    from datetime import datetime
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    from src.models.deployment import Deployment
    
    session = await get_session(session_id)
    if not session:
        return
    
    # Create Deployment record at start
    db = SessionLocal()
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="destroy",
        status="running"
    )
    db.add(deployment)
    db.commit()
    db.close()
    
    try:
        # Subscribe to Deployer destroy SSE
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/infrastructure/destroy/stream",
                params={"provider": provider, "project_name": resource_name}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        msg = line[6:]
                        print(msg, flush=True)
                        await session.push_log(msg)
        
        # Success path
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DESTROYED
                twin.destroyed_at = datetime.utcnow()
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(success=True, message="Destruction complete")
        
    except Exception as e:
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.ERROR
                twin.last_error = str(e)
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        await session.push_log(f"✗ Destroy error: {e}", level="error")
        session.on_complete(success=False, message=str(e))


# =============================================================================
# Logs Query Endpoint
# =============================================================================

@router.get("/{twin_id}/logs")
async def get_deployment_logs(
    twin_id: str,
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    after_event_id: Optional[int] = Query(None, description="Return events after this ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get persisted deployment logs for a twin.
    
    Used for reconnection catchup when SSE session has expired.
    """
    from src.models import DeploymentLog
    
    # Verify twin ownership
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    # Build query
    query = db.query(DeploymentLog).filter(DeploymentLog.twin_id == twin_id)
    
    if session_id:
        query = query.filter(DeploymentLog.session_id == session_id)
    
    if after_event_id is not None:
        query = query.filter(DeploymentLog.event_id > after_event_id)
    
    logs = query.order_by(DeploymentLog.event_id.asc()).limit(limit).all()
    
    return {
        "twin_id": twin_id,
        "logs": [
            {
                "id": log.event_id,
                "session_id": log.session_id,
                "message": log.message,
                "level": log.level,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "operation_type": log.operation_type
            }
            for log in logs
        ]
    }



# =============================================================================
# Legacy Simulation Functions (kept for backward compatibility)
# =============================================================================

async def _simulate_deployment(name: str, duration: int, should_fail: bool, logger) -> list:
    """Print realistic terraform-style deployment logs. Returns collected logs."""
    import asyncio
    
    collected_logs = []
    
    # Define steps with relative timing (fractions that sum to ~1.0)
    steps = [
        (0.02, "=" * 60),
        (0.02, "  TERRAFORM DEPLOYMENT - STARTING (TEST MODE)"),
        (0.02, "=" * 60),
        (0.05, ""),
        (0.05, f"[STEP 0/9] Validating cloud credentials for '{name}'..."),
        (0.03, "  Configured clouds: aws, azure"),
        (0.02, "✓ Deploy complete!"),
    ]
    
    total_fraction = sum(s[0] for s in steps)
    for fraction, msg in steps:
        if msg:
            logger.info(msg)
            collected_logs.append(msg)
        await asyncio.sleep(duration * fraction / total_fraction)
    
    if should_fail:
        error_msg = "Simulated deployment failure: Terraform apply failed with exit code 1"
        collected_logs.append(f"✗ {error_msg}")
        raise Exception(error_msg)
    
    return collected_logs


async def _simulate_destroy(name: str, duration: int, should_fail: bool, logger) -> list:
    """Print realistic terraform-style destruction logs. Returns collected logs."""
    import asyncio
    
    collected_logs = []
    
    steps = [
        (0.05, "=" * 60),
        (0.05, "  TERRAFORM DESTROY - STARTING (TEST MODE)"),
        (0.05, "=" * 60),
        (0.10, ""),
        (0.10, "[STEP 1/2] Terraform destroy..."),
        (0.15, f"aws_lambda_function.{name}_dispatcher: Destroying..."),
        (0.15, f"aws_lambda_function.{name}_dispatcher: Destruction complete after 5s"),
        (0.10, f"aws_dynamodb_table.{name}_hot_storage: Destroying..."),
        (0.15, f"aws_dynamodb_table.{name}_hot_storage: Destruction complete after 10s"),
        (0.05, ""),
        (0.05, "Destroy complete! Resources: 15 destroyed."),
        (0.05, "=" * 60),
        (0.05, "  TERRAFORM DESTROY - COMPLETE"),
        (0.05, "=" * 60),
    ]
    
    total_fraction = sum(s[0] for s in steps)
    for fraction, msg in steps:
        if msg:
            logger.info(msg)
            print(msg, flush=True)
            collected_logs.append(msg)
        await asyncio.sleep(duration * fraction / total_fraction)
    
    if should_fail:
        error_msg = "Simulated destroy failure: Resource still in use"
        logger.error(f"✗ {error_msg}")
        print(f"✗ {error_msg}", flush=True)
        collected_logs.append(f"✗ {error_msg}")
        raise Exception(error_msg)
    
    return collected_logs


def _build_deploy_config(twin: DigitalTwin) -> dict:
    """
    Build the config.json payload from saved configurations.
    
    Combines:
    - OptimizerConfiguration (layer providers, parameters)
    - DeployerConfiguration (config files, user functions)
    """
    import json
    
    config = {
        "resource_name": twin.name.lower().replace(" ", "-"),
        "twin_id": twin.id,
    }
    
    # Add from deployer config
    if twin.deployer_config:
        dc = twin.deployer_config
        config["resource_name"] = dc.resource_name or config["resource_name"]
        
        # Parse JSON fields
        if dc.config_events_json:
            config["config_events"] = json.loads(dc.config_events_json)
        if dc.config_iot_devices_json:
            config["config_iot_devices"] = json.loads(dc.config_iot_devices_json)
        if dc.payloads_json:
            config["payloads"] = json.loads(dc.payloads_json)
        if dc.state_machine_content:
            config["state_machine"] = dc.state_machine_content
        if dc.hierarchy_json:
            config["hierarchy"] = json.loads(dc.hierarchy_json)
        if dc.scenes_3d_json:
            config["3d_scenes"] = json.loads(dc.scenes_3d_json)
        if dc.config_user_json:
            config["config_user"] = json.loads(dc.config_user_json)
        
        # User functions
        if dc.processor_contents:
            config["processors"] = json.loads(dc.processor_contents)
        if dc.event_feedback_content:
            config["event_feedback"] = dc.event_feedback_content
        if dc.event_action_contents:
            config["event_actions"] = json.loads(dc.event_action_contents)
    
    # Add from optimizer config
    if twin.optimizer_config:
        oc = twin.optimizer_config
        config["layers"] = {
            "l1": oc.layer_1_provider,
            "l2": oc.layer_2_provider,
            "l3_hot": oc.layer_3_hot_provider,
            "l3_cool": oc.layer_3_cool_provider,
            "l3_archive": oc.layer_3_archive_provider,
            "l4": oc.layer_4_provider,
            "l5": oc.layer_5_provider,
        }
        if oc.optimizer_result:
            config["optimizer_result"] = json.loads(oc.optimizer_result)
    
    return config


# ============================================================
# Log Trace Endpoints (Proxy to Deployer API)
# ============================================================

@router.post("/{twin_id}/log-trace/start")
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


@router.get("/{twin_id}/log-trace/stream/{trace_id}")
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

@router.get("/{twin_id}/simulator/download", tags=["twins"])
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


@router.get(
    "/{twin_id}/simulator/test-download",
    tags=["Twins"],
    summary="[TEST] Download mock IoT simulator package",
    responses={
        200: {"description": "Mock simulator zip package for UI testing"},
        404: {"description": "Twin not found"}
    }
)
async def test_download_simulator(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mock endpoint for UI testing - returns a sample simulator zip.
    
    Does NOT require real deployment or Deployer connectivity.
    Use when kUseTestDeploy = true in Flutter.
    """
    import io
    import json
    import zipfile
    from fastapi.responses import StreamingResponse
    from src.models.optimizer_config import OptimizerConfiguration
    
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).first()
    if not twin:
        raise HTTPException(404, "Twin not found")
    
    # Get L1 provider from optimizer config (or default to 'gcp')
    opt_config = db.query(OptimizerConfiguration).filter_by(twin_id=twin_id).first()
    l1_provider = opt_config.cheapest_l1.lower() if opt_config and opt_config.cheapest_l1 else "gcp"
    
    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name
    
    # Create mock zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # config.json
        config = {
            "project_id": "mock-project-id",
            "topic_name": f"projects/mock-project/topics/{resource_name}-telemetry",
            "device_id": "mock-device-1",
            "digital_twin_name": resource_name,
            "payload_path": "payloads.json",
            "service_account_key_path": "service_account.json"
        }
        zf.writestr("config.json", json.dumps(config, indent=2))
        
        # payloads.json
        payloads = [{"temperature": 25.5, "humidity": 60, "device_id": "mock-device-1"}]
        zf.writestr("payloads.json", json.dumps(payloads, indent=2))
        
        # README.md
        readme = f"""# IoT Device Simulator - {resource_name} ({l1_provider.upper()})

## [MOCK PACKAGE - FOR UI TESTING ONLY]

This is a mock simulator package generated for UI testing purposes.
In production, this package would contain the actual simulator code.

## Usage
```bash
pip install -r requirements.txt
python src/main.py --project {resource_name}
```
"""
        zf.writestr("README.md", readme)
        
        # requirements.txt
        zf.writestr("requirements.txt", "google-cloud-pubsub>=2.0.0\n")
        
        # src/main.py placeholder
        zf.writestr("src/main.py", "# Mock simulator main.py\nprint('Mock simulator')\n")
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=simulator_{resource_name}_{l1_provider}.zip"}
    )
