import asyncio

import pytest
from fastapi import HTTPException

from src.api.upload_limits import read_upload_bounded


class ChunkedUpload:
    def __init__(self, content: bytes):
        self.content = content
        self.offset = 0
        self.closed = False

    async def read(self, size: int) -> bytes:
        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    async def close(self) -> None:
        self.closed = True


def test_bounded_reader_returns_content_at_limit():
    upload = ChunkedUpload(b"1234")

    assert asyncio.run(read_upload_bounded(upload, max_bytes=4)) == b"1234"
    assert upload.closed is True


def test_bounded_reader_stops_once_limit_is_exceeded():
    upload = ChunkedUpload(b"12345-secret-tail")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(read_upload_bounded(upload, max_bytes=4))

    assert exc_info.value.status_code == 413
    assert upload.offset == 5
    assert upload.closed is True
