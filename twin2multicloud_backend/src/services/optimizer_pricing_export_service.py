"""Optimizer pricing export use case."""

from __future__ import annotations

from typing import Any

from src.clients.optimizer_client import OptimizerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.service_errors import ValidationError


SUPPORTED_PRICING_EXPORT_PROVIDERS = {"aws", "azure", "gcp"}


class OptimizerPricingExportService:
    """Owns Optimizer pricing snapshot export proxying."""

    def __init__(self, optimizer_client: OptimizerClient | None = None):
        self.optimizer_client = optimizer_client or OptimizerClient()

    async def export_pricing_snapshot(self, provider: str) -> dict[str, Any]:
        """Return the full pricing export payload for a supported provider."""
        if provider not in SUPPORTED_PRICING_EXPORT_PROVIDERS:
            raise ValidationError(f"Invalid provider: {provider}")

        try:
            return await self.optimizer_client.export_pricing_snapshot(provider)
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc
