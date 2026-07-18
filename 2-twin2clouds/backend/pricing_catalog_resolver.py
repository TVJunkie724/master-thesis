"""Resolve exact catalog references into one immutable calculation input."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from backend.pricing_catalog_models import (
    PricingCatalogContext,
    PricingCatalogSnapshot,
)
from backend.pricing_catalog_repository import PricingCatalogRepository
from backend.pricing_schema import strip_pricing_metadata


@dataclass(frozen=True)
class ResolvedPricingCatalogs:
    """Detached calculation pricing and the exact references that produced it."""

    pricing: Mapping[str, Any]
    context: PricingCatalogContext

    def detached_pricing(self) -> dict[str, Any]:
        return deepcopy(dict(self.pricing))


class PricingCatalogResolver:
    """Fail-closed exact-reference resolver used by the calculation boundary."""

    def __init__(self, repository: PricingCatalogRepository) -> None:
        self.repository = repository

    def resolve_context(
        self,
        context: PricingCatalogContext,
        *,
        require_fresh: bool = True,
    ) -> ResolvedPricingCatalogs:
        snapshots: dict[str, PricingCatalogSnapshot] = {}
        for provider in ("aws", "azure", "gcp"):
            snapshots[provider] = self.repository.resolve_exact(
                context.catalogs[provider],
                require_fresh=require_fresh,
            )

        combined = {
            provider: strip_pricing_metadata(snapshot.pricing)
            for provider, snapshot in snapshots.items()
        }
        combined["__aws_schema__"] = deepcopy(
            snapshots["aws"].pricing.get("__schema__") or {}
        )
        return ResolvedPricingCatalogs(
            pricing=MappingProxyType(combined),
            context=PricingCatalogContext.model_validate(
                {
                    "catalogs": {
                        provider: reference.to_storage_dict()
                        for provider, reference in context.catalogs.items()
                    }
                }
            ),
        )
