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
from src.services.service_errors import DownstreamServiceError


class OptimizerCalculationService:
    """Owns forwarding calculation requests to the Optimizer service."""

    def __init__(
        self,
        *,
        optimizer_client: OptimizerClient | None = None,
        aws_twinmaker_contexts: AwsTwinMakerPricingContextService,
    ):
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.aws_twinmaker_contexts = aws_twinmaker_contexts

    async def calculate(
        self,
        params: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """Return the full Optimizer calculation response for the given params."""
        try:
            context = await self.aws_twinmaker_contexts.resolve(user_id)
            optimizer_params = {
                **params,
                "providerPricingContexts": {
                    "awsTwinMaker": context.payload,
                },
            }
            result = await self.optimizer_client.calculate(optimizer_params)
            optimizer_result = result.get("result", result)
            if (
                not isinstance(optimizer_result, dict)
                or not optimizer_aws_l4_selection_matches_context(
                    optimizer_result,
                    context,
                )
            ):
                raise DownstreamServiceError(
                    502,
                    "Optimizer response is not bound to the trusted AWS "
                    "pricing context.",
                )
            return result
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc
