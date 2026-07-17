"""Publish provider refresh output through the immutable catalog repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.pricing_catalog_models import Provider, canonicalize_pricing_region
from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRepository,
)
from backend.pricing_registry_service import PricingRegistryService
from backend.pricing_schema import (
    PRICING_CONTRACT_VERSION,
    PRICING_SCHEMA_VERSION,
    validate_pricing_payload,
)


PRICING_REFRESH_RESULT_SCHEMA_VERSION = "pricing-catalog-refresh-result.v2"


class PricingCatalogRefreshService:
    """Validate, store, and conditionally publish one provider refresh."""

    def __init__(
        self,
        repository: PricingCatalogRepository,
        registry_service: PricingRegistryService | None = None,
    ) -> None:
        self.repository = repository
        self.registry_service = registry_service or PricingRegistryService()

    def persist_refresh(
        self,
        *,
        provider: Provider,
        pricing_region: str,
        pricing: dict[str, Any],
        account_pricing_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        canonical_region = canonicalize_pricing_region(provider, pricing_region)
        _validate_provider_identity(provider, canonical_region, pricing)
        validation = validate_pricing_payload(provider, pricing)
        fetched_at = _provider_timestamp(pricing)
        publishable = (
            validation["status"] == "valid"
            and not validation.get("review_required", False)
        )
        snapshot = self.repository.store_candidate(
            provider=provider,
            pricing_region=canonical_region,
            pricing=pricing,
            provider_schema_version=(
                (pricing.get("__schema__") or {}).get("schema_version")
                or PRICING_SCHEMA_VERSION
            ),
            contract_version=(
                (pricing.get("__schema__") or {}).get("contract_version")
                or PRICING_CONTRACT_VERSION
            ),
            registry_version=self.registry_service.get_registry_version(),
            mapping_versions=self._mapping_versions(provider),
            fetched_at=fetched_at,
            source="provider_api",
            review_status="reviewed" if publishable else "review_required",
            calculation_source="fresh",
        )
        active_reference = None
        if publishable:
            active_reference = self.repository.publish(snapshot.reference)
        else:
            try:
                active_reference = self.repository.resolve_published(
                    provider,
                    canonical_region,
                    require_fresh=False,
                ).reference
            except PricingCatalogNotFoundError:
                active_reference = None

        account_context = None
        if account_pricing_context is not None and active_reference is not None:
            account_context = dict(account_pricing_context)
            account_context["catalog_snapshot_digest"] = (
                active_reference.content_digest
            )

        return {
            "schemaVersion": PRICING_REFRESH_RESULT_SCHEMA_VERSION,
            "provider": provider,
            "pricingRegion": snapshot.reference.pricing_region,
            "status": "published" if publishable else "review_required",
            "reviewRequired": not publishable,
            "candidateReference": snapshot.reference.to_http_dict(),
            "activeCalculationReference": (
                active_reference.to_http_dict()
                if active_reference is not None
                else None
            ),
            "publicationSummary": _publication_summary(validation),
            "accountPricingContext": account_context,
        }

    def cached_result(
        self,
        provider: Provider,
        pricing_region: str,
    ) -> dict[str, Any]:
        snapshot = self.repository.resolve_published(
            provider,
            pricing_region,
            require_fresh=False,
        )
        return {
            "schemaVersion": PRICING_REFRESH_RESULT_SCHEMA_VERSION,
            "provider": provider,
            "pricingRegion": snapshot.reference.pricing_region,
            "status": "cached",
            "reviewRequired": False,
            "candidateReference": None,
            "activeCalculationReference": snapshot.reference.to_http_dict(),
            "publicationSummary": {
                "validationStatus": "valid",
                "qualityStatus": "reviewed",
                "missingFieldCount": 0,
                "fallbackFieldCount": len(
                    ((snapshot.pricing.get("__quality__") or {}).get(
                        "fallback_fields"
                    ) or [])
                ),
                "unsupportedFieldCount": len(
                    ((snapshot.pricing.get("__quality__") or {}).get(
                        "unsupported_fields"
                    ) or [])
                ),
            },
            "accountPricingContext": None,
        }

    def _mapping_versions(self, provider: Provider) -> tuple[str, ...]:
        mappings = self.registry_service.load().provider_mappings.get(provider, {})
        versions = {
            str(mapping.get("mapping_version"))
            for mapping in mappings.values()
            if mapping.get("mapping_version")
        }
        if not versions:
            raise ValueError(f"No pricing mapping versions exist for {provider}")
        return tuple(sorted(versions))


def _provider_timestamp(pricing: dict[str, Any]) -> datetime:
    value = (pricing.get("__schema__") or {}).get("generated_at")
    if not isinstance(value, str):
        raise ValueError("Provider pricing is missing generated_at")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Provider pricing generated_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _validate_provider_identity(
    provider: Provider,
    pricing_region: str,
    pricing: dict[str, Any],
) -> None:
    schema = pricing.get("__schema__")
    if not isinstance(schema, dict):
        raise ValueError("Provider pricing is missing schema metadata")
    if schema.get("provider") != provider:
        raise ValueError("Provider pricing metadata does not match the refresh provider")
    observed_region = schema.get("pricing_region")
    if not isinstance(observed_region, str):
        raise ValueError("Provider pricing is missing pricing_region")
    if canonicalize_pricing_region(provider, observed_region) != pricing_region:
        raise ValueError("Provider pricing metadata does not match the refresh region")


def _publication_summary(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "validationStatus": validation.get("status", "error"),
        "qualityStatus": validation.get("quality_status", "review_required"),
        "missingFieldCount": len(validation.get("missing_keys") or []),
        "fallbackFieldCount": len(validation.get("fallback_fields") or []),
        "unsupportedFieldCount": len(validation.get("unsupported_fields") or []),
    }
