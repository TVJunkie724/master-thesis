"""One-time migration of an explicit legacy export into reviewed baselines."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from backend.pricing_catalog_models import (
    PricingCatalogBaselineManifest,
    PricingCatalogSnapshot,
    build_pricing_catalog_reference,
    canonical_json_bytes,
)
from backend.pricing_schema import (
    PRICING_CONTRACT_VERSION,
    PRICING_SCHEMA_VERSION,
    attach_pricing_metadata,
    canonical_pricing_snapshot_digest,
)


PROVIDER_REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}


def migrate_baselines(
    *,
    legacy_root: Path,
    output_root: Path,
    registry_root: Path,
    gcp_reviewed_at: datetime,
) -> PricingCatalogBaselineManifest:
    if output_root.exists():
        raise FileExistsError(f"Baseline output already exists: {output_root}")

    references = {}
    snapshots = {}
    registry_version = _registry_version(registry_root)
    for provider, region in PROVIDER_REGIONS.items():
        source = legacy_root / f"pricing_dynamic_{provider}.json"
        payload = _load_json(source)
        prepared, fetched_at = _prepare_payload(
            provider,
            region,
            payload,
            gcp_reviewed_at=gcp_reviewed_at,
        )
        mapping_versions = _mapping_versions(registry_root, provider)
        reference = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=region,
            pricing=prepared,
            provider_schema_version=PRICING_SCHEMA_VERSION,
            contract_version=PRICING_CONTRACT_VERSION,
            registry_version=registry_version,
            mapping_versions=mapping_versions,
            fetched_at=fetched_at,
            source="reviewed_baseline",
            review_status="reviewed",
            calculation_source="reviewed_baseline",
        )
        references[provider] = reference
        snapshots[provider] = PricingCatalogSnapshot(
            reference=reference,
            pricing=prepared,
        )

    manifest = PricingCatalogBaselineManifest(catalogs=references)
    output_root.mkdir(parents=True)
    (output_root / "baseline.json").write_bytes(
        canonical_json_bytes(manifest.to_storage_dict())
    )
    for provider, snapshot in snapshots.items():
        reference = snapshot.reference
        target = (
            output_root
            / provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(canonical_json_bytes(snapshot.to_storage_dict()))
    return manifest


def _prepare_payload(
    provider: str,
    region: str,
    payload: dict[str, Any],
    *,
    gcp_reviewed_at: datetime,
) -> tuple[dict[str, Any], datetime]:
    prepared = deepcopy(payload)
    prepared.pop("__account_pricing_context__", None)
    prepared.pop("__publication__", None)
    schema = prepared.get("__schema__")
    if provider == "gcp":
        prepared = attach_pricing_metadata("gcp", prepared, fetched={})
        schema = prepared["__schema__"]
        fetched_at = gcp_reviewed_at.astimezone(timezone.utc)
    else:
        if not isinstance(schema, dict):
            raise ValueError(f"{provider} baseline is missing __schema__")
        fetched_at = _parse_timestamp(schema.get("generated_at"))

    schema["schema_version"] = PRICING_SCHEMA_VERSION
    schema["contract_version"] = PRICING_CONTRACT_VERSION
    schema["provider"] = provider
    schema["pricing_region"] = region
    schema["generated_at"] = fetched_at.isoformat()
    schema["baseline_provenance"] = (
        "curated_legacy_review"
        if provider == "gcp"
        else "provider_observation_migration"
    )
    schema["snapshot_digest"] = canonical_pricing_snapshot_digest(prepared)
    return prepared, fetched_at


def _mapping_versions(registry_root: Path, provider: str) -> tuple[str, ...]:
    path = registry_root / "providers" / provider / "mappings.yaml"
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    versions: set[str] = set()
    _collect_mapping_versions(payload, versions)
    if not versions:
        raise ValueError(f"No mapping version found for provider {provider}")
    return tuple(sorted(versions))


def _registry_version(registry_root: Path) -> str:
    versions = set()
    for path in sorted(registry_root.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if isinstance(payload, dict) and payload.get("registry_version"):
            versions.add(str(payload["registry_version"]))
    if len(versions) != 1:
        raise ValueError("Registry documents must declare one shared registry version")
    return versions.pop()


def _collect_mapping_versions(value: Any, target: set[str]) -> None:
    if isinstance(value, dict):
        mapping_version = value.get("mapping_version")
        if mapping_version:
            target.add(str(mapping_version))
        for nested in value.values():
            _collect_mapping_versions(nested, target)
    elif isinstance(value, list):
        for nested in value:
            _collect_mapping_versions(nested, target)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Legacy pricing document must be an object: {path}")
    return payload


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Provider baseline is missing a trustworthy timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Provider baseline timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-root",
        type=Path,
        required=True,
        help="Explicit directory containing the three legacy provider exports",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("json/pricing_catalog_baselines"),
    )
    parser.add_argument(
        "--registry-root",
        type=Path,
        default=Path("pricing_registry"),
    )
    parser.add_argument("--gcp-reviewed-at", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    gcp_reviewed_at = _parse_timestamp(args.gcp_reviewed_at)
    manifest = migrate_baselines(
        legacy_root=args.legacy_root,
        output_root=args.output_root,
        registry_root=args.registry_root,
        gcp_reviewed_at=gcp_reviewed_at,
    )
    print(
        "Migrated immutable pricing baselines:",
        ", ".join(
            f"{provider}={reference.snapshot_id}"
            for provider, reference in sorted(manifest.catalogs.items())
        ),
    )


if __name__ == "__main__":
    main()
