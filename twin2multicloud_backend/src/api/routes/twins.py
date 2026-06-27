"""Digital Twin CRUD and lifecycle API adapters."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.twin import DigitalTwin
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.management_contracts import MessageResponse
from src.schemas.twin import TwinCreate, TwinResponse, TwinUpdate
from src.services.configuration_validation_service import ConfigurationValidationService
from src.services.errors import ConfigurationValidationFailed
from src.services.service_errors import ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.twin_lifecycle_service import TwinLifecycleService, TwinReadService

router = APIRouter(prefix="/twins", tags=["twins"])


def _twin_read_service(db: Session) -> TwinReadService:
    """Build the read-side twin service for this request."""
    return TwinReadService(twin_repository=TwinRepository(db))


def _twin_lifecycle_service(db: Session) -> TwinLifecycleService:
    """Build the write-side twin lifecycle service for this request."""
    return TwinLifecycleService(db=db, twin_repository=TwinRepository(db))


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing route-level HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, DownstreamServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.public_detail) from exc
    raise exc


@router.get(
    "/",
    response_model=List[TwinResponse],
    operation_id="listDigitalTwins",
    responses={401: ERROR_RESPONSES[401]},
)
async def list_twins(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active twins for the current user."""
    return _twin_read_service(db).list_twins(current_user.id)


@router.post(
    "/",
    response_model=TwinResponse,
    operation_id="createDigitalTwin",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        409: {"description": "Twin with this name already exists"},
    },
)
async def create_twin(
    twin: TwinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new digital twin."""
    try:
        return _twin_lifecycle_service(db).create_twin(twin.name, current_user.id)
    except ConflictError as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}",
    response_model=TwinResponse,
    operation_id="getDigitalTwin",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def get_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one active twin owned by the current user."""
    try:
        return _twin_read_service(db).get_twin(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.put(
    "/{twin_id}",
    response_model=TwinResponse,
    operation_id="updateDigitalTwin",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: {"description": "Twin with this name already exists"},
    },
)
async def update_twin(
    twin_id: str,
    update: TwinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update twin name and/or lifecycle state."""
    try:
        return await _twin_lifecycle_service(db).update_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            name=update.name,
            state=update.state,
            configured_validator=_validate_configured_transition,
        )
    except (ConflictError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


async def _validate_configured_transition(twin: DigitalTwin, db: Session) -> None:
    """Run distributed validation before a twin can become CONFIGURED."""
    try:
        await ConfigurationValidationService().validate_configured_transition(twin)
    except ConfigurationValidationFailed as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_FAILED",
                "message": exc.message,
                "errors": exc.errors,
            },
        ) from exc


@router.delete(
    "/{twin_id}",
    response_model=MessageResponse,
    operation_id="deleteDigitalTwin",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def delete_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a twin and clean up its uploaded scene file."""
    try:
        return _twin_lifecycle_service(db).delete_twin(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)
