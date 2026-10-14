"""Read-only thesis pricing baseline coverage."""

from __future__ import annotations

import json

import pytest

from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRepository,
    PricingCatalogTamperedError,
    get_pricing_catalog_repository,
)


def test_tracked_baseline_resolves_exactly_three_verified_snapshots():
    repository = get_pricing_catalog_repository()

    snapshots = {
        provider: repository.resolve_baseline(provider)
        for provider in ("aws", "azure", "gcp")
    }

    assert set(snapshots) == {"aws", "azure", "gcp"}
    assert all(
        snapshot.reference.source == "reviewed_baseline"
        for snapshot in snapshots.values()
    )
    assert all(
        snapshot.reference.content_digest.startswith("sha256:")
        for snapshot in snapshots.values()
    )


def test_unpinned_exact_reference_is_rejected():
    repository = get_pricing_catalog_repository()
    reference = repository.resolve_baseline("aws").reference
    unpinned = reference.model_copy(update={"snapshot_id": "pcs_" + ("0" * 64)})

    with pytest.raises(PricingCatalogNotFoundError):
        repository.resolve_exact(unpinned)


def test_tampered_snapshot_fails_digest_validation(tmp_path):
    source = get_pricing_catalog_repository().baseline_root
    baseline = json.loads((source / "baseline.json").read_text(encoding="utf-8"))
    target = tmp_path / "baseline"
    target.mkdir()
    (target / "baseline.json").write_text(
        json.dumps(baseline),
        encoding="utf-8",
    )
    for provider, reference in baseline["catalogs"].items():
        source_snapshot = (
            source
            / provider
            / reference["pricing_region"]
            / "snapshots"
            / f"{reference['snapshot_id']}.json"
        )
        destination = (
            target
            / provider
            / reference["pricing_region"]
            / "snapshots"
            / source_snapshot.name
        )
        destination.parent.mkdir(parents=True)
        payload = json.loads(source_snapshot.read_text(encoding="utf-8"))
        if provider == "aws":
            payload["pricing"]["tampered"] = True
        destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PricingCatalogTamperedError):
        PricingCatalogRepository(baseline_root=target).verify_readiness()
