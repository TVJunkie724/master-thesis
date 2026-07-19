"""Authenticated user-function slot, artifact, source, and binding routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.upload_limits import UploadLimitExceeded, read_upload_bounded
from src.models.database import get_db
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.user_function_extension import (
    ExtensionSlotListResponse,
    TwinExtensionBindingListResponse,
    TwinExtensionBindingResponse,
    TwinExtensionBindingUpdate,
    UserFunctionArtifactListResponse,
    UserFunctionArtifactResponse,
    UserFunctionValidationResponse,
)
from src.security.request_context import current_request_id
from src.security.user_function_rate_limit import (
    UserFunctionRateLimitExceeded,
    UserFunctionSecurityControlUnavailable,
    enforce_user_function_source_rate_limit,
)
from src.services.user_function_extension_service import (
    ExtensionContractError,
    UserFunctionExtensionService,
)


router = APIRouter(tags=["user-function-extensions"])
MAX_METADATA_BYTES = 64 * 1024
MAX_SOURCE_ARCHIVE_BYTES = 10 * 1024 * 1024
HTTP_BAD_REQUEST = 400


def _service(db: Session) -> UserFunctionExtensionService:
    return UserFunctionExtensionService(db, TwinRepository(db))


def _raise_contract_error(exc: ExtensionContractError) -> None:
    status = {
        "EXTENSION_BINDING_UNRESOLVED": 409,
        "EXTENSION_ARCHIVE_UNSAFE": HTTP_BAD_REQUEST,
        "EXTENSION_SECRET_MATERIAL_DETECTED": HTTP_BAD_REQUEST,
    }.get(exc.code, 422)
    raise HTTPException(status_code=status, detail=exc.as_dict()) from exc


async def _read_part(
    upload: UploadFile,
    *,
    limit: int,
    field: str,
) -> bytes:
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


async def _read_artifact_upload(
    *,
    metadata: UploadFile,
    source_archive: UploadFile,
    service: UserFunctionExtensionService,
    user_id: str,
    correlation_id: str,
) -> tuple[bytes, bytes]:
    try:
        metadata_bytes = await _read_part(
            metadata,
            limit=MAX_METADATA_BYTES,
            field="metadata",
        )
        archive_bytes = await _read_part(
            source_archive,
            limit=MAX_SOURCE_ARCHIVE_BYTES,
            field="source_archive",
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        service.record_upload(
            user_id=user_id,
            outcome="rejected",
            correlation_id=correlation_id,
            error_code=detail.get("error_code"),
        )
        raise
    service.record_upload(
        user_id=user_id,
        outcome="succeeded",
        correlation_id=correlation_id,
    )
    return metadata_bytes, archive_bytes


@router.get(
    "/architecture/extension-slots",
    response_model=ExtensionSlotListResponse,
    operation_id="listExtensionSlots",
    summary="List reviewed user-function extension slots",
)
async def list_extension_slots(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ExtensionSlotListResponse:
    return _service(db).list_slots()


@router.post(
    "/user-function-artifacts/validate",
    response_model=UserFunctionValidationResponse,
    operation_id="validateUserFunctionArtifact",
    summary="Validate a user-function artifact without persisting it",
)
async def validate_user_function_artifact(
    metadata: UploadFile = File(..., description="UTF-8 JSON client metadata"),
    source_archive: UploadFile = File(..., description="Source ZIP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserFunctionValidationResponse:
    service = _service(db)
    correlation_id = current_request_id()
    metadata_bytes, archive_bytes = await _read_artifact_upload(
        metadata=metadata,
        source_archive=source_archive,
        service=service,
        user_id=current_user.id,
        correlation_id=correlation_id,
    )
    try:
        return service.validate(
            user_id=current_user.id,
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
            correlation_id=correlation_id,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.post(
    "/user-function-artifacts",
    response_model=UserFunctionArtifactResponse,
    operation_id="createUserFunctionArtifact",
    summary="Validate and create one immutable user-function artifact",
    status_code=201,
)
async def create_user_function_artifact(
    metadata: UploadFile = File(..., description="UTF-8 JSON client metadata"),
    source_archive: UploadFile = File(..., description="Source ZIP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserFunctionArtifactResponse:
    service = _service(db)
    correlation_id = current_request_id()
    metadata_bytes, archive_bytes = await _read_artifact_upload(
        metadata=metadata,
        source_archive=source_archive,
        service=service,
        user_id=current_user.id,
        correlation_id=correlation_id,
    )
    try:
        return service.create(
            user_id=current_user.id,
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
            correlation_id=correlation_id,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.post(
    "/user-function-artifacts/{legacy_artifact_id}/import",
    response_model=UserFunctionArtifactResponse,
    operation_id="importLegacyUserFunctionArtifact",
    summary="Explicitly validate a replacement for one owner-scoped legacy artifact",
    status_code=201,
)
async def import_legacy_user_function_artifact(
    legacy_artifact_id: UUID,
    metadata: UploadFile = File(..., description="UTF-8 JSON client metadata"),
    source_archive: UploadFile = File(..., description="Reviewed replacement ZIP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserFunctionArtifactResponse:
    service = _service(db)
    correlation_id = current_request_id()
    metadata_bytes, archive_bytes = await _read_artifact_upload(
        metadata=metadata,
        source_archive=source_archive,
        service=service,
        user_id=current_user.id,
        correlation_id=correlation_id,
    )
    try:
        return service.import_legacy(
            user_id=current_user.id,
            legacy_artifact_id=str(legacy_artifact_id),
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
            correlation_id=correlation_id,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.get(
    "/user-function-artifacts",
    response_model=UserFunctionArtifactListResponse,
    operation_id="listUserFunctionArtifacts",
    summary="List owner-scoped immutable artifacts without source text",
)
async def list_user_function_artifacts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserFunctionArtifactListResponse:
    return _service(db).list_artifacts(
        current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/user-function-artifacts/{artifact_id}",
    response_model=UserFunctionArtifactResponse,
    operation_id="getUserFunctionArtifact",
    summary="Get owner-scoped artifact metadata without source text",
)
async def get_user_function_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserFunctionArtifactResponse:
    try:
        return _service(db).get_artifact(current_user.id, artifact_id)
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.get(
    "/user-function-artifacts/{artifact_id}/source",
    operation_id="downloadUserFunctionArtifactSource",
    summary="Download owner-only deterministic source ZIP",
)
async def download_user_function_artifact_source(
    artifact_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    safe_artifact_id = str(artifact_id)
    service = _service(db)
    try:
        await enforce_user_function_source_rate_limit(response, current_user.id)
    except (
        UserFunctionRateLimitExceeded,
        UserFunctionSecurityControlUnavailable,
    ) as exc:
        service.record_source_download_attempt(
            user_id=current_user.id,
            artifact_id=safe_artifact_id,
            outcome=(
                "rate_limited"
                if isinstance(exc, UserFunctionRateLimitExceeded)
                else "control_unavailable"
            ),
            correlation_id=current_request_id(),
            error_code=(
                "RATE_LIMITED"
                if isinstance(exc, UserFunctionRateLimitExceeded)
                else "SECURITY_CONTROL_UNAVAILABLE"
            ),
        )
        raise
    try:
        payload = service.get_source_zip(
            user_id=current_user.id,
            artifact_id=safe_artifact_id,
            correlation_id=current_request_id(),
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="user-function-{safe_artifact_id}.zip"'
            ),
            "Cache-Control": "no-store",
            **{
                name: value
                for name, value in response.headers.items()
                if name.lower().startswith("ratelimit-")
            },
        },
    )


@router.get(
    "/twins/{twin_id}/extension-bindings",
    response_model=TwinExtensionBindingListResponse,
    operation_id="listTwinExtensionBindings",
    summary="List active owner-scoped Twin extension bindings",
)
async def list_twin_extension_bindings(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwinExtensionBindingListResponse:
    try:
        return _service(db).list_bindings(
            user_id=current_user.id,
            twin_id=twin_id,
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.put(
    "/twins/{twin_id}/extension-bindings/{slot_id}",
    response_model=TwinExtensionBindingResponse,
    operation_id="bindTwinExtensionArtifact",
    summary="Bind one validated immutable artifact to a reviewed slot",
)
async def bind_twin_extension_artifact(
    twin_id: str,
    slot_id: str,
    update: TwinExtensionBindingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwinExtensionBindingResponse:
    try:
        return _service(db).bind(
            user_id=current_user.id,
            twin_id=twin_id,
            slot_id=slot_id,
            update=update,
            correlation_id=current_request_id(),
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)


@router.delete(
    "/twins/{twin_id}/extension-bindings/{slot_id}",
    operation_id="unbindTwinExtensionArtifact",
    summary="Deactivate one Twin extension binding without deleting history",
    status_code=204,
)
async def unbind_twin_extension_artifact(
    twin_id: str,
    slot_id: str,
    slot_version: str = Query(pattern="^[1-9][0-9]*$"),
    expected_revision: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        _service(db).unbind(
            user_id=current_user.id,
            twin_id=twin_id,
            slot_id=slot_id,
            slot_version=slot_version,
            expected_revision=expected_revision,
            correlation_id=current_request_id(),
        )
    except ExtensionContractError as exc:
        _raise_contract_error(exc)
    return Response(status_code=204)
