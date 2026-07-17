from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import multiprocessing
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.pricing_catalog_models import (
    PricingCatalogBaselineManifest,
    PricingCatalogContext,
    PricingCatalogReference,
    PricingCatalogSnapshot,
    build_pricing_catalog_reference,
    canonical_json_bytes,
    canonicalize_pricing_region,
)
from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRefreshInProgressError,
    PricingCatalogRepository,
    PricingCatalogStaleError,
    PricingCatalogStorageError,
    PricingCatalogTamperedError,
    PricingCatalogUnreviewedError,
    get_pricing_catalog_repository,
)


FETCHED_AT = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}


def _pricing(provider: str, value: float = 0.25) -> dict:
    return {
        "__schema__": {
            "schema_version": "pricing-provider-schema.v1",
            "contract_version": "2026.07.17",
            "provider": provider,
        },
        "__quality__": {
            "quality_status": "publishable",
            "review_required": False,
            "field_sources": {"service.price": "fetched"},
            "fallback_fields": [],
            "unsupported_fields": [],
        },
        "service": {"price": value},
    }


def _reference(
    provider: str,
    *,
    pricing: dict | None = None,
    region: str | None = None,
    fetched_at: datetime = FETCHED_AT,
    source: str = "reviewed_baseline",
    review_status: str = "reviewed",
    calculation_source: str = "reviewed_baseline",
) -> PricingCatalogReference:
    return build_pricing_catalog_reference(
        provider=provider,
        pricing_region=region or REGIONS[provider],
        pricing=pricing or _pricing(provider),
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=fetched_at,
        source=source,
        review_status=review_status,
        calculation_source=calculation_source,
    )


