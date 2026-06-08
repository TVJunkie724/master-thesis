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
