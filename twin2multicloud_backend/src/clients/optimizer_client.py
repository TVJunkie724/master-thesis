"""Typed Optimizer API client."""

from typing import Any

from src.clients.base import ExternalServiceClient
from src.config import settings


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

    async def calculate(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "PUT",
            "/calculate",
            json=params,
            timeout=60.0,
        )

    async def refresh_pricing(
        self,
        provider: str,
        *,
        credentials: dict[str, Any] | None = None,
        force_fetch: bool = True,
    ) -> dict[str, Any]:
        if provider == "azure":
            return await self._request_json(
                "POST",
                "/fetch_pricing/azure",
                params={"force_fetch": force_fetch},
                timeout=300.0,
            )
        return await self._request_json(
            "POST",
            f"/fetch_pricing_with_credentials/{provider}",
            json=credentials or {},
            params={"force_fetch": force_fetch},
            timeout=300.0,
        )
