"""Bounded request-body readers for upload endpoints."""

from fastapi import HTTPException, UploadFile

from src.project_archive.policy import UPLOAD_READ_CHUNK_BYTES


async def read_upload_bounded(upload: UploadFile, *, max_bytes: int) -> bytes:
    """Read at most ``max_bytes`` without first buffering the entire upload."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(min(UPLOAD_READ_CHUNK_BYTES, max_bytes + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {max_bytes} bytes.",
            )
        chunks.append(chunk)
