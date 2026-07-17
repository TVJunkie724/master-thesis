"""Upgrade reviewed baselines to the canonical transfer-pricing contract."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any

from backend.pricing_catalog_models import (
    PricingCatalogBaselineManifest,
    PricingCatalogSnapshot,
    build_pricing_catalog_reference,
    canonical_json_bytes,
)
from backend.pricing_schema import (
    CURATED,
    PRICING_CONTRACT_VERSION,
    PRICING_SCHEMA_VERSION,
    RESERVED_PRICING_KEYS,
    canonical_pricing_snapshot_digest,
)
from backend.transfer_catalog import (
    TRANSFER_CATALOG_FIELDS,
    build_transfer_catalog,
    build_transfer_evidence,
)
from scripts.migrate_pricing_catalog_baselines import _mapping_versions


PROVIDER_TRANSFER_BASELINES: dict[str, dict[str, Any]] = {
    "aws": {
        "source_api": "aws-price-list-reviewed-baseline",
        "source_url": "https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer",
        "free_allowance_quantity": 100,
        "tiers": (
            ("aws-paid-1", 0, 10_240, 0.09),
            ("aws-paid-2", 10_240, 51_200, 0.085),
            ("aws-paid-3", 51_200, 153_600, 0.07),
            ("aws-paid-4", 153_600, None, 0.05),
        ),
    },
    "azure": {
        "source_api": "azure-retail-prices-reviewed-baseline",
        "source_url": "https://azure.microsoft.com/en-us/pricing/details/bandwidth/",
        "free_allowance_quantity": None,
        "tiers": (
            ("azure-free", 0, 100, 0),
            ("azure-paid-1", 100, 10_335, 0.087),
            ("azure-paid-2", 10_335, 51_295, 0.083),
            ("azure-paid-3", 51_295, 153_695, 0.07),
            ("azure-paid-4", 153_695, 512_095, 0.05),
            ("azure-paid-5", 512_095, None, 0.05),
        ),
    },
    "gcp": {
        "source_api": "gcp-official-pricing-reviewed-baseline",
        "source_url": (
            "https://cloud.google.com/skus/sku-groups/"
            "network-premium-gce-internet-egress"
        ),
        "free_allowance_quantity": 1,
        "tiers": (
            ("gcp-paid-1", 0, 1_024, 0.12),
            ("gcp-paid-2", 1_024, 10_240, 0.11),
            ("gcp-paid-3", 10_240, None, 0.085),
        ),
    },
}

REMOVED_FIELDS = {
    "aws": {
        "s3InfrequentAccess": (
            "transferCostFromDynamoDB",
            "transferCostFromCosmosDB",
        ),
        "apiGateway": ("dataTransferOutPrice",),
    },
    "azure": {
        "blobStorageCool": ("transferCostFromCosmosDB",),
    },
    "gcp": {
        "apiGateway": ("dataTransferOutPrice",),
    },
}


def upgrade_transfer_pricing_baseline(
    *,
    source_root: Path,
    output_root: Path,
    registry_root: Path,
) -> PricingCatalogBaselineManifest:
    """Create a non-destructive v2 baseline package from the reviewed v1 seed."""

    if output_root.exists():
        raise FileExistsError(f"Baseline output already exists: {output_root}")
    source_manifest_payload = _load_json(source_root / "baseline.json")
    source_manifest = PricingCatalogBaselineManifest.model_validate(
        source_manifest_payload
    )
    shutil.copytree(source_root, output_root)
    history_root = output_root / "history"
    history_root.mkdir(parents=True, exist_ok=True)
    (history_root / "baseline-2026.07.17.json").write_bytes(
        canonical_json_bytes(source_manifest_payload)
    )

    references = {}
    snapshots = {}
    template = {}
    for provider, old_reference in source_manifest.catalogs.items():
        source_snapshot = source_root / (
            f"{provider}/{old_reference.pricing_region}/snapshots/"
            f"{old_reference.snapshot_id}.json"
        )
        old_snapshot = PricingCatalogSnapshot.model_validate(
            _load_json(source_snapshot)
        )
        prepared = _upgrade_provider_pricing(
            provider,
            old_reference.pricing_region,
            old_snapshot.pricing,
            fetched_at=old_reference.fetched_at.isoformat().replace(
                "+00:00",
                "Z",
            ),
        )
        reference = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=old_reference.pricing_region,
            pricing=prepared,
            provider_schema_version=PRICING_SCHEMA_VERSION,
            contract_version=PRICING_CONTRACT_VERSION,
            registry_version=old_reference.registry_version,
            mapping_versions=_mapping_versions(registry_root, provider),
            fetched_at=old_reference.fetched_at,
            source="reviewed_baseline",
            review_status="reviewed",
            calculation_source="reviewed_baseline",
        )
        references[provider] = reference
        snapshots[provider] = PricingCatalogSnapshot(
            reference=reference,
            pricing=prepared,
        )
        template[provider] = {
            key: deepcopy(value)
            for key, value in prepared.items()
            if key not in RESERVED_PRICING_KEYS
        }

    manifest = PricingCatalogBaselineManifest(catalogs=references)
    (output_root / "baseline.json").write_bytes(
        canonical_json_bytes(manifest.to_storage_dict())
    )
    for provider, snapshot in snapshots.items():
        reference = snapshot.reference
        target = output_root / (
            f"{provider}/{reference.pricing_region}/snapshots/"
            f"{reference.snapshot_id}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical_json_bytes(snapshot.to_storage_dict()))
    (output_root / "pricing.template.json").write_bytes(
        canonical_json_bytes(template)
    )
    return manifest


def _upgrade_provider_pricing(
    provider: str,
    pricing_region: str,
    pricing: dict[str, Any],
    *,
    fetched_at: str,
) -> dict[str, Any]:
    prepared = deepcopy(pricing)
    specification = PROVIDER_TRANSFER_BASELINES[provider]
    selected_rows = [
        {
            "tierId": tier_id,
            "startQuantity": start,
            "endQuantity": end,
            "unitPrice": price,
        }
        for tier_id, start, end, price in specification["tiers"]
    ]
    evidence = build_transfer_evidence(
        provider=provider,
        pricing_region=pricing_region,
        source_type="reviewed_baseline",
        source_api=specification["source_api"],
        source_url=specification["source_url"],
        mapping_version="2026.07.18",
        selected_rows=selected_rows,
        fetched_at=fetched_at,
    )
    prepared["transfer"] = build_transfer_catalog(
        provider=provider,
        pricing_region=pricing_region,
        tier_thresholds=[
            {
                "tier_id": tier_id,
                "start_quantity": start,
                "unit_price": price,
            }
            for tier_id, start, _, price in specification["tiers"]
        ],
        free_allowance_quantity=specification["free_allowance_quantity"],
        evidence_id=evidence["evidence_id"],
    )
    for service, fields in REMOVED_FIELDS[provider].items():
        service_payload = prepared.get(service)
        if isinstance(service_payload, dict):
            for field in fields:
                service_payload.pop(field, None)

    schema = prepared.setdefault("__schema__", {})
    schema["schema_version"] = PRICING_SCHEMA_VERSION
    schema["contract_version"] = PRICING_CONTRACT_VERSION
    schema["provider"] = provider
    schema["pricing_region"] = pricing_region

    quality = prepared.setdefault("__quality__", {})
    field_sources = quality.setdefault("field_sources", {})
    removed_paths = {
        f"{service}.{field}"
        for service, fields in REMOVED_FIELDS[provider].items()
        for field in fields
    }
    for path in tuple(field_sources):
        if path in removed_paths or path.startswith("transfer."):
            field_sources.pop(path, None)
    for field in TRANSFER_CATALOG_FIELDS:
        field_sources[f"transfer.{field}"] = CURATED
    for key in ("fallback_fields", "unsupported_fields"):
        quality[key] = [
            path
            for path in quality.get(key, [])
            if path not in removed_paths and not path.startswith("transfer.")
        ]
    quality["review_required"] = bool(
        quality.get("fallback_fields") or quality.get("unsupported_fields")
    )
    quality["quality_status"] = (
        "review_required" if quality["review_required"] else "publishable"
    )

    generated = prepared.setdefault(
        "__evidence__",
        {
            "schema_version": "pricing-generated-evidence.v1",
            "provider": provider,
        },
    )
    generated.setdefault("fields", {})["transfer.catalog"] = evidence
    schema["snapshot_digest"] = canonical_pricing_snapshot_digest(prepared)
    return prepared


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("json/pricing_catalog_baselines"),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--registry-root",
        type=Path,
        default=Path("pricing_registry"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = upgrade_transfer_pricing_baseline(
        source_root=args.source_root,
        output_root=args.output_root,
        registry_root=args.registry_root,
    )
    print(
        "Upgraded transfer pricing baselines:",
        ", ".join(
            f"{provider}={reference.snapshot_id}"
            for provider, reference in sorted(manifest.catalogs.items())
        ),
    )


if __name__ == "__main__":
    main()
