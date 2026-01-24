import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
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
        
    if update.state is not None:
        twin.state = update.state
        
    db.commit()
    db.refresh(twin)
    return twin

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

DEPLOYER_API_URL = os.getenv("DEPLOYER_API_URL", "http://3cloud-deployer:5004")


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
    if twin.deployer_config and twin.deployer_config.resource_name:
        resource_name = twin.deployer_config.resource_name
    
    # Determine provider - use L1 provider as the main deployment target
    provider = "aws"  # default
    if twin.optimizer_config and twin.optimizer_config.layer_1_provider:
        provider = twin.optimizer_config.layer_1_provider.lower()
    
    # Update state to deploying
    twin.state = TwinState.DEPLOYING
    twin.last_error = None
    db.commit()
    
    # Call Deployer API to start deployment
    # NOTE: Deployer expects project context to already exist with config files
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DEPLOYER_API_URL}/infrastructure/deploy",
                params={
                    "provider": provider,
                    "project_name": resource_name,
                },
                timeout=300.0  # Deployment can take several minutes
            )
            response.raise_for_status()
            result = response.json()
            
            # Update deployed_at timestamp on success
            from datetime import datetime
            twin.state = TwinState.DEPLOYED
            twin.deployed_at = datetime.utcnow()
            db.commit()
            
            return {
                "deployment_id": twin_id,
                "status": "deployed",
                "message": result.get("message", "Deployment successful")
            }
    except httpx.HTTPStatusError as e:
        # Rollback state on failure
        twin.state = TwinState.ERROR
        twin.last_error = f"Deployment failed: {e.response.text}"
        db.commit()
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        twin.state = TwinState.ERROR
        twin.last_error = f"Deployer API unavailable: {str(e)}"
        db.commit()
        raise HTTPException(status_code=503, detail="Deployer API unavailable")


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
    if twin.deployer_config and twin.deployer_config.resource_name:
        resource_name = twin.deployer_config.resource_name
    
    # Determine provider - use L1 provider as the main deployment target
    provider = "aws"  # default
    if twin.optimizer_config and twin.optimizer_config.layer_1_provider:
        provider = twin.optimizer_config.layer_1_provider.lower()
    
    # Update state to destroying
    twin.state = TwinState.DESTROYING
    twin.last_error = None
    db.commit()
    
    # Call Deployer API to start destruction
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DEPLOYER_API_URL}/infrastructure/destroy",
                params={
                    "provider": provider,
                    "project_name": resource_name,
                },
                timeout=300.0  # Destruction can take several minutes
            )
            response.raise_for_status()
            result = response.json()
            
            # Update destroyed_at timestamp on success
            twin.state = TwinState.DESTROYED
            twin.destroyed_at = datetime.utcnow()
            db.commit()
            
            return {
                "status": "destroyed",
                "message": result.get("message", "Destruction successful")
            }
    except httpx.HTTPStatusError as e:
        twin.state = TwinState.ERROR
        twin.last_error = f"Destroy failed: {e.response.text}"
        db.commit()
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        twin.state = TwinState.ERROR
        twin.last_error = f"Deployer API unavailable: {str(e)}"
        db.commit()
        raise HTTPException(status_code=503, detail="Deployer API unavailable")


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
