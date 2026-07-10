"""Optimizer pricing and regions status use cases."""

from __future__ import annotations

from typing import Any

from src.clients.optimizer_client import OptimizerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.service_errors import DownstreamServiceError


PROVIDERS = ("aws", "azure", "gcp")


class OptimizerStatusService:
    """Owns read-only Optimizer freshness status proxy calls."""

    def __init__(self, optimizer_client: OptimizerClient | None = None):
        self.optimizer_client = optimizer_client or OptimizerClient()

    async def get_pricing_status(self) -> dict[str, Any]:
        """Return pricing freshness status for all providers."""
        return await self._get_provider_status(endpoint_prefix="pricing_age")

    async def get_regions_status(self) -> dict[str, Any]:
        """Return region freshness status for all providers."""
        return await self._get_provider_status(endpoint_prefix="regions_age")

    async def _get_provider_status(self, endpoint_prefix: str) -> dict[str, Any]:
        try:
            responses = {
                provider: await self.optimizer_client.get_cache_status(
                    endpoint_prefix=endpoint_prefix,
                    provider=provider,
                )
                for provider in PROVIDERS
            }
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc

        return {
            provider: response.payload if response.is_success else {"error": "Failed to fetch"}
            for provider, response in responses.items()
        }
