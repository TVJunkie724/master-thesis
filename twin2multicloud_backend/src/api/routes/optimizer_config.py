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
from src.services.twin_helpers import get_user_twin
from src.api.routes.error_models import ERROR_RESPONSES

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



@router.get(
    "/",
    response_model=OptimizerConfigResponse,
    operation_id="getOptimizerConfig",
    summary="Get optimizer config for a twin",
    description=(
        "**Purpose:** Retrieve the full optimizer configuration including saved parameters, calculation results, and cheapest path.\n\n"
        "**When to call:** When loading Step 2 (Optimizer) screen to restore previous calculation state.\n\n"
        "**Response fields:**\n"
        "- `params`: The 26 calculation parameters last used\n"
        "- `result`: Full calculation result JSON (costs per provider/layer)\n"
        "- `cheapest_path`: Optimal provider per layer (l1, l2, l3_hot, l3_cool, l3_archive, l4, l5)\n"
        "- `pricing_*_snapshot`: Pricing data used at calculation time\n"
        "- `calculated_at`: Timestamp of last calculation\n\n"
        "**Note:** Creates empty config if none exists."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
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
        pricing_aws_snapshot=safe_json_loads(config.pricing_aws_snapshot) if hasattr(config, 'pricing_aws_snapshot') else None,
        pricing_azure_snapshot=safe_json_loads(config.pricing_azure_snapshot) if hasattr(config, 'pricing_azure_snapshot') else None,
        pricing_gcp_snapshot=safe_json_loads(config.pricing_gcp_snapshot) if hasattr(config, 'pricing_gcp_snapshot') else None,
        pricing_aws_updated_at=config.pricing_aws_updated_at,
        pricing_azure_updated_at=config.pricing_azure_updated_at,
        pricing_gcp_updated_at=config.pricing_gcp_updated_at,
        updated_at=config.updated_at or datetime.now(timezone.utc)
    )


@router.put(
    "/params",
    response_model=OptimizerConfigResponse,
    operation_id="updateOptimizerParams",
    summary="Save calculation params before Calculate is clicked",
    description=(
        "**Purpose:** Persist the 26 optimizer parameters without triggering calculation.\n\n"
        "**When to call:** When user changes any parameter in Step 2 (auto-save on blur/change).\n\n"
        "**Request body:**\n"
        "- `params`: Object containing all 26 calculation parameters (numberOfDevices, hotStorageDurationInMonths, etc.)\n\n"
        "**Behavior:** Saves params but does NOT run calculation. Call `calculateOptimalDistribution` separately."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
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


@router.put(
    "/result",
    response_model=OptimizerConfigResponse,
    operation_id="saveOptimizerResult",
    summary="Save full calculation result with cheapest path",
    description=(
        "**Purpose:** Persist the complete optimization result after `calculateOptimalDistribution` returns.\n\n"
        "**When to call:** Immediately after receiving successful response from `calculateOptimalDistribution`.\n\n"
        "**Request body:**\n"
        "- `params`: The parameters used for this calculation\n"
        "- `result`: Full calculation response (awsCosts, azureCosts, gcpCosts, combinationTables)\n"
        "- `cheapest_path`: Object with l1, l2, l3_hot, l3_cool, l3_archive, l4, l5 provider names\n"
        "- `pricing_snapshots`: {aws: {...}, azure: {...}, gcp: {...}} pricing data used\n"
        "- `pricing_timestamps`: {aws: ISO, azure: ISO, gcp: ISO} when pricing was fetched\n\n"
        "**Important:** This enables Step 3 (Deployer) by storing the cheapest_path used for deployment."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        422: ERROR_RESPONSES[422],
    }
)
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


@router.get(
    "/cheapest-path",
    operation_id="getCheapestPath",
    summary="Get cheapest path only for deployment logic",
    description=(
        "**Purpose:** Retrieve just the cheapest provider selection per layer - used by deployment logic.\n\n"
        "**When to call:** When preparing deployment to determine which cloud providers to deploy to.\n\n"
        "**Prerequisite:** Must have run `calculateOptimalDistribution` and saved via `saveOptimizerResult` first.\n\n"
        "**Response fields:**\n"
        "- `l1`: IoT layer provider (aws, azure, gcp)\n"
        "- `l2`: Orchestration layer provider\n"
        "- `l3_hot`, `l3_cool`, `l3_archive`: Storage layer providers\n"
        "- `l4`: Analytics layer provider\n"
        "- `l5`: Visualization layer provider\n\n"
        "**Error 404:** Returned if calculation has not been run yet."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
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
