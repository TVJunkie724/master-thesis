"""Shared HTTP client helpers for external service clients."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.services.errors import ExternalServiceError, ExternalServiceUnavailable


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

    def _client(self, timeout: float | httpx.Timeout | None = None) -> httpx.AsyncClient:
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
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} unavailable") from exc

        self._raise_for_status(response)
        return response.json()

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
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} unavailable") from exc

        self._raise_for_status(response)
        return response.content

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
                async with client.stream(method, f"{self.base_url}{path}", **kwargs) as response:
                    self._raise_for_status(response)
                    async for line in response.aiter_lines():
                        yield line
        except httpx.RequestError as exc:
            raise ExternalServiceUnavailable(f"{self.service_name} unavailable") from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise ExternalServiceError(
                f"{self.service_name} returned {response.status_code}: {response.text}"
            )
