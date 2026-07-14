"""Project archive extraction HTTP boundary."""

from __future__ import annotations

import zipfile

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import ValidationError

from api.error_models import ERROR_RESPONSES
from logger import logger
from src.api.models.zip_extraction import ValidationContextInput, ZipExtractionResponse
from src.api.upload_limits import read_upload_bounded
from src.core.observability import redact_sensitive
from src.project_archive.extraction import extract_project_archive
from src.project_archive.policy import (
    ArchiveLimitExceeded,
    ArchivePolicyError,
    MAX_COMPRESSED_ARCHIVE_BYTES,
)


router = APIRouter()


@router.post(
    "/validate/zip/extract",
    operation_id="extractProjectZip",
    tags=["Validation"],
    summary="Validate and extract non-secret project fields",
    description=(
        "Validates a bounded project ZIP and returns configuration, function, and "
        "scene fields for wizard auto-population. Credential files are never returned."
    ),
    response_model=ZipExtractionResponse,
    responses={
        200: {"description": "Extraction completed with aggregated validation results"},
        400: ERROR_RESPONSES[400],
        413: {"description": "Compressed or expanded archive limit exceeded"},
        422: ERROR_RESPONSES[422],
        500: ERROR_RESPONSES[500],
    },
)
async def extract_zip(
    file: UploadFile = File(..., description="Project ZIP file to extract"),
    validation_context: str | None = Query(None),
    include_credentials: bool = Query(
        False,
        description="Deprecated; credential content cannot be returned",
    ),
) -> ZipExtractionResponse:
    if include_credentials:
        raise HTTPException(
            status_code=400,
            detail=(
                "Credential extraction is not supported. "
                "Import cloud accounts through the Management API Cloud Connections boundary."
            ),
        )
    try:
        context = (
            ValidationContextInput.model_validate_json(validation_context)
            if validation_context
            else ValidationContextInput()
        )
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_COMPRESSED_ARCHIVE_BYTES,
        )
        return extract_project_archive(content, context)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid validation_context",
        ) from exc
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file") from exc
    except ArchiveLimitExceeded as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ArchivePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Project ZIP extraction failed: %s", redact_sensitive(exc))
        raise HTTPException(
            status_code=500,
            detail="Internal extraction error. Check server logs.",
        ) from exc
