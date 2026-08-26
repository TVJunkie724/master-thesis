#!/usr/bin/env python3
"""Refresh the digest cascade for the standalone Six-layer contract bundle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCH_ROOT = ROOT / "contracts" / "architecture-profiles"
DEFINITIONS = ARCH_ROOT / "definitions"
PROFILE_PATH = DEFINITIONS / "profiles" / "six-layer-eventing" / "1" / "profile.json"
CATALOG_PATH = (
    DEFINITIONS / "component-catalogs" / "six-layer-eventing" / "1" / "catalog.json"
)
MANIFEST_PATH = DEFINITIONS / "six-layer-eventing-v1-manifest.json"
REGISTRY_PATH = ARCH_ROOT / "v2" / "semantic-registry.json"
CAPACITY_REGISTRY_PATH = (
    ROOT
    / "contracts"
    / "resolved-deployment-specification"
    / "v2"
    / "component-capacity-registry.json"
)
RTA_PATH = (
    ARCH_ROOT
    / "v2"
    / "fixtures"
    / "valid"
    / "six-layer-aws-azure-eventing-small-resolved.json"
)
RDS_PATH = (
    ROOT
    / "contracts"
    / "resolved-deployment-specification"
    / "v2"
    / "fixtures"
    / "valid"
    / "six-layer-aws-azure-eventing-small.json"
)
DEPLOYMENT_MANIFEST_PATH = (
    ROOT
    / "contracts"
    / "deployment-manifest"
    / "v4"
    / "fixtures"
    / "valid"
    / "six-layer-aws-azure-eventing-small.json"
)
PRICING_BASELINE_PATH = (
    ROOT / "2-twin2clouds" / "json" / "pricing_catalog_baselines" / "baseline.json"
)
PROVIDERS = ("aws", "azure", "gcp")


def _load_runtime() -> ModuleType:
    path = ARCH_ROOT / "v2" / "runtime.py"
    spec = importlib.util.spec_from_file_location("six_layer_contract_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load architecture contract runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNTIME = _load_runtime()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _refresh_document(document: dict[str, Any]) -> str:
    document["content_digest"] = RUNTIME.calculate_digest(document)
    return str(document["content_digest"])


def _rds_digest(document: dict[str, Any]) -> str:
    value = dict(document)
    value.pop("digest", None)
    return _digest(value)


def _artifact_source_digest(repository_source_path: str) -> str:
    source_path = ROOT / repository_source_path
    paths = [source_path] if source_path.is_file() else sorted(source_path.rglob("*"))
    digest = hashlib.sha256()
    included = 0
    for path in paths:
        if (
            not path.is_file()
            or path.is_symlink()
            or "__pycache__" in path.parts
            or ".git" in path.parts
            or path.suffix.lower() == ".zip"
            or path.name.startswith(".git")
            or path.name == ".DS_Store"
        ):
            continue
        relative = (
            repository_source_path
            if source_path.is_file()
            else f"{repository_source_path}/{path.relative_to(source_path).as_posix()}"
        )
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        included += 1
    if included == 0:
        raise RuntimeError(f"Six-layer package source is empty: {repository_source_path}")
    return f"sha256:{digest.hexdigest()}"


def main() -> int:
    profile = _read(PROFILE_PATH)
    bundle = dict(profile["optimization_bundle"])
    bundle["workload_contract_version"] = "1"
    bundle.pop("compatibility_digest", None)
    bundle["compatibility_digest"] = _digest(bundle)
    profile["optimization_bundle"] = bundle
    profile_digest = _refresh_document(profile)
    _write(PROFILE_PATH, profile)

    catalog = _read(CATALOG_PATH)
    for artifact in catalog["package_artifacts"]:
        artifact["source_digest"] = _artifact_source_digest(
            artifact["repository_source_path"]
        )
    catalog_digest = _refresh_document(catalog)
    _write(CATALOG_PATH, catalog)

    provider_documents: dict[str, dict[str, Any]] = {}
    for provider in PROVIDERS:
        path = (
            DEFINITIONS
            / "provider-implementations"
            / "six-layer-eventing"
            / "1"
            / provider
            / "1.json"
        )
        document = _read(path)
        document["architecture_profile_ref"] = {
            "id": "six-layer-eventing",
            "version": "1",
            "digest": profile_digest,
        }
        _refresh_document(document)
        _write(path, document)
        provider_documents[provider] = document

    registry = _read(REGISTRY_PATH)
    registry["compatible_optimization_bundles"] = [bundle]
    _refresh_document(registry)
    _write(REGISTRY_PATH, registry)

    manifest = _read(MANIFEST_PATH)
    inherited = sorted(key for key in manifest if key.startswith("inherited_"))
    if inherited:
        raise RuntimeError(f"Standalone manifest still inherits: {', '.join(inherited)}")
    manifest["profile_ref"] = {
        "id": "six-layer-eventing",
        "version": "1",
        "digest": profile_digest,
    }
    manifest["provider_profile_refs"] = [
        {
            "provider": provider,
            "id": document["implementation_profile_id"],
            "version": document["implementation_profile_version"],
            "digest": document["content_digest"],
        }
        for provider, document in provider_documents.items()
    ]
    manifest["catalog_ref"] = {
        "id": catalog["catalog_id"],
        "version": catalog["catalog_version"],
        "digest": catalog_digest,
    }
    manifest_digest = _refresh_document(manifest)
    _write(MANIFEST_PATH, manifest)

    capacity_registry = _read(CAPACITY_REGISTRY_PATH)
    capacity_registry["content_digest"] = ""
    capacity_registry["content_digest"] = _digest(capacity_registry)
    _write(CAPACITY_REGISTRY_PATH, capacity_registry)

    pricing = _read(PRICING_BASELINE_PATH)["catalogs"]
    rds = _read(RDS_PATH)
    rds["architecture_profile_ref"]["digest"] = profile_digest
    rds["optimization_context"]["component_catalog_ref"]["digest"] = catalog_digest
    for reference in rds["optimization_context"]["pricing_evidence_refs"]:
        reference["digest"] = pricing[reference["provider"]]["content_digest"]
    rds["digest"] = _rds_digest(rds)
    _write(RDS_PATH, rds)

    rta = _read(RTA_PATH)
    rta["architecture_profile_ref"]["digest"] = profile_digest
    for key in tuple(rta["optimization_bundle_ref"]):
        if key in bundle:
            rta["optimization_bundle_ref"][key] = bundle[key]
    used_providers = {row["provider"] for row in rta["provider_profile_refs"]}
    provider_refs = {
        provider: {
            "id": provider_documents[provider]["implementation_profile_id"],
            "version": provider_documents[provider]["implementation_profile_version"],
            "digest": provider_documents[provider]["content_digest"],
            "provider": provider,
        }
        for provider in sorted(used_providers)
    }
    rta["provider_profile_refs"] = list(provider_refs.values())
    for assignment in rta["component_assignments"]:
        reference = provider_refs[assignment["provider"]]
        assignment["provider_implementation_profile_ref"] = {
            key: reference[key] for key in ("id", "version", "digest")
        }
    for reference in rta["pricing_evidence_refs"]:
        catalog_reference = pricing[reference["provider"]]
        reference["id"] = catalog_reference["snapshot_id"]
        reference["digest"] = catalog_reference["content_digest"]
    rta["deployment_specification_ref"]["digest"] = rds["digest"]
    rta["resolution_id"] = RUNTIME.calculate_resolution_id(rta)
    completeness_payload = {
        "capabilities": sorted(
            rta["functional_completeness"]["required_capability_ids"]
        ),
        "profile_digest": profile_digest,
        "catalog_digest": catalog_digest,
    }
    rta["functional_completeness"]["validation_digest"] = _digest(
        completeness_payload
    )
    rta_digest = _refresh_document(rta)
    _write(RTA_PATH, rta)

    deployment_manifest = _read(DEPLOYMENT_MANIFEST_PATH)
    deployment_manifest["resolved_twin_architecture"] = rta
    deployment_manifest["resolved_twin_architecture_digest"] = rta_digest
    deployment_manifest["resolved_deployment_specification"] = rds
    deployment_manifest["resolved_deployment_specification_digest"] = rds["digest"]
    deployment_manifest["compatibility"]["component_catalog_ref"] = {
        "id": catalog["catalog_id"],
        "version": catalog["catalog_version"],
        "digest": catalog_digest,
    }
    _write(DEPLOYMENT_MANIFEST_PATH, deployment_manifest)

    print(
        "six-layer-contract-digests: OK "
        f"(profile={profile_digest}, catalog={catalog_digest}, manifest={manifest_digest}, "
        f"capacity_registry={capacity_registry['content_digest']}, "
        f"rta={rta_digest}, rds={rds['digest']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
