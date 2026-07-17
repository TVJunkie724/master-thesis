import json
from pathlib import Path
import shutil

import pytest

from backend.pricing_catalog_models import PricingCatalogSnapshot
from backend.transfer_catalog import TRANSFER_CATALOG_FIELDS, validate_transfer_catalog
from scripts.upgrade_transfer_pricing_baseline import (
    upgrade_transfer_pricing_baseline,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASELINE_ROOT = PROJECT_ROOT / "json" / "pricing_catalog_baselines"
REGISTRY_ROOT = PROJECT_ROOT / "pricing_registry"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_transfer_baseline_upgrade_is_non_destructive_and_auditable(tmp_path):
    source_root = tmp_path / "source"
    output_root = tmp_path / "output"
    shutil.copytree(BASELINE_ROOT, source_root)
    predecessor_path = BASELINE_ROOT / "history" / "baseline-2026.07.17.json"
    predecessor_payload = _load_json(predecessor_path)
    (source_root / "baseline.json").write_text(
        json.dumps(predecessor_payload),
        encoding="utf-8",
    )

    manifest = upgrade_transfer_pricing_baseline(
        source_root=source_root,
        output_root=output_root,
        registry_root=REGISTRY_ROOT,
    )

    assert _load_json(output_root / "history" / predecessor_path.name) == (
        predecessor_payload
    )
    template = _load_json(output_root / "pricing.template.json")
    for provider, reference in manifest.catalogs.items():
        snapshot_path = (
            output_root
            / provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )
        snapshot = PricingCatalogSnapshot.model_validate(_load_json(snapshot_path))
        assert snapshot.reference == reference
        transfer = snapshot.pricing["transfer"]
        validate_transfer_catalog(provider, reference.pricing_region, transfer)
        assert set(transfer) == set(TRANSFER_CATALOG_FIELDS)
        assert template[provider]["transfer"] == transfer

        field_sources = snapshot.pricing["__quality__"]["field_sources"]
        assert {
            field_sources[f"transfer.{field}"]
            for field in TRANSFER_CATALOG_FIELDS
        } == {"curated"}
        evidence = snapshot.pricing["__evidence__"]["fields"]["transfer.catalog"]
        assert evidence["source_type"] == "reviewed_baseline"
        assert evidence["review_required"] is False

        predecessor = predecessor_payload["catalogs"][provider]
        predecessor_snapshot = (
            output_root
            / provider
            / predecessor["pricing_region"]
            / "snapshots"
            / f"{predecessor['snapshot_id']}.json"
        )
        assert predecessor_snapshot.is_file()

    with pytest.raises(FileExistsError, match="already exists"):
        upgrade_transfer_pricing_baseline(
            source_root=source_root,
            output_root=output_root,
            registry_root=REGISTRY_ROOT,
        )
