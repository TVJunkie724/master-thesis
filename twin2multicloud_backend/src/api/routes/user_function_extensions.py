"""Bounded user-function validation and current Twin source routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.upload_limits import UploadLimitExceeded, read_upload_bounded
from src.models.database import get_db
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.user_function_extension import (
    ExtensionSlotListResponse,
    TwinUserFunctionListResponse,
    TwinUserFunctionResponse,
    UserFunctionValidationResponse,
)
from src.services.user_function_extension_service import (
    ExtensionContractError,
    UserFunctionExtensionService,
)

router = APIRouter(tags=["twin-user-functions"])
MAX_METADATA_BYTES = 64 * 1024
MAX_SOURCE_ARCHIVE_BYTES = 10 * 1024 * 1024


def _service(db: Session) -> UserFunctionExtensionService:
    return UserFunctionExtensionService(db, TwinRepository(db))


def _raise_contract_error(exc: ExtensionContractError) -> None:
    status = {
        "EXTENSION_BINDING_UNRESOLVED": 409,
        "EXTENSION_ARCHIVE_UNSAFE": 400,
        "EXTENSION_SECRET_MATERIAL_DETECTED": 400,
    }.get(exc.code, 422)
    raise HTTPException(status_code=status, detail=exc.as_dict()) from exc


async def _read_part(upload: UploadFile, *, limit: int, field: str) -> bytes:
    try:
        payload = await read_upload_bounded(upload, max_bytes=limit)
    except UploadLimitExceeded as exc:
        raise HTTPException(
            status_code=413,
            detail={
                "error_code": "EXTENSION_ARCHIVE_UNSAFE",
                "field": field,
                "message": "The multipart field exceeds its size limit.",
            },
        ) from exc
    if not payload:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "EXTENSION_SCHEMA_INVALID",
                "field": field,
                "message": "The multipart field is empty.",
            },
        )
    return payload


async def _read_upload(
    metadata: UploadFile,
    source_archive: UploadFile,
) -> tuple[bytes, bytes]:
    return (
        await _read_part(metadata, limit=MAX_METADATA_BYTES, field="metadata"),
        await _read_part(
            source_archive,
            limit=MAX_SOURCE_ARCHIVE_BYTES,
            field="source_archive",
        ),
    )


@router.get(
    "/architecture/extension-slots",
    response_model=ExtensionSlotListResponse,
    operation_id="listExtensionSlots",
    summary="List the fixed reviewed user-function slots",
)
async def list_extension_slots(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ExtensionSlotListResponse:
    return _service(db).list_slots()


@router.post(
    "/twins/{twin_id}/user-functions/{slot_id}/validate",
    response_model=UserFunctionValidationResponse,
    operation_id="validateTwinUserFunction",
    summary="Validate bounded Twin function source without persisting it",
)
async def validate_twin_user_function(
    twin_id: str,
    slot_id: str,
    metadata: UploadFile = File(..., description="UTF-8 JSON function metadata"),
    source_archive: UploadFile = File(..., description="Bounded source ZIP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserFunctionValidationResponse:
    metadata_bytes, archive_bytes = await _read_upload(metadata, source_archive)
    try:
        return _service(db).validate(
            user_id=current_user.id,
            twin_id=twin_id,
            slot_id=slot_id,
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.put(
    "/twins/{twin_id}/user-functions/{slot_id}",
    response_model=TwinUserFunctionResponse,
    operation_id="saveTwinUserFunction",
    summary="Validate and save the current source for one Twin function slot",
)
async def save_twin_user_function(
    twin_id: str,
    slot_id: str,
    metadata: UploadFile = File(..., description="UTF-8 JSON function metadata"),
    source_archive: UploadFile = File(..., description="Bounded source ZIP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwinUserFunctionResponse:
    metadata_bytes, archive_bytes = await _read_upload(metadata, source_archive)
    try:
        return _service(db).save(
            user_id=current_user.id,
            twin_id=twin_id,
            slot_id=slot_id,
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.get(
    "/twins/{twin_id}/user-functions",
    response_model=TwinUserFunctionListResponse,
    operation_id="listTwinUserFunctions",
    summary="List the current validated functions of one Twin",
)
async def list_twin_user_functions(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwinUserFunctionListResponse:
    try:
        return _service(db).list_for_twin(
            user_id=current_user.id,
            twin_id=twin_id,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.delete(
    "/twins/{twin_id}/user-functions/{slot_id}",
    operation_id="deleteTwinUserFunction",
    summary="Remove the current function from one mutable Twin slot",
    status_code=204,
)
async def delete_twin_user_function(
    twin_id: str,
    slot_id: str,
    slot_version: str = Query(pattern="^[1-9][0-9]*$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        _service(db).delete(
            user_id=current_user.id,
            twin_id=twin_id,
            slot_id=slot_id,
            slot_version=slot_version,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)
    return Response(status_code=204)
