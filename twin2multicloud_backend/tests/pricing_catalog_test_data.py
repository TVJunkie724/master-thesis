"""Deterministic immutable pricing-catalog contracts for Management tests."""

from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.pricing_catalog import (
    PricingCatalogContext,
    PricingCatalogReference,
    Provider,
    build_pricing_catalog_snapshot_id,
)


REGIONS: dict[Provider, str] = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
IDENTITY_HEX: dict[Provider, str] = {
    "aws": "a",
    "azure": "b",
    "gcp": "c",
}


def catalog_reference(
    provider: Provider,
    *,
    pricing_region: str | None = None,
    identity_hex: str | None = None,
    calculation_source: str = "reviewed_baseline",
) -> PricingCatalogReference:
    marker = identity_hex or IDENTITY_HEX[provider]
    fetched_at = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
    source = (
        "reviewed_baseline"
        if calculation_source == "reviewed_baseline"
        else "provider_api"
    )
    pricing_region = pricing_region or REGIONS[provider]
    content_digest = f"sha256:{marker * 64}"
    snapshot_id = build_pricing_catalog_snapshot_id(
        provider=provider,
        pricing_region=pricing_region,
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=fetched_at,
        content_digest=content_digest,
        source=source,
        review_status="reviewed",
    )
    return PricingCatalogReference.model_validate(
        {
            "schemaVersion": "pricing-catalog-reference.v1",
            "snapshotId": snapshot_id,
            "provider": provider,
            "pricingRegion": pricing_region,
            "providerSchemaVersion": "pricing-provider-schema.v1",
            "contractVersion": "2026.07.17",
            "registryVersion": "2026.07.17",
            "mappingVersions": ["2026.07.17"],
            "fetchedAt": fetched_at,
            "contentDigest": content_digest,
            "source": source,
            "reviewStatus": "reviewed",
            "publicationStatus": "published",
            "calculationSource": calculation_source,
        }
    )


def catalog_context() -> PricingCatalogContext:
    return PricingCatalogContext(
        schema_version="provider-pricing-catalog-context.v1",
        catalogs={
            provider: catalog_reference(provider)
            for provider in ("aws", "azure", "gcp")
        },
    )


def catalog_status(provider: Provider, *, is_fresh: bool = True) -> dict:
    return {
        "age": "1 hour" if is_fresh else "8 days",
        "status": "valid",
        "missing_keys": [],
        "is_fresh": is_fresh,
        "threshold_days": 7,
        "active_reference": catalog_reference(provider).to_http_dict(),
    }
