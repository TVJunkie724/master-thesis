"""Typed Optimizer API client."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.clients.base import ExternalServiceClient
from src.config import settings


@dataclass(frozen=True)
class OptimizerProviderStatus:
    """Provider-scoped cache status from the Optimizer freshness endpoints."""

    provider: str
    status_code: int
    payload: dict[str, Any]

    @property
    def is_success(self) -> bool:
        return self.status_code == 200


class OptimizerClient(ExternalServiceClient):
    service_name = "Optimizer API"

    def __init__(self, base_url: str | None = None, **kwargs):
        super().__init__(
            base_url=base_url or getattr(settings, "OPTIMIZER_URL", "http://twin2clouds:8000"),
            **kwargs,
        )

    async def validate_optimizer_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/validate/optimizer-config",
            json=payload,
            timeout=30.0,
        )

    async def verify_permissions(self, provider: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/permissions/verify/{provider}",
            json=credentials,
            timeout=30.0,
        )

    async def calculate(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "PUT",
            "/calculate",
            json=params,
            timeout=60.0,
        )

    async def get_cache_status(
        self,
        *,
        endpoint_prefix: str,
        provider: str,
    ) -> OptimizerProviderStatus:
        """Return one provider cache status while preserving non-200 detail."""
        response = await self._request(
            "GET",
            f"/{endpoint_prefix}/{provider}",
            timeout=30.0,
        )
        payload = self._json_object(response) if response.status_code == 200 else {}
        return OptimizerProviderStatus(
            provider=provider,
            status_code=response.status_code,
            payload=payload,
        )

    async def export_pricing_snapshot(self, provider: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/pricing/export/{provider}",
            timeout=30.0,
        )

    async def refresh_azure_pricing(self) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/fetch_pricing/azure",
            params={"force_fetch": True},
            timeout=300.0,
        )

    async def refresh_pricing_with_credentials(
        self,
        provider: str,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/fetch_pricing_with_credentials/{provider}",
            json=credentials,
            timeout=300.0,
        )

    def stream_pricing_refresh(
        self,
        provider: str,
        credentials: dict[str, Any],
    ) -> AsyncIterator[str]:
        return self._stream_text_chunks(
            "POST",
            f"/stream/fetch_pricing/{provider}",
            json=credentials,
            headers={"Accept": "text/event-stream"},
            timeout=300.0,
        )
