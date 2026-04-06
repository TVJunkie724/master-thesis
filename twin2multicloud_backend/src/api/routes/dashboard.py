"""
Dashboard statistics endpoint.

Returns aggregated stats for the dashboard overview:
- Number of deployed twins
- Number of draft twins
- Estimated monthly cost (from deployed twins' optimizer results)
- Total active twins
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    """Dashboard statistics response."""
    deployed_count: int
    draft_count: int
    total_twins: int
    estimated_monthly_cost: float  # USD, from deployed twins' optimizer results


@router.get(
    "/stats",
    response_model=DashboardStats,
    operation_id="getDashboardStats",
    summary="Get aggregated dashboard statistics",
    description=(
        "**Purpose:** Retrieve overview statistics for the dashboard home screen.\n\n"
        "**When to call:** When loading the dashboard main page to populate summary cards.\n\n"
        "**Response fields:**\n"
        "- `deployed_count`: Number of twins currently in DEPLOYED state\n"
        "- `draft_count`: Number of twins in DRAFT state\n"
        "- `total_twins`: Total active twins (excludes INACTIVE)\n"
        "- `estimated_monthly_cost`: USD sum of costs from deployed twins' cheapest paths\n\n"
        "**Cost calculation:** Sums layer costs from each deployed twin's "
        "optimizer result that match their stored cheapest_path selection."
    ),
    responses={
        401: ERROR_RESPONSES[401],
    }
)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get aggregated dashboard statistics."""
    
    # Get all active twins for this user
    twins = db.query(DigitalTwin).filter(
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).all()
    
    total_twins = len(twins)
    deployed_count = sum(1 for t in twins if t.state == TwinState.DEPLOYED)
    draft_count = sum(1 for t in twins if t.state == TwinState.DRAFT)
    
    # Calculate estimated monthly cost from deployed twins' optimizer results
    estimated_cost = 0.0
    for twin in twins:
        if twin.state == TwinState.DEPLOYED and twin.optimizer_config:
            result_json = twin.optimizer_config.result_json
            if result_json:
                try:
                    result = json.loads(result_json)
                    # Use the engine's pre-computed totalCost (includes layer + transfer costs)
                    estimated_cost += result.get('totalCost', 0)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
    
    return DashboardStats(
        deployed_count=deployed_count,
        draft_count=draft_count,
        total_twins=total_twins,
        estimated_monthly_cost=round(estimated_cost, 2)
    )
