from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.pricing_catalog_models import (
    PricingCatalogBaselineManifest,
    PricingCatalogContext,
    PricingCatalogSnapshot,
    build_pricing_catalog_reference,
    canonical_json_bytes,
)
from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRepository,
)
from backend.pricing_catalog_resolver import PricingCatalogResolver


FETCHED_AT = datetime.now(timezone.utc)


def _seed_repository(tmp_path: Path) -> tuple[
    PricingCatalogRepository,
    PricingCatalogContext,
]:
    baseline_root = tmp_path / "baseline"
    baseline_root.mkdir()
    references = {}
    payloads = {}
    for provider, region in {
        "aws": "eu-central-1",
        "azure": "westeurope",
        "gcp": "europe-west1",
    }.items():
        pricing = {
            "__schema__": {
                "schema_version": "pricing-provider-schema.v1",
                "contract_version": "2026.07.17",
                "provider": provider,
            },
            "service": {"price": 0.25},
        }
        reference = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=region,
            pricing=pricing,
            provider_schema_version="pricing-provider-schema.v1",
            contract_version="2026.07.17",
            registry_version="2026.07.17",
            mapping_versions=("2026.07.17",),
            fetched_at=FETCHED_AT,
            source="reviewed_baseline",
            review_status="reviewed",
            calculation_source="reviewed_baseline",
        )
        references[provider] = reference
        payloads[provider] = PricingCatalogSnapshot(
            reference=reference,
            pricing=pricing,
        )
    manifest = PricingCatalogBaselineManifest(catalogs=references)
    (baseline_root / "baseline.json").write_bytes(
        canonical_json_bytes(manifest.to_storage_dict())
    )
    for provider, snapshot in payloads.items():
        reference = snapshot.reference
        target = (
            baseline_root
            / provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(canonical_json_bytes(snapshot.to_storage_dict()))
    repository = PricingCatalogRepository(
        runtime_root=tmp_path / "runtime",
        baseline_root=baseline_root,
    )
    repository.initialize_from_baseline()
    return repository, PricingCatalogContext(catalogs=references)


def test_resolver_returns_exact_detached_three_provider_pricing(tmp_path):
    repository, context = _seed_repository(tmp_path)
    resolved = PricingCatalogResolver(repository).resolve_context(context)

    assert resolved.context == context
    assert set(resolved.pricing) == {
        "aws",
        "azure",
        "gcp",
        "__aws_schema__",
    }
    assert resolved.pricing["azure"]["service"]["price"] == 0.25
    detached = resolved.detached_pricing()
    detached["azure"]["service"]["price"] = 99
    assert resolved.pricing["azure"]["service"]["price"] == 0.25


def test_resolver_resolves_all_snapshots_before_returning(tmp_path):
    repository, context = _seed_repository(tmp_path)
    missing = context.catalogs["gcp"]
    target = (
        repository.runtime_root
        / "gcp"
        / missing.pricing_region
        / "snapshots"
        / f"{missing.snapshot_id}.json"
    )
    target.unlink()

    with pytest.raises(PricingCatalogNotFoundError):
        PricingCatalogResolver(repository).resolve_context(context)


def test_resolver_ignores_pointer_movement_after_context_selection(tmp_path):
    repository, context = _seed_repository(tmp_path)
    updated = repository.store_candidate(
        provider="azure",
        pricing_region="westeurope",
        pricing={
            "__schema__": {
                "schema_version": "pricing-provider-schema.v1",
                "contract_version": "2026.07.17",
                "provider": "azure",
            },
            "service": {"price": 0.75},
        },
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=datetime.now(timezone.utc),
        source="provider_api",
        review_status="reviewed",
        calculation_source="fresh",
    )
    repository.publish(updated.reference)

    resolved = PricingCatalogResolver(repository).resolve_context(context)

    assert resolved.pricing["azure"]["service"]["price"] == 0.25
    assert resolved.context.catalogs["azure"] == context.catalogs["azure"]
