from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import yaml

from backend.pricing_catalog_models import PricingCatalogBaselineManifest
from backend.pricing_catalog_repository import PricingCatalogRepository
from backend.pricing_schema import strip_pricing_metadata
from scripts.migrate_pricing_catalog_baselines import migrate_baselines


def _write_legacy_payload(root: Path, provider: str) -> None:
    payload = {"service": {"price": 0.25}}
    if provider != "gcp":
        payload["__schema__"] = {
            "schema_version": "pricing-provider-schema.v1",
            "contract_version": "old",
            "provider": provider,
            "generated_at": "2026-07-17T10:00:00+00:00",
        }
        payload["__publication__"] = {"evaluated_at": "volatile"}
    (root / f"pricing_dynamic_{provider}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _write_registry(root: Path) -> None:
    (root / "intents.yaml").parent.mkdir(parents=True)
    (root / "intents.yaml").write_text(
        yaml.safe_dump({"registry_version": "2026.07.17"}),
        encoding="utf-8",
    )
    for provider, version in {
        "aws": "2026.07.17",
        "azure": "2026.07.16",
        "gcp": "2026.06.08",
    }.items():
        target = root / "providers" / provider / "mappings.yaml"
        target.parent.mkdir(parents=True)
        target.write_text(
            yaml.safe_dump(
                {
                    "mapping_version": version,
                    "mappings": [{"mapping_version": "2026.07.17"}],
                }
            ),
            encoding="utf-8",
        )


def test_migration_builds_three_verified_region_baselines(tmp_path):
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    for provider in ("aws", "azure", "gcp"):
        _write_legacy_payload(legacy_root, provider)
    registry_root = tmp_path / "registry"
    _write_registry(registry_root)
    output_root = tmp_path / "baseline"
    reviewed_at = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)

    manifest = migrate_baselines(
        legacy_root=legacy_root,
        output_root=output_root,
        registry_root=registry_root,
        gcp_reviewed_at=reviewed_at,
    )

    assert isinstance(manifest, PricingCatalogBaselineManifest)
    assert manifest.catalogs["aws"].pricing_region == "eu-central-1"
    assert manifest.catalogs["azure"].pricing_region == "westeurope"
    assert manifest.catalogs["gcp"].pricing_region == "europe-west1"
    assert manifest.catalogs["gcp"].fetched_at == reviewed_at
    assert manifest.catalogs["gcp"].mapping_versions == (
        "2026.06.08",
        "2026.07.17",
    )

    repository = PricingCatalogRepository(
        runtime_root=tmp_path / "runtime",
        baseline_root=output_root,
    )
    repository.initialize_from_baseline()
    gcp = repository.resolve_baseline("gcp", require_fresh=False)
    assert gcp.pricing["__schema__"]["baseline_provenance"] == (
        "curated_legacy_review"
    )
    assert gcp.pricing["__quality__"]["review_required"] is True
    assert "__publication__" not in gcp.pricing


def test_migration_refuses_to_replace_existing_output(tmp_path):
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    for provider in ("aws", "azure", "gcp"):
        _write_legacy_payload(legacy_root, provider)
    registry_root = tmp_path / "registry"
    _write_registry(registry_root)
    output_root = tmp_path / "baseline"
    output_root.mkdir()

    try:
        migrate_baselines(
            legacy_root=legacy_root,
            output_root=output_root,
            registry_root=registry_root,
            gcp_reviewed_at=datetime.now(timezone.utc),
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing baseline output must not be replaced")


def test_committed_baselines_preserve_legacy_calculation_payloads(tmp_path):
    project_root = Path(__file__).resolve().parents[3]
    repository = PricingCatalogRepository(
        runtime_root=tmp_path / "runtime",
        baseline_root=project_root / "json" / "pricing_catalog_baselines",
    )
    repository.initialize_from_baseline()
    for provider in ("aws", "azure", "gcp"):
        legacy = json.loads(
            (
                project_root
                / "json"
                / "fetched_data"
                / f"pricing_dynamic_{provider}.json"
            ).read_text(encoding="utf-8")
        )
        baseline = repository.resolve_baseline(
            provider,
            require_fresh=False,
        )
        assert strip_pricing_metadata(baseline.pricing) == (
            strip_pricing_metadata(legacy)
        )
