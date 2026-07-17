"""Optimizer pricing and regions status use cases."""

from __future__ import annotations

from typing import Any

from src.clients.optimizer_client import OptimizerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error


PROVIDERS = ("aws", "azure", "gcp")


class OptimizerStatusService:
    """Owns read-only Optimizer freshness status proxy calls."""

    def __init__(self, optimizer_client: OptimizerClient | None = None):
        self.optimizer_client = optimizer_client or OptimizerClient()

    async def get_pricing_status(
        self,
        *,
        pricing_regions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return pricing freshness status for all providers."""
        return await self._get_provider_status(
            endpoint_prefix="pricing_age",
            pricing_regions=pricing_regions,
        )

    async def get_regions_status(self) -> dict[str, Any]:
        """Return region freshness status for all providers."""
        return await self._get_provider_status(endpoint_prefix="regions_age")

    async def _get_provider_status(
        self,
        endpoint_prefix: str,
        *,
        pricing_regions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            responses = {}
            for provider in PROVIDERS:
                kwargs = {
                    "endpoint_prefix": endpoint_prefix,
                    "provider": provider,
                }
                if pricing_regions is not None:
                    kwargs["pricing_region"] = pricing_regions[provider]
                responses[provider] = await self.optimizer_client.get_cache_status(
                    **kwargs,
                )
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc

        return {
            provider: response.payload if response.is_success else {"error": "Failed to fetch"}
            for provider, response in responses.items()
        }
