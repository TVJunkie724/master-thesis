from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.cloud_connection import (
    CloudConnectionCreate,
    CloudConnectionResponse,
    CloudConnectionUpdate,
    CloudConnectionValidationResponse,
)
from src.services.cloud_connection_service import CloudConnectionService
from src.services.cloud_credential_validation_service import perform_dual_validation

router = APIRouter(prefix="/cloud-connections", tags=["cloud-connections"])


@router.get(
    "/",
    response_model=list[CloudConnectionResponse],
    operation_id="listCloudConnections",
    summary="List the current user's cloud connections",
    responses={401: ERROR_RESPONSES[401]},
)
async def list_cloud_connections(
    provider: str | None = Query(default=None, pattern="^(aws|azure|gcp)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connections = service.list_connections(current_user.id)
    if provider is None:
        return connections
    return [connection for connection in connections if connection.provider == provider]


@router.post(
    "/",
    response_model=CloudConnectionResponse,
    operation_id="createCloudConnection",
    summary="Create a user-scoped cloud connection",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
    },
)
async def create_cloud_connection(
    request: CloudConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    try:
        return service.create_connection(current_user.id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{connection_id}",
    response_model=CloudConnectionResponse,
    operation_id="getCloudConnection",
    summary="Get a cloud connection without exposing its secret payload",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    return service.to_response(connection, current_user.id)


@router.patch(
    "/{connection_id}",
    response_model=CloudConnectionResponse,
    operation_id="updateCloudConnection",
    summary="Update cloud connection metadata",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def update_cloud_connection(
    connection_id: str,
    request: CloudConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    return service.update_connection(connection, current_user.id, request)


@router.delete(
    "/{connection_id}",
    status_code=204,
    operation_id="deleteCloudConnection",
    summary="Delete a cloud connection owned by the current user",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def delete_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    service.delete_connection(connection)


@router.post(
    "/{connection_id}/validate",
    response_model=CloudConnectionValidationResponse,
    operation_id="validateCloudConnection",
    summary="Validate a stored cloud connection against Optimizer and Deployer",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def validate_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")

    result = await perform_dual_validation(
        connection.provider,
        service.build_optimizer_credentials(connection, current_user.id),
        service.build_deployer_credentials(connection, current_user.id),
    )
    service.record_validation_result(connection, result)
    return CloudConnectionValidationResponse(
        id=connection.id,
        provider=connection.provider,
        valid=result.get("valid", False),
        validation_status=connection.validation_status,
        message=connection.validation_message or "Validation complete",
        optimizer=result.get("optimizer"),
        deployer=result.get("deployer"),
    )
