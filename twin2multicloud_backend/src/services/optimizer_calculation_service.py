"""Optimizer calculation proxy use case."""

from __future__ import annotations

from typing import Any

from src.clients.optimizer_client import OptimizerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.service_errors import DownstreamServiceError


class OptimizerCalculationService:
    """Owns forwarding calculation requests to the Optimizer service."""

    def __init__(self, optimizer_client: OptimizerClient | None = None):
        self.optimizer_client = optimizer_client or OptimizerClient()

    async def calculate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the full Optimizer calculation response for the given params."""
        try:
            return await self.optimizer_client.calculate(params)
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc
