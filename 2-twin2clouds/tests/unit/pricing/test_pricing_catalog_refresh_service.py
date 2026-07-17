from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from backend.pricing_catalog_models import PricingCatalogReference
from backend.pricing_catalog_refresh_service import PricingCatalogRefreshService
from backend.pricing_catalog_repository import PricingCatalogRepository
from backend.pricing_registry_service import PricingRegistryService


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _repository(tmp_path) -> PricingCatalogRepository:
    baseline_root = tmp_path / "baseline"
    shutil.copytree(
        PROJECT_ROOT / "json" / "pricing_catalog_baselines",
        baseline_root,
    )
    repository = PricingCatalogRepository(
        runtime_root=tmp_path / "runtime",
        baseline_root=baseline_root,
    )
    repository.initialize_from_baseline()
    return repository


def test_publishable_refresh_replaces_only_matching_region_pointer(tmp_path):
    repository = _repository(tmp_path)
    service = PricingCatalogRefreshService(
        repository,
        PricingRegistryService(PROJECT_ROOT / "pricing_registry"),
    )
    pricing = repository.resolve_baseline(
        "azure",
        require_fresh=False,
    ).pricing

    result = service.persist_refresh(
        provider="azure",
        pricing_region="westeurope",
        pricing=pricing,
    )

    assert result["status"] == "published"
    assert result["reviewRequired"] is False
    assert result["candidateReference"] == result["activeCalculationReference"]
    assert result["publicationSummary"]["fallbackFieldCount"] == 0
    assert repository.resolve_published(
        "azure",
        "westeurope",
        require_fresh=False,
    ).reference.snapshot_id == result["candidateReference"]["snapshotId"]


def test_review_required_refresh_preserves_last_known_good(tmp_path):
    repository = _repository(tmp_path)
    service = PricingCatalogRefreshService(
        repository,
        PricingRegistryService(PROJECT_ROOT / "pricing_registry"),
    )
    previous = repository.resolve_published(
        "gcp",
        "europe-west1",
        require_fresh=False,
    ).reference
    pricing = repository.resolve_baseline("gcp", require_fresh=False).pricing

    result = service.persist_refresh(
        provider="gcp",
        pricing_region="europe-west1",
        pricing=pricing,
    )

    assert result["status"] == "review_required"
    assert result["candidateReference"]["publicationStatus"] == "candidate"
    assert result["activeCalculationReference"]["snapshotId"] == previous.snapshot_id
    assert result["publicationSummary"]["fallbackFieldCount"] > 0


def test_account_context_is_bound_to_active_digest_but_not_snapshot(tmp_path):
    repository = _repository(tmp_path)
    service = PricingCatalogRefreshService(
        repository,
        PricingRegistryService(PROJECT_ROOT / "pricing_registry"),
    )
    pricing = repository.resolve_baseline("aws", require_fresh=False).pricing

    result = service.persist_refresh(
        provider="aws",
        pricing_region="eu-central-1",
        pricing=pricing,
        account_pricing_context={"provider_account_id": "123456789012"},
    )

    assert result["accountPricingContext"]["catalog_snapshot_digest"] == (
        result["activeCalculationReference"]["contentDigest"]
    )
    candidate = PricingCatalogReference.model_validate(
        result["candidateReference"]
    )
    snapshot_path = (
        repository.runtime_root
        / "aws"
        / "eu-central-1"
        / "snapshots"
        / f"{candidate.snapshot_id}.json"
    )
    assert "provider_account_id" not in snapshot_path.read_text(encoding="utf-8")


def test_cached_result_contains_reference_not_full_pricing(tmp_path):
    repository = _repository(tmp_path)
    service = PricingCatalogRefreshService(
        repository,
        PricingRegistryService(PROJECT_ROOT / "pricing_registry"),
    )

    result = service.cached_result("azure", "westeurope")

    assert result["status"] == "cached"
    assert result["activeCalculationReference"]["provider"] == "azure"
    assert "pricing" not in result


def test_refresh_rejects_missing_or_mismatched_provider_identity(tmp_path):
    repository = _repository(tmp_path)
    service = PricingCatalogRefreshService(
        repository,
        PricingRegistryService(PROJECT_ROOT / "pricing_registry"),
    )
    pricing = repository.resolve_baseline(
        "azure",
        require_fresh=False,
    ).pricing

    without_region = {
        **pricing,
        "__schema__": {
            **pricing["__schema__"],
        },
    }
    without_region["__schema__"].pop("pricing_region")
    with pytest.raises(ValueError, match="missing pricing_region"):
        service.persist_refresh(
            provider="azure",
            pricing_region="westeurope",
            pricing=without_region,
        )

    mismatched = {
        **pricing,
        "__schema__": {
            **pricing["__schema__"],
            "provider": "gcp",
        },
    }
    with pytest.raises(ValueError, match="refresh provider"):
        service.persist_refresh(
            provider="azure",
            pricing_region="westeurope",
            pricing=mismatched,
        )

    wrong_region = {
        **pricing,
        "__schema__": {
            **pricing["__schema__"],
            "pricing_region": "northeurope",
        },
    }
    with pytest.raises(ValueError, match="refresh region"):
        service.persist_refresh(
            provider="azure",
            pricing_region="westeurope",
            pricing=wrong_region,
        )