def _write_baselines(root: Path) -> PricingCatalogBaselineManifest:
    references = {
        provider: _reference(provider)
        for provider in ("aws", "azure", "gcp")
    }
    manifest = PricingCatalogBaselineManifest(catalogs=references)
    root.mkdir(parents=True)
    (root / "baseline.json").write_bytes(
        canonical_json_bytes(manifest.to_storage_dict())
    )
    for provider, reference in references.items():
        snapshot = PricingCatalogSnapshot(
            reference=reference,
            pricing=_pricing(provider),
        )
        target = (
            root
            / provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(canonical_json_bytes(snapshot.to_storage_dict()))
    return manifest


@pytest.fixture
def repository(tmp_path):
    baseline_root = tmp_path / "baseline"
    _write_baselines(baseline_root)
    return PricingCatalogRepository(
        runtime_root=tmp_path / "runtime",
        baseline_root=baseline_root,
    )


def test_reference_identity_is_deterministic_and_fetch_time_sensitive():
    first = _reference("aws")
    duplicate = _reference("aws")
    later = _reference(
        "aws",
        fetched_at=FETCHED_AT + timedelta(seconds=1),
    )

    assert first == duplicate
    assert first.snapshot_id == duplicate.snapshot_id
    assert later.content_digest == first.content_digest
    assert later.snapshot_id != first.snapshot_id


def test_reference_rejects_unsorted_mapping_versions():
    reference = _reference("azure").model_dump(mode="json")
    reference["mapping_versions"] = ["2026.07.17", "2026.07.16"]

    with pytest.raises(ValidationError, match="sorted and unique"):
        PricingCatalogReference.model_validate(reference)


def test_reference_rejects_identity_mismatch():
    reference = _reference("gcp").model_dump(mode="json")
    reference["pricing_region"] = "us-central1"

    with pytest.raises(ValidationError, match="reference identity"):
        PricingCatalogReference.model_validate(reference)


def test_context_requires_exact_provider_map_and_matching_keys():
    references = {
        provider: _reference(provider)
        for provider in ("aws", "azure", "gcp")
    }
    context = PricingCatalogContext(catalogs=references)
    assert set(context.catalogs) == {"aws", "azure", "gcp"}
    with pytest.raises(TypeError):
        context.catalogs["aws"] = references["aws"]

    with pytest.raises(ValidationError, match="exactly aws, azure, and gcp"):
        PricingCatalogContext(catalogs={"aws": references["aws"]})

    mismatched = dict(references)
    mismatched["azure"] = references["gcp"]
    with pytest.raises(ValidationError, match="map key"):
        PricingCatalogContext(catalogs=mismatched)


def test_region_canonicalization_and_path_input_rejection():
    assert canonicalize_pricing_region("azure", "West Europe") == "westeurope"
    assert canonicalize_pricing_region("gcp", "EUROPE_WEST1") == "europe-west1"

    with pytest.raises(ValueError, match="canonical"):
        canonicalize_pricing_region("azure", "../../secrets")
    with pytest.raises(ValueError, match="AWS"):
        canonicalize_pricing_region("aws", "westeurope")


def test_initialization_is_idempotent_and_resolves_detached_baselines(repository):
    first = repository.initialize_from_baseline()
    second = repository.initialize_from_baseline()

    assert first == second
    snapshot = repository.resolve_baseline(
        "azure",
        now=FETCHED_AT + timedelta(days=1),
    )
    snapshot.pricing["service"]["price"] = 99
    reread = repository.resolve_baseline(
        "azure",
        now=FETCHED_AT + timedelta(days=1),
    )
    assert reread.pricing["service"]["price"] == 0.25


def test_initialization_preserves_newer_runtime_pointer(repository):
    manifest = repository.initialize_from_baseline()
    newer_pricing = _pricing("azure", 0.33)
    newer = repository.store_candidate(
        provider="azure",
        pricing_region="westeurope",
        pricing=newer_pricing,
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=FETCHED_AT + timedelta(hours=1),
        source="provider_api",
        review_status="reviewed",
        calculation_source="fresh",
    )
    repository.publish(newer.reference)

    repository.initialize_from_baseline()

    active = repository.resolve_published(
        "azure",
        "westeurope",
        now=FETCHED_AT + timedelta(days=1),
    )
    assert active.reference == newer.reference
    assert active.reference != manifest.catalogs["azure"]


def test_immutable_collision_with_different_bytes_fails(repository):
    repository.initialize_from_baseline()
    reference = repository.resolve_baseline(
        "aws",
        require_fresh=False,
    ).reference
    target = (
        repository.runtime_root
        / "aws"
        / "eu-central-1"
        / "snapshots"
        / f"{reference.snapshot_id}.json"
    )
    target.write_text('{"altered":true}\n', encoding="utf-8")

    with pytest.raises(PricingCatalogTamperedError, match="collision"):
        repository.initialize_from_baseline()


def test_exact_resolution_detects_content_tampering(repository):
    manifest = repository.initialize_from_baseline()
    reference = manifest.catalogs["gcp"]
    target = (
        repository.runtime_root
        / "gcp"
        / "europe-west1"
        / "snapshots"
        / f"{reference.snapshot_id}.json"
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["pricing"]["service"]["price"] = 9.99
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PricingCatalogTamperedError, match="invalid"):
        repository.resolve_exact(reference, require_fresh=False)


def test_symlink_snapshot_is_rejected(repository, tmp_path):
    manifest = repository.initialize_from_baseline()
    reference = manifest.catalogs["aws"]
    target = (
        repository.runtime_root
        / "aws"
        / "eu-central-1"
        / "snapshots"
        / f"{reference.snapshot_id}.json"
    )
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(replacement)

    with pytest.raises(PricingCatalogTamperedError, match="opened safely"):
        repository.resolve_exact(reference, require_fresh=False)


def test_missing_and_stale_snapshots_fail_closed(repository):
    manifest = repository.initialize_from_baseline()
    reference = manifest.catalogs["aws"]
    target = (
        repository.runtime_root
        / "aws"
        / "eu-central-1"
        / "snapshots"
        / f"{reference.snapshot_id}.json"
    )
    target.unlink()
    with pytest.raises(PricingCatalogNotFoundError):
        repository.resolve_exact(reference, require_fresh=False)

    repository.initialize_from_baseline()
    with pytest.raises(PricingCatalogStaleError):
        repository.resolve_exact(
            reference,
            now=FETCHED_AT + timedelta(days=8),
        )


def test_review_required_candidate_is_stored_but_not_publishable(repository):
    repository.initialize_from_baseline()
    candidate = repository.store_candidate(
        provider="gcp",
        pricing_region="europe-west1",
        pricing=_pricing("gcp", 0.5),
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=FETCHED_AT + timedelta(hours=1),
        source="provider_api",
        review_status="review_required",
        calculation_source="fresh",
    )

    with pytest.raises(PricingCatalogUnreviewedError):
        repository.publish(candidate.reference)
    with pytest.raises(PricingCatalogUnreviewedError):
        repository.resolve_exact(candidate.reference, require_fresh=False)


def test_account_context_is_removed_and_secret_keys_are_rejected(repository):
    repository.initialize_from_baseline()
    pricing = _pricing("aws")
    pricing["__account_pricing_context__"] = {"account_id": "123"}
    stored = repository.store_candidate(
        provider="aws",
        pricing_region="eu-central-1",
        pricing=pricing,
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=FETCHED_AT + timedelta(hours=1),
        source="provider_api",
        review_status="reviewed",
        calculation_source="fresh",
    )
    assert "__account_pricing_context__" not in stored.pricing

    unsafe = _pricing("aws")
    unsafe["service"]["aws_secret_access_key"] = "never-store-this"
    with pytest.raises(PricingCatalogStorageError, match="forbidden secret"):
        repository.store_candidate(
            provider="aws",
            pricing_region="eu-central-1",
            pricing=unsafe,
            provider_schema_version="pricing-provider-schema.v1",
            contract_version="2026.07.17",
            registry_version="2026.07.17",
            mapping_versions=("2026.07.17",),
            fetched_at=FETCHED_AT + timedelta(hours=2),
            source="provider_api",
            review_status="reviewed",
            calculation_source="fresh",
        )


def test_provider_regions_are_isolated(repository):
    repository.initialize_from_baseline()
    west = repository.store_candidate(
        provider="gcp",
        pricing_region="europe-west1",
        pricing=_pricing("gcp", 0.2),
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=FETCHED_AT + timedelta(hours=1),
        source="provider_api",
        review_status="reviewed",
        calculation_source="fresh",
    )
    central = repository.store_candidate(
        provider="gcp",
        pricing_region="us-central1",
        pricing=_pricing("gcp", 0.4),
        provider_schema_version="pricing-provider-schema.v1",
        contract_version="2026.07.17",
        registry_version="2026.07.17",
        mapping_versions=("2026.07.17",),
        fetched_at=FETCHED_AT + timedelta(hours=1),
        source="provider_api",
        review_status="reviewed",
        calculation_source="fresh",
    )
    repository.publish(west.reference)
    repository.publish(central.reference)

    assert repository.resolve_published(
        "gcp",
        "europe-west1",
        require_fresh=False,
    ).pricing["service"]["price"] == 0.2
    assert repository.resolve_published(
        "gcp",
        "us-central1",
        require_fresh=False,
    ).pricing["service"]["price"] == 0.4


def test_same_region_guard_rejects_duplicate_but_other_region_is_independent(
    repository,
):
    repository.initialize_from_baseline()
    with repository.refresh_guard("gcp", "europe-west1"):
        with pytest.raises(PricingCatalogRefreshInProgressError):
            with repository.refresh_guard("gcp", "europe-west1"):
                pass
        with repository.refresh_guard("gcp", "us-central1"):
            pass


def _hold_refresh_lock(runtime_root: str, baseline_root: str, ready, release):
    repository = PricingCatalogRepository(
        runtime_root=Path(runtime_root),
        baseline_root=Path(baseline_root),
    )
    with repository.refresh_guard("azure", "westeurope"):
        ready.set()
        release.wait(timeout=10)


def test_cross_process_refresh_lock_rejects_duplicate(repository):
    repository.initialize_from_baseline()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_refresh_lock,
        args=(
            str(repository.runtime_root),
            str(repository.baseline_root),
            ready,
            release,
        ),
    )
    process.start()
    try:
        assert ready.wait(timeout=10)
        with pytest.raises(PricingCatalogRefreshInProgressError):
            with repository.refresh_guard("azure", "westeurope"):
                pass
    finally:
        release.set()
        process.join(timeout=10)
    assert process.exitcode == 0


