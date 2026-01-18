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

