"""Bounded multipart upload readers for Management API routes."""

from __future__ import annotations

from fastapi import UploadFile


UPLOAD_CHUNK_BYTES = 1024 * 1024


class UploadLimitExceeded(ValueError):
    """Raised before an uploaded request body can exceed its memory contract."""


async def read_upload_bounded(upload: UploadFile, *, max_bytes: int) -> bytes:
    """Read at most ``max_bytes`` and reject the first excess byte."""
    if max_bytes <= 0:
        raise ValueError("Upload size limit must be positive")
    content = bytearray()
    while True:
        remaining_with_sentinel = max_bytes + 1 - len(content)
        chunk = await upload.read(min(UPLOAD_CHUNK_BYTES, remaining_with_sentinel))
        if not chunk:
            return bytes(content)
        content.extend(chunk)
        if len(content) > max_bytes:
            raise UploadLimitExceeded(f"Upload exceeds {max_bytes} bytes")
