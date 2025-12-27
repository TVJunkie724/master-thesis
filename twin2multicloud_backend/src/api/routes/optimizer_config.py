from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from datetime import datetime, timezone
from typing import Optional

from src.models.database import get_db
from src.models.twin import DigitalTwin
from src.models.optimizer_config import OptimizerConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.optimizer_config import (
    OptimizerParamsUpdate, OptimizerResultUpdate, 
    OptimizerConfigResponse, CheapestPathResponse
)

router = APIRouter(prefix="/twins/{twin_id}/optimizer-config", tags=["optimizer-config"])


def parse_iso_safe(s: str) -> Optional[datetime]:
    """Safely parse ISO timestamp string."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def safe_json_loads(s: str) -> Optional[dict]:
    """Safely parse JSON string, returning None on error."""
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin


@router.get("/", response_model=OptimizerConfigResponse)
async def get_optimizer_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get optimizer config including params, result, and cheapest path."""
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.optimizer_config:
        config = OptimizerConfiguration(twin_id=twin_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        config = twin.optimizer_config
    
    return OptimizerConfigResponse(
        id=config.id,
        twin_id=config.twin_id,
        params=safe_json_loads(config.params),
        result=safe_json_loads(config.result_json),
        cheapest_path=CheapestPathResponse(
            l1=config.cheapest_l1,
            l2=config.cheapest_l2,
            l3_hot=config.cheapest_l3_hot,
            l3_cool=config.cheapest_l3_cool,
            l3_archive=config.cheapest_l3_archive,
            l4=config.cheapest_l4,
            l5=config.cheapest_l5,
        ) if config.cheapest_l1 else None,
        calculated_at=config.calculated_at,
        pricing_aws_updated_at=config.pricing_aws_updated_at,
        pricing_azure_updated_at=config.pricing_azure_updated_at,
        pricing_gcp_updated_at=config.pricing_gcp_updated_at,
        updated_at=config.updated_at or datetime.now(timezone.utc)
    )


@router.put("/params", response_model=OptimizerConfigResponse)
async def update_params(
    twin_id: str,
    update: OptimizerParamsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save calculation params (before Calculate is clicked)."""
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.optimizer_config or OptimizerConfiguration(twin_id=twin_id)
    
    if update.params:
        config.params = json.dumps(update.params)
    
    db.add(config)
    db.commit()
    db.refresh(config)
    return await get_optimizer_config(twin_id, db, current_user)


@router.put("/result", response_model=OptimizerConfigResponse)
async def save_result(
    twin_id: str,
    update: OptimizerResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save full calculation result with cheapest path and pricing snapshots."""
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.optimizer_config or OptimizerConfiguration(twin_id=twin_id)
    
    # Params
    config.params = json.dumps(update.params)
    
    # Result
    config.result_json = json.dumps(update.result)
    
    # Cheapest path (separate fields)
    cp = update.cheapest_path
    config.cheapest_l1 = cp.get("l1")
    config.cheapest_l2 = cp.get("l2")
    config.cheapest_l3_hot = cp.get("l3_hot")
    config.cheapest_l3_cool = cp.get("l3_cool")
    config.cheapest_l3_archive = cp.get("l3_archive")
    config.cheapest_l4 = cp.get("l4")
    config.cheapest_l5 = cp.get("l5")
    
    # Pricing snapshots
    snapshots = update.pricing_snapshots
    config.pricing_aws_snapshot = json.dumps(snapshots.get("aws")) if snapshots.get("aws") else None
    config.pricing_azure_snapshot = json.dumps(snapshots.get("azure")) if snapshots.get("azure") else None
    config.pricing_gcp_snapshot = json.dumps(snapshots.get("gcp")) if snapshots.get("gcp") else None
    
    # Pricing timestamps (safe parsing)
    ts = update.pricing_timestamps
    config.pricing_aws_updated_at = parse_iso_safe(ts.get("aws", ""))
    config.pricing_azure_updated_at = parse_iso_safe(ts.get("azure", ""))
    config.pricing_gcp_updated_at = parse_iso_safe(ts.get("gcp", ""))
    
    config.calculated_at = datetime.now(timezone.utc)
    
    db.add(config)
    db.commit()
    db.refresh(config)
    return await get_optimizer_config(twin_id, db, current_user)


@router.get("/cheapest-path")
async def get_cheapest_path(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get cheapest path only (for deployment logic)."""
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.optimizer_config
    if not config or not config.cheapest_l1:
        raise HTTPException(404, "No optimizer result found. Run calculation first.")
    
    return {
        "l1": config.cheapest_l1,
        "l2": config.cheapest_l2,
        "l3_hot": config.cheapest_l3_hot,
        "l3_cool": config.cheapest_l3_cool,
        "l3_archive": config.cheapest_l3_archive,
        "l4": config.cheapest_l4,
        "l5": config.cheapest_l5,
    }
