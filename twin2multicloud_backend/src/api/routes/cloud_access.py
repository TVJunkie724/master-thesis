from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.cloud_access import CloudAccessInventoryResponse
from src.services.cloud_access_inventory_service import CloudAccessInventoryService

router = APIRouter(prefix="/cloud-access", tags=["cloud-access"])


@router.get(
    "",
    response_model=CloudAccessInventoryResponse,
    operation_id="getCloudAccessInventory",
    summary="Get the current user's secret-free cloud access inventory",
    responses={401: ERROR_RESPONSES[401]},
)
async def get_cloud_access_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return CloudAccessInventoryService(db).build_inventory(current_user.id)
