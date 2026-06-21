"""Optimizer pricing and regions status use cases."""

from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.services.service_errors import DownstreamServiceError


OPTIMIZER_URL = getattr(settings, "OPTIMIZER_URL", "http://master-thesis-2twin2clouds-1:8000")
PROVIDERS = ("aws", "azure", "gcp")


class OptimizerStatusService:
    """Owns read-only Optimizer freshness status proxy calls."""

    async def get_pricing_status(self) -> dict[str, Any]:
        """Return pricing freshness status for all providers."""
        return await self._get_provider_status(endpoint_prefix="pricing_age")

    async def get_regions_status(self) -> dict[str, Any]:
        """Return region freshness status for all providers."""
        return await self._get_provider_status(endpoint_prefix="regions_age")

    async def _get_provider_status(self, endpoint_prefix: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                responses = {
                    provider: await client.get(f"{OPTIMIZER_URL}/{endpoint_prefix}/{provider}")
                    for provider in PROVIDERS
                }
        except httpx.ConnectError as exc:
            raise DownstreamServiceError(503, "Cannot connect to Optimizer service") from exc
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(504, "Optimizer service timed out") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(502, f"Request failed: {type(exc).__name__}") from exc

        return {
            provider: response.json() if response.status_code == 200 else {"error": "Failed to fetch"}
            for provider, response in responses.items()
        }