def test_readiness_rejects_drifted_runtime_manifest(repository):
    repository.initialize_from_baseline()
    target = repository.runtime_root / "baseline.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = "altered"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PricingCatalogTamperedError, match="differs"):
        repository.verify_readiness()


def test_readiness_rejects_tampered_active_pointer(repository):
    manifest = repository.initialize_from_baseline()
    target = (
        repository.runtime_root
        / "azure"
        / "westeurope"
        / "published.json"
    )
    payload = manifest.catalogs["azure"].model_dump(mode="json")
    payload["pricing_region"] = "northeurope"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PricingCatalogTamperedError, match="reference is invalid"):
        repository.verify_readiness()


def test_snapshot_size_limit_is_enforced(tmp_path):
    baseline_root = tmp_path / "baseline"
    _write_baselines(baseline_root)
    repository = PricingCatalogRepository(
        runtime_root=tmp_path / "runtime",
        baseline_root=baseline_root,
        max_snapshot_bytes=32,
    )

    with pytest.raises(PricingCatalogTamperedError, match="size limit"):
        repository.initialize_from_baseline()


def test_pricing_snapshot_digest_changes_with_quality_evidence():
    pricing = _pricing("azure")
    original = _reference("azure", pricing=pricing)
    altered = deepcopy(pricing)
    altered["__quality__"]["field_sources"]["service.price"] = "curated"
    changed = _reference("azure", pricing=altered)

    assert changed.content_digest != original.content_digest
    assert changed.snapshot_id != original.snapshot_id


def test_default_repository_uses_configured_roots(monkeypatch, tmp_path):
    baseline_root = tmp_path / "baseline"
    _write_baselines(baseline_root)
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("PRICING_CATALOG_BASELINE_ROOT", str(baseline_root))
    monkeypatch.setenv("PRICING_CATALOG_STORE_ROOT", str(runtime_root))
    get_pricing_catalog_repository.cache_clear()
    try:
        repository = get_pricing_catalog_repository()
        assert repository.runtime_root == runtime_root
        repository.verify_readiness()
    finally:
        get_pricing_catalog_repository.cache_clear()
