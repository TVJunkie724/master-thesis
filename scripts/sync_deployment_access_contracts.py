#!/usr/bin/env python3
"""Validate and synchronize the canonical deployment-access contracts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "contracts" / "deployment-access"
V1_ROOT = SOURCE_ROOT / "v1"
TARGETS = (
    REPO_ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "deployment-access",
    REPO_ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "deployment-access",
    REPO_ROOT
    / "twin2multicloud_flutter"
    / "assets"
    / "contracts"
    / "deployment-access",
)
IGNORED_NAMES = {".DS_Store", ".contract-sha256", "__pycache__"}
SURFACE_MATRIX = {
    ("l4", "aws"): ("aws_iot_twinmaker", "aws_identity_center", "none"),
    ("l4", "azure"): ("azure_digital_twins", "azure_entra", "none"),
    ("l4", "gcp"): ("gcp_twin_explorer", "gcp_iap", "none"),
    ("l5", "aws"): ("aws_managed_grafana", "aws_identity_center", "none"),
    ("l5", "azure"): ("azure_managed_grafana", "azure_entra", "none"),
    ("l5", "gcp"): ("gcp_grafana_oss", "generated_viewer", "rotate"),
}
EVIDENCE_PROFILES = (
    ("five-layer-baseline", "2"),
    ("six-layer-eventing", "1"),
)


def _files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_NAMES for part in path.relative_to(root).parts)
    )


def _documents(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in _files(root)}


def _tree_digest(documents: dict[str, bytes]) -> str:
    hasher = hashlib.sha256()
    for name, payload in sorted(documents.items()):
        relative = name.encode("utf-8")
        hasher.update(len(relative).to_bytes(4, "big"))
        hasher.update(relative)
        hasher.update(len(payload).to_bytes(8, "big"))
        hasher.update(payload)
    return f"sha256:{hasher.hexdigest()}"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((V1_ROOT / relative).read_text(encoding="utf-8"))


def _schema_validators() -> dict[str, Draft202012Validator]:
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(V1_ROOT.glob("*.schema.json"))
    }
    registry = Registry()
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema)
        )
    return {
        name: Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        )
        for name, schema in schemas.items()
    }


def validate_surface(surface: dict[str, Any]) -> None:
    identity = (surface.get("layer"), surface.get("provider"))
    expected = SURFACE_MATRIX.get(identity)
    actual = (
        surface.get("service_id"),
        surface.get("auth", {}).get("mode"),
        surface.get("auth", {}).get("credential_action"),
    )
    if expected != actual:
        raise ValueError(
            "Surface provider/service/auth mismatch: "
            f"identity={identity!r}, expected={expected!r}, actual={actual!r}"
        )
    parsed = urlsplit(str(surface.get("url", "")))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Surface URL is not safe absolute HTTPS: {surface.get('url')!r}")


def validate_snapshot(
    document: dict[str, Any],
    validator: Draft202012Validator,
) -> None:
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"Invalid deployment-access snapshot: {errors[0].message}")
    for surface in document["surfaces"]:
        validate_surface(surface)


def _placement_snapshots() -> list[dict[str, Any]]:
    surface_catalog = _load("fixtures/valid/surface-catalog.json")
    if set(surface_catalog) != {f"{layer}:{provider}" for layer, provider in SURFACE_MATRIX}:
        raise ValueError("Surface catalog does not contain the exact six provider/layer surfaces")
    matrix = _load("fixtures/valid/placement-matrix.json")
    if matrix.get("schema_version") != "deployment-access-placement-fixtures.v1":
        raise ValueError("Placement fixture schema version mismatch")
    snapshots: list[dict[str, Any]] = []
    pairs: set[tuple[str, str]] = set()
    fixture_ids: set[str] = set()
    for placement in matrix.get("placements", []):
        fixture_id = placement.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id or fixture_id in fixture_ids:
            raise ValueError("Placement fixture identifiers must be unique and non-empty")
        fixture_ids.add(fixture_id)
        try:
            l4 = deepcopy(surface_catalog[placement["l4_surface"]])
            l5 = deepcopy(surface_catalog[placement["l5_surface"]])
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Placement fixture {fixture_id!r} has an unknown surface") from exc
        pairs.add((l4["provider"], l5["provider"]))
        snapshots.append(
            {
                "schema_version": "deployment-access.v1",
                "twin_id": f"twin-{fixture_id}",
                "deployment_id": f"deployment-{fixture_id}",
                "generated_at": matrix["generated_at"],
                "availability": "available",
                "reason_code": None,
                "surfaces": [l4, l5],
            }
        )
    expected_pairs = {(l4, l5) for l4 in ("aws", "azure", "gcp") for l5 in ("aws", "azure", "gcp")}
    if pairs != expected_pairs or len(snapshots) != 9:
        raise ValueError("Placement fixtures must cover each of the exact nine L4/L5 provider pairs")
    return snapshots


def validate_source() -> str:
    required = {
        "README.md",
        "v1/deployment-access.schema.json",
        "v1/deployment-access-evidence.schema.json",
        "v1/deployment-access-credential.schema.json",
        "v1/fixtures/valid/surface-catalog.json",
        "v1/fixtures/valid/placement-matrix.json",
        "v1/fixtures/valid/unsupported-historical.json",
        "v1/fixtures/valid/gcp-viewer-credential.json",
        "v1/fixtures/invalid/available-missing-l5.json",
        "v1/fixtures/invalid/surface-secret-field.json",
        "v1/fixtures/invalid/provider-auth-mismatch.json",
    }
    present = {path.relative_to(SOURCE_ROOT).as_posix() for path in _files(SOURCE_ROOT)}
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"Missing canonical deployment-access files: {', '.join(missing)}")

    validators = _schema_validators()
    access_validator = validators["deployment-access.schema.json"]
    evidence_validator = validators["deployment-access-evidence.schema.json"]
    for snapshot in _placement_snapshots():
        validate_snapshot(snapshot, access_validator)
        for profile_id, profile_version in EVIDENCE_PROFILES:
            evidence = {
                "schema_version": "deployment-access-evidence.v1",
                "profile_id": profile_id,
                "profile_version": profile_version,
                "generated_at": snapshot["generated_at"],
                "surfaces": snapshot["surfaces"],
            }
            evidence_validator.validate(evidence)
    validate_snapshot(
        _load("fixtures/valid/unsupported-historical.json"), access_validator
    )
    validators["deployment-access-credential.schema.json"].validate(
        _load("fixtures/valid/gcp-viewer-credential.json")
    )

    for name in ("available-missing-l5.json", "surface-secret-field.json"):
        invalid = _load(f"fixtures/invalid/{name}")
        if not list(access_validator.iter_errors(invalid)):
            raise ValueError(f"Invalid fixture {name} unexpectedly passed its schema")
    mismatch = _load("fixtures/invalid/provider-auth-mismatch.json")
    access_validator.validate(mismatch)
    try:
        for surface in mismatch["surfaces"]:
            validate_surface(surface)
    except ValueError:
        pass
    else:
        raise ValueError("Provider/auth mismatch fixture unexpectedly passed semantic validation")
    return _tree_digest(_documents(SOURCE_ROOT))


def synchronize() -> str:
    digest = validate_source()
    for target in TARGETS:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(SOURCE_ROOT, target, ignore=shutil.ignore_patterns(".DS_Store"))
        (target / ".contract-sha256").write_text(f"{digest}\n", encoding="utf-8")
    return digest


def check() -> str:
    digest = validate_source()
    source_files = _documents(SOURCE_ROOT)
    failures: list[str] = []
    for target in TARGETS:
        if not target.is_dir():
            failures.append(f"missing target {target.relative_to(REPO_ROOT)}")
            continue
        if _documents(target) != source_files:
            failures.append(f"content drift in {target.relative_to(REPO_ROOT)}")
        digest_file = target / ".contract-sha256"
        if not digest_file.is_file() or digest_file.read_text(encoding="utf-8").strip() != digest:
            failures.append(f"digest drift in {target.relative_to(REPO_ROOT)}")
    if failures:
        raise ValueError("; ".join(failures))
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        digest = check() if args.check else synchronize()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"deployment-access-contracts: ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "deployment-access-contracts: OK "
        f"(source_digest={digest}, placements=9, generated_copies={len(TARGETS)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
