"""Canonical transfer-pricing fixtures shared by pricing unit tests."""

from datetime import datetime, timezone

from backend.pricing_catalog_models import (
    PricingCatalogContext,
    build_pricing_catalog_reference,
)
from backend.transfer_catalog import (
    build_transfer_catalog,
    build_transfer_evidence,
)


PROVIDER_REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}

_SPECS = {
    "aws": {
        "free_allowance_quantity": 100,
        "tiers": ((0, 0.09), (10_240, 0.085), (51_200, 0.07), (153_600, 0.05)),
    },
    "azure": {
        "free_allowance_quantity": None,
        "tiers": (
            (0, 0),
            (100, 0.087),
            (10_335, 0.083),
            (51_295, 0.07),
            (153_695, 0.05),
            (512_095, 0.05),
        ),
    },
    "gcp": {
        "free_allowance_quantity": 1,
        "tiers": ((0, 0.12), (1_024, 0.11), (10_240, 0.085)),
    },
}


def canonical_transfer_fetch(provider: str) -> dict:
    """Return a fetched transfer payload with bounded canonical evidence."""

    region = PROVIDER_REGIONS[provider]
    specification = _SPECS[provider]
    selected_rows = [
        {
            "tierId": f"{provider}-tier-{index + 1}",
            "startQuantity": start,
            "unitPrice": price,
        }
        for index, (start, price) in enumerate(specification["tiers"])
    ]
    evidence = build_transfer_evidence(
        provider=provider,
        pricing_region=region,
        source_type="test_fixture",
        source_api="deterministic-test-fixture",
        source_url="https://example.invalid/pricing-fixture",
        mapping_version="2026.07.18",
        selected_rows=selected_rows,
        fetched_at="2026-07-18T00:00:00Z",
    )
    catalog = build_transfer_catalog(
        provider=provider,
        pricing_region=region,
        tier_thresholds=[
            {
                "tier_id": row["tierId"],
                "start_quantity": row["startQuantity"],
                "unit_price": row["unitPrice"],
            }
            for row in selected_rows
        ],
        free_allowance_quantity=specification["free_allowance_quantity"],
        evidence_id=evidence["evidence_id"],
    )
    return {
        **catalog,
        "__transfer_evidence__": evidence,
    }


def canonical_transfer_catalog(provider: str) -> dict:
    """Return only the strict calculation-time catalog fields."""

    return {
        key: value
        for key, value in canonical_transfer_fetch(provider).items()
        if key != "__transfer_evidence__"
    }


def pricing_catalog_context_for(pricing: dict) -> PricingCatalogContext:
    """Build exact, immutable catalog identities for calculation test data."""

    references = {}
    for provider in ("aws", "azure", "gcp"):
        provider_pricing = pricing[provider]
        references[provider] = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=provider_pricing["transfer"]["source_region"],
            pricing=provider_pricing,
            provider_schema_version="pricing-schema.v2",
            contract_version="test-pricing-contract.v1",
            registry_version="2026.07.17",
            mapping_versions=("test-fixture.v1",),
            fetched_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
            source="reviewed_baseline",
            review_status="reviewed",
            calculation_source="reviewed_baseline",
        )
    return PricingCatalogContext(catalogs=references)
