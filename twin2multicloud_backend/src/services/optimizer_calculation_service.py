"""Optimizer calculation proxy use case."""

from __future__ import annotations

from typing import Any

from src.clients.optimizer_client import OptimizerClient
from src.services.aws_twinmaker_pricing_context_service import (
    AwsTwinMakerPricingContextService,
    optimizer_aws_l4_selection_matches_context,
)
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.pricing_catalog_context_service import (
    PricingCatalogContextService,
    pricing_catalog_contexts_match,
)
from src.services.service_errors import DownstreamServiceError


class OptimizerCalculationService:
    """Owns forwarding calculation requests to the Optimizer service."""

    def __init__(
        self,
        *,
        optimizer_client: OptimizerClient | None = None,
        aws_twinmaker_contexts: AwsTwinMakerPricingContextService,
        pricing_catalog_contexts: PricingCatalogContextService,
    ):
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.aws_twinmaker_contexts = aws_twinmaker_contexts
        self.pricing_catalog_contexts = pricing_catalog_contexts

    async def calculate(
        self,
        params: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """Return the full Optimizer calculation response for the given params."""
        try:
            catalog_context = await self.pricing_catalog_contexts.resolve_for_user(
                user_id
            )
            aws_context = await self.aws_twinmaker_contexts.resolve(
                user_id,
                catalog_context.catalogs["aws"],
            )
            optimizer_params = {
                **params,
                "providerPricingCatalogs": catalog_context.to_http_dict(),
                "providerPricingContexts": {
                    "awsTwinMaker": aws_context.payload,
                },
            }
            result = await self.optimizer_client.calculate(optimizer_params)
            optimizer_result = result.get("result", result)
            if (
                not isinstance(optimizer_result, dict)
                or not optimizer_aws_l4_selection_matches_context(
                    optimizer_result,
                    aws_context,
                )
                or not pricing_catalog_contexts_match(
                    catalog_context,
                    optimizer_result.get("pricingCatalogs"),
                )
            ):
                raise DownstreamServiceError(
                    502,
                    "Optimizer response is not bound to the trusted pricing context.",
                )
            return result
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc
