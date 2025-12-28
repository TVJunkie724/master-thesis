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


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    """Dashboard statistics response."""
    deployed_count: int
    draft_count: int
    total_twins: int
    estimated_monthly_cost: float  # USD, from deployed twins' optimizer results


@router.get("/stats", response_model=DashboardStats)
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
                    # Sum the cheapest path costs
                    cheapest_path = result.get('cheapestPath', [])
                    for provider_costs_key in ['awsCosts', 'azureCosts', 'gcpCosts']:
                        costs = result.get(provider_costs_key, {})
                        for layer_key, layer_data in costs.items():
                            # Only count if this layer is in the cheapest path
                            provider = provider_costs_key.replace('Costs', '').upper()
                            path_key = f"{layer_key}_{provider}"
                            if path_key in cheapest_path:
                                estimated_cost += layer_data.get('cost', 0)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
    
    return DashboardStats(
        deployed_count=deployed_count,
        draft_count=draft_count,
        total_twins=total_twins,
        estimated_monthly_cost=round(estimated_cost, 2)
    )

