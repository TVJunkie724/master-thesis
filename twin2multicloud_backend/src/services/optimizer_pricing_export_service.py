"""Optimizer pricing export use case."""

from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.services.service_errors import DownstreamServiceError, ValidationError


OPTIMIZER_URL = getattr(settings, "OPTIMIZER_URL", "http://master-thesis-2twin2clouds-1:8000")
SUPPORTED_PRICING_EXPORT_PROVIDERS = {"aws", "azure", "gcp"}


class OptimizerPricingExportService:
    """Owns Optimizer pricing snapshot export proxying."""

    async def export_pricing_snapshot(self, provider: str) -> dict[str, Any]:
        """Return the full pricing export payload for a supported provider."""
        if provider not in SUPPORTED_PRICING_EXPORT_PROVIDERS:
            raise ValidationError(f"Invalid provider: {provider}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{OPTIMIZER_URL}/pricing/export/{provider}")
        except httpx.ConnectError as exc:
            raise DownstreamServiceError(503, "Cannot connect to Optimizer service") from exc
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(504, "Optimizer service timed out") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(502, f"Request failed: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise DownstreamServiceError(response.status_code, response.text)
        return response.json()
