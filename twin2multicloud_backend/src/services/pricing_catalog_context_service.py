"""Resolve owner-safe immutable pricing catalogs for Optimizer calculations."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.clients.optimizer_client import OptimizerClient
from src.schemas.pricing_catalog import (
    PricingCatalogContext,
    PricingCatalogReference,
    Provider,
)
from src.services.errors import (
    ExternalServiceError,
    OptimizerContractError,
    PricingCatalogUnavailable,
)

PROVIDERS: tuple[Provider, ...] = ("aws", "azure", "gcp")


class PricingCatalogContextService:
    """Build and verify exact three-provider contexts without loading pricing."""

    def __init__(
        self,
        optimizer_client: OptimizerClient | None = None,
    ) -> None:
        self._optimizer_client = optimizer_client or OptimizerClient()

    async def resolve(self) -> PricingCatalogContext:
        """Resolve the repository-pinned reviewed snapshot for every provider."""

        catalogs = {
            provider: await self._resolve_provider_reference(provider)
            for provider in PROVIDERS
        }
        return PricingCatalogContext(
            schema_version="provider-pricing-catalog-context.v1",
            catalogs=catalogs,
        )

    async def verify_context(
        self,
        context: PricingCatalogContext,
    ) -> PricingCatalogContext:
        verified: dict[Provider, PricingCatalogReference] = {}
        for provider, reference in context.catalogs.items():
            try:
                exact = await self._verify_reference(reference)
            except ExternalServiceError as exc:
                if exc.upstream_status_code != 404:
                    raise
                raise PricingCatalogUnavailable(
                    f"The stored {provider.upper()} pricing catalog no longer exists.",
                    error_code="PRICING_CATALOG_NOT_FOUND",
                ) from exc
            verified[provider] = exact
        return PricingCatalogContext(
            schema_version="provider-pricing-catalog-context.v1",
            catalogs=verified,
        )

    async def _resolve_provider_reference(
        self,
        provider: Provider,
    ) -> PricingCatalogReference:
        baseline = await self._baseline_reference(provider)
        try:
            verified_baseline = await self._verify_reference(baseline)
        except ExternalServiceError as exc:
            if exc.upstream_status_code != 404:
                raise
            raise PricingCatalogUnavailable(
                f"No published {provider.upper()} pricing catalog is available.",
                error_code="PRICING_CATALOG_NOT_FOUND",
            ) from exc
        return verified_baseline

    async def _baseline_reference(
        self,
        provider: Provider,
    ) -> PricingCatalogReference:
        payload = await self._optimizer_client.get_pricing_catalog_baseline(provider)
        try:
            reference = PricingCatalogReference.model_validate(payload)
        except ValidationError as exc:
            raise OptimizerContractError(
                "Optimizer baseline pricing reference is invalid.",
                [
                    {
                        "field": f"pricingCatalogs.catalogs.{provider}",
                        "message": "Invalid baseline reference",
                    }
                ],
            ) from exc
        if reference.provider != provider:
            raise OptimizerContractError(
                "Optimizer baseline pricing reference has the wrong provider."
            )
        return reference

    async def _verify_reference(
        self,
        reference: PricingCatalogReference,
    ) -> PricingCatalogReference:
        payload = (
            await self._optimizer_client.get_exact_pricing_catalog_reference(
                reference.provider,
                reference.pricing_region,
                reference.snapshot_id,
            )
        )

        try:
            verified = PricingCatalogReference.model_validate(
                payload.get("reference")
            )
        except ValidationError as exc:
            raise OptimizerContractError(
                "Optimizer exact pricing reference is invalid."
            ) from exc
        if verified != reference:
            raise OptimizerContractError(
                "Optimizer exact pricing reference does not match the requested identity."
            )
        return verified


def parse_pricing_catalog_context(value: Any) -> PricingCatalogContext:
    """Validate a persisted or downstream three-provider context."""

    try:
        return PricingCatalogContext.model_validate(value)
    except ValidationError as exc:
        raise OptimizerContractError(
            "Optimizer pricing catalog context is invalid.",
            [{"field": "pricingCatalogs", "message": "Invalid exact reference set"}],
        ) from exc


def pricing_catalog_contexts_match(
    expected: PricingCatalogContext,
    actual: Any,
) -> bool:
    try:
        parsed = PricingCatalogContext.model_validate(actual)
    except ValidationError:
        return False
    return parsed == expected
