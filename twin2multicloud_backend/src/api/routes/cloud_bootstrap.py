from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.cloud_bootstrap import (
    CloudBootstrapImportRequest,
    CloudBootstrapImportResponse,
    CloudBootstrapPlanRequest,
    CloudBootstrapPlanResponse,
)
from src.services.cloud_bootstrap_service import CloudBootstrapService
from src.services.cloud_connection_service import CloudConnectionService

router = APIRouter(prefix="/cloud-bootstrap", tags=["cloud-bootstrap"])


@router.post(
    "/{provider}/plan",
    response_model=CloudBootstrapPlanResponse,
    operation_id="createCloudBootstrapPlan",
    summary="Create a safe manual provider bootstrap plan",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        422: ERROR_RESPONSES[422],
    },
)
async def create_cloud_bootstrap_plan(
    provider: str,
    request: CloudBootstrapPlanRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    try:
        return CloudBootstrapService().build_plan(provider, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/import",
    response_model=CloudBootstrapImportResponse,
    operation_id="importCloudBootstrapConnection",
    summary="Import generated bootstrap output as a CloudConnection",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        422: ERROR_RESPONSES[422],
    },
)
async def import_cloud_bootstrap_connection(
    request: CloudBootstrapImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    try:
        connection = service.create_connection(current_user.id, request.connection)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CloudBootstrapImportResponse(connection=connection)
