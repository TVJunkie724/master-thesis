"""Shared bounded request parsing for API upload boundaries."""

import base64
import binascii
import json

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.upload_limits import read_upload_bounded

_JSON_ENVELOPE_ALLOWANCE_BYTES = 64 * 1024


async def extract_file_content(
    request: Request,
    *,
    max_bytes: int,
    file_field: str = "file",
    base64_field: str = "file_base64",
) -> bytes:
    """
    Extracts file content from a request, supporting both Multipart/Form-Data and Application/JSON (Base64).
    
    Args:
        request (Request): The FastAPI request object.
        file_field (str): The field name for multipart upload.
        base64_field (str): The field name for base64 string in JSON body.
        
    Returns:
        bytes: The binary content of the file.
        
    Raises:
        HTTPException: If extraction fails or content type is unsupported.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type:
        form = None
        try:
            form = await request.form(
                max_files=1,
                max_fields=2,
                max_part_size=max_bytes,
            )
        except StarletteHTTPException as exc:
            if exc.status_code == 400 and "maximum size" in str(exc.detail).lower():
                _raise_too_large(max_bytes)
            raise
        try:
            upload = form.get(file_field)
            if not isinstance(upload, UploadFile):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Missing or invalid file field '{file_field}' "
                        "in multipart request."
                    ),
                )
            return await read_upload_bounded(upload, max_bytes=max_bytes)
        finally:
            await form.close()
        
    elif "application/json" in content_type or not content_type:
        encoded_limit = ((max_bytes + 2) // 3) * 4 + _JSON_ENVELOPE_ALLOWANCE_BYTES
        raw_body = await _read_body_bounded(
            request,
            max_bytes=encoded_limit,
            reported_max_bytes=max_bytes,
        )
        try:
            body = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if not content_type:
                raise HTTPException(
                    status_code=415,
                    detail=(
                        "Missing Content-Type header. Use 'multipart/form-data' or "
                        "'application/json' with base64-encoded content."
                    ),
                ) from exc
            raise HTTPException(status_code=400, detail="Invalid JSON.") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON body.")
        encoded = body.get(base64_field)
        if not isinstance(encoded, str) or not encoded:
            raise HTTPException(
                status_code=400,
                detail=f"Missing or invalid '{base64_field}' field in JSON body.",
            )
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid Base64 string.") from exc
        if len(content) > max_bytes:
            _raise_too_large(max_bytes)
        return content

    raise HTTPException(
        status_code=415,
        detail="Unsupported Content-Type. Use 'multipart/form-data' or 'application/json'.",
    )


async def _read_body_bounded(
    request: Request,
    *,
    max_bytes: int,
    reported_max_bytes: int | None = None,
) -> bytes:
    reported_limit = reported_max_bytes or max_bytes
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            parsed_content_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid Content-Length header.",
            ) from exc
        if parsed_content_length < 0:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.")
        if parsed_content_length > max_bytes:
            _raise_too_large(reported_limit)

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            _raise_too_large(reported_limit)
        chunks.append(chunk)
    return b"".join(chunks)


def _raise_too_large(max_bytes: int) -> None:
    raise HTTPException(
        status_code=413,
        detail=f"File too large. Maximum allowed size is {max_bytes} bytes.",
    )
