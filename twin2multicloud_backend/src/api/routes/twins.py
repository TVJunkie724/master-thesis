from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin import TwinCreate, TwinUpdate, TwinResponse

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
    """Soft delete a twin (set to inactive)."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    twin.state = TwinState.INACTIVE
    db.commit()
    return {"message": "Twin deleted"}
