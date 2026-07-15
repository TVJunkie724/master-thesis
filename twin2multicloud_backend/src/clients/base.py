"""Shared HTTP client helpers for external service clients."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.services.errors import ExternalServiceError, ExternalServiceUnavailable


MAX_EXTERNAL_ERROR_BODY_BYTES = 64 * 1024


class ExternalServiceClient:
    """Small wrapper around httpx with consistent error mapping."""

    service_name = "External service"

    def __init__(
        self,
        base_url: str,
        timeout: float | httpx.Timeout = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _client(
        self, timeout: float | httpx.Timeout | None = None
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=timeout or self.timeout,
            transport=self.transport,
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            async with self._client(timeout) as client:
                response = await client.request(
                    method, f"{self.base_url}{path}", **kwargs
                )
        except httpx.TimeoutException as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} timed out") from exc
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(
                f"{self.service_name} unavailable"
            ) from exc

        self._raise_for_status(response)
        return self._json_object(response)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Return a raw response for client methods that preserve status details."""
        try:
            async with self._client(timeout) as client:
                return await client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.TimeoutException as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} timed out") from exc
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(
                f"{self.service_name} unavailable"
            ) from exc

    async def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> bytes:
        try:
            async with self._client(timeout) as client:
                response = await client.request(
                    method, f"{self.base_url}{path}", **kwargs
                )
        except httpx.TimeoutException as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} timed out") from exc
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(
                f"{self.service_name} unavailable"
            ) from exc

        self._raise_for_status(response)
        return response.content

    async def _request_bounded_response(
        self,
        method: str,
        path: str,
        *,
        max_bytes: int,
        size_error_detail: str,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Stream a binary response into a bounded buffer while retaining metadata."""
        try:
            async with self._client(timeout) as client:
                async with client.stream(
                    method,
                    f"{self.base_url}{path}",
                    **kwargs,
                ) as response:
                    await self._raise_for_stream_status(response)
                    self._validate_content_length(
                        response,
                        max_bytes=max_bytes,
                        public_detail=size_error_detail,
                    )
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > max_bytes:
                            raise ExternalServiceError(
                                f"{self.service_name} response exceeded {max_bytes} bytes",
                                public_detail=size_error_detail,
                            )
                        content.extend(chunk)
                    return httpx.Response(
                        status_code=response.status_code,
                        headers=response.headers,
                        content=bytes(content),
                        request=response.request,
                    )
        except httpx.TimeoutException as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} timed out") from exc
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(
                f"{self.service_name} unavailable"
            ) from exc

    async def _stream_lines(
        self,
        method: str,
        path: str,
        *,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        try:
            async with self._client(timeout) as client:
                async with client.stream(
                    method, f"{self.base_url}{path}", **kwargs
                ) as response:
                    await self._raise_for_stream_status(response)
                    async for line in response.aiter_lines():
                        yield line
        except httpx.TimeoutException as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} timed out") from exc
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(
                f"{self.service_name} unavailable"
            ) from exc

    async def _stream_text_chunks(
        self,
        method: str,
        path: str,
        *,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        try:
            async with self._client(timeout) as client:
                async with client.stream(
                    method, f"{self.base_url}{path}", **kwargs
                ) as response:
                    await self._raise_for_stream_status(response)
                    async for chunk in response.aiter_text():
                        yield chunk
        except httpx.TimeoutException as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} timed out") from exc
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(
                f"{self.service_name} unavailable"
            ) from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            detail = response.text[:MAX_EXTERNAL_ERROR_BODY_BYTES]
            raise ExternalServiceError(
                f"{self.service_name} returned {response.status_code}: {detail}",
                upstream_status_code=response.status_code,
                public_detail=detail,
            )

    async def _raise_for_stream_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        content = bytearray()
        async for chunk in response.aiter_bytes():
            remaining = MAX_EXTERNAL_ERROR_BODY_BYTES - len(content)
            if remaining <= 0:
                break
            content.extend(chunk[:remaining])
        detail = bytes(content).decode(response.encoding or "utf-8", errors="replace")
        raise ExternalServiceError(
            f"{self.service_name} returned {response.status_code}: {detail}",
            upstream_status_code=response.status_code,
            public_detail=detail,
        )

    def _validate_content_length(
        self,
        response: httpx.Response,
        *,
        max_bytes: int,
        public_detail: str,
    ) -> None:
        raw_length = response.headers.get("content-length")
        if raw_length is None:
            return
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ExternalServiceError(
                f"{self.service_name} returned an invalid Content-Length",
                public_detail=public_detail,
            ) from exc
        if content_length < 0 or content_length > max_bytes:
            raise ExternalServiceError(
                f"{self.service_name} response size is invalid",
                public_detail=public_detail,
            )

    def _json_object(self, response: httpx.Response) -> dict[str, Any]:
        """Decode an object payload or fail with a safe, typed upstream error."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                f"{self.service_name} returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ExternalServiceError(f"{self.service_name} returned non-object JSON")
        return payload
