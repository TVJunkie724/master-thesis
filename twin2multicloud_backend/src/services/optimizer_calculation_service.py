"""Optimizer calculation proxy use case."""

from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.services.service_errors import DownstreamServiceError


OPTIMIZER_URL = getattr(settings, "OPTIMIZER_URL", "http://master-thesis-2twin2clouds-1:8000")


class OptimizerCalculationService:
    """Owns forwarding calculation requests to the Optimizer service."""

    async def calculate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the full Optimizer calculation response for the given params."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.put(f"{OPTIMIZER_URL}/calculate", json=params)
        except httpx.ConnectError as exc:
            raise DownstreamServiceError(503, "Cannot connect to Optimizer service") from exc
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(504, "Optimizer service timed out") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(502, f"Request failed: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise DownstreamServiceError(response.status_code, response.text)
        return response.json()
