"""Bounded request-body readers for upload endpoints."""

import inspect

from fastapi import HTTPException, UploadFile

from src.project_archive.policy import UPLOAD_READ_CHUNK_BYTES

MAX_VALIDATION_UPLOAD_BYTES = 5 * 1024 * 1024


async def read_upload_bounded(upload: UploadFile, *, max_bytes: int) -> bytes:
    """Consume and close an upload while buffering at most ``max_bytes``."""
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await upload.read(
                min(UPLOAD_READ_CHUNK_BYTES, max_bytes + 1 - total)
            )
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum allowed size is {max_bytes} bytes.",
                )
            chunks.append(chunk)
    finally:
        close = getattr(upload, "close", None)
        if close is not None:
            close_result = close()
            if inspect.isawaitable(close_result):
                await close_result
