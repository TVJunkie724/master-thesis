#!/usr/bin/env python3
"""Validate, synchronize, and drift-check the standalone Six-layer contracts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
ARCH_ROOT = ROOT / "contracts" / "architecture-profiles"
ARCH_V2 = ARCH_ROOT / "v2"
DEFINITIONS = ARCH_ROOT / "definitions"
RDS_ROOT = ROOT / "contracts" / "resolved-deployment-specification"
RDS_V2 = RDS_ROOT / "v2"
MANIFEST_ROOT = ROOT / "contracts" / "deployment-manifest"
MANIFEST_V4 = MANIFEST_ROOT / "v4"
PROFILE_PATH = DEFINITIONS / "profiles" / "six-layer-eventing" / "1" / "profile.json"
CATALOG_PATH = (
    DEFINITIONS / "component-catalogs" / "six-layer-eventing" / "1" / "catalog.json"
)
DEFINITION_MANIFEST_PATH = DEFINITIONS / "six-layer-eventing-v1-manifest.json"
RTA_PATH = ARCH_V2 / "fixtures" / "valid" / "six-layer-aws-azure-eventing-small-resolved.json"
RDS_PATH = RDS_V2 / "fixtures" / "valid" / "six-layer-aws-azure-eventing-small.json"
DEPLOYMENT_MANIFEST_PATH = (
    MANIFEST_V4 / "fixtures" / "valid" / "six-layer-aws-azure-eventing-small.json"
)
PROVIDERS = ("aws", "azure", "gcp")
ARCH_TARGETS = (
    ROOT / "2-twin2clouds" / "backend" / "contracts" / "generated" / "architecture-profiles",
    ROOT / "twin2multicloud_backend" / "src" / "contracts" / "generated" / "architecture-profiles",
    ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated" / "architecture-profiles",
)
RDS_TARGETS = (
    ROOT / "2-twin2clouds" / "backend" / "contracts" / "generated" / "resolved-deployment-specification",
    ROOT / "twin2multicloud_backend" / "src" / "contracts" / "generated" / "resolved-deployment-specification",
    ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated" / "resolved-deployment-specification",
)
MANIFEST_TARGETS = (
    ROOT / "twin2multicloud_backend" / "src" / "contracts" / "generated" / "deployment-manifest",
    ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated" / "deployment-manifest",
)
FLUTTER_DEMO_ROOT = ROOT / "twin2multicloud_flutter" / "assets" / "demo" / "v1"


def _provider_path(provider: str) -> Path:
    return (
        DEFINITIONS
        / "provider-implementations"
        / "six-layer-eventing"
        / "1"
        / provider
        / "1.json"
    )


FLUTTER_ASSETS = {
    "architecture-profile-six-layer-v1.json": PROFILE_PATH,
    **{
        f"provider-profile-six-layer-v1-{provider}.json": _provider_path(provider)
        for provider in PROVIDERS
    },
    "resolved-twin-architecture-six-layer-v1.json": RTA_PATH,
    "resolved-deployment-specification-six-layer-v1.json": RDS_PATH,
    "deployment-manifest-six-layer-v1.json": DEPLOYMENT_MANIFEST_PATH,
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def _load_runtime() -> ModuleType:
    path = ARCH_V2 / "runtime.py"
    spec = importlib.util.spec_from_file_location("six_layer_sync_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load architecture contract runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNTIME = _load_runtime()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


def _rds_digest(document: dict[str, Any]) -> str:
    value = dict(document)
    value.pop("digest", None)
    return _digest(value)


def _tree_digest(root: Path) -> str:
    entries = [
        (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".contract-sha256" and "__pycache__" not in path.parts
    ]
    return _digest(entries)


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def validate_source() -> None:
    for path in sorted(ARCH_V2.glob("*.schema.json")):
        Draft202012Validator.check_schema(_read(path))
    Draft202012Validator.check_schema(_read(RDS_V2 / "schema.json"))
    Draft202012Validator.check_schema(_read(MANIFEST_V4 / "schema.json"))

    registry = _read(ARCH_V2 / "semantic-registry.json")
    profile = _read(PROFILE_PATH)
    catalog = _read(CATALOG_PATH)
    providers = {provider: _read(_provider_path(provider)) for provider in PROVIDERS}
    rta = _read(RTA_PATH)
    linked = [registry, profile, *providers.values(), catalog, rta]
    RUNTIME.validate_bundle(linked, bundle_root=ARCH_V2)

    if profile["profile_id"] != "six-layer-eventing" or profile["profile_version"] != "1":
        raise RuntimeError("Six-layer must be the sole architecture profile")
    if len(profile["responsibilities"]) != 6 or len(profile["components"]) != 8:
        raise RuntimeError("Six-layer logical profile is incomplete")
    if profile["workload_contract_ref"] != {
        "id": "six-layer-workload",
        "version": "1",
        "digest": "sha256:51745c9efac65afd11fdd10c0a74b60c4443d0ba65a97a1647b736eadc01b7f5",
    }:
        raise RuntimeError("Six-layer workload reference drifted")

    definition_manifest = _read(DEFINITION_MANIFEST_PATH)
    if any(key.startswith("inherited_") for key in definition_manifest):
        raise RuntimeError("Standalone Six-layer manifest must not inherit another profile")
    supplied_manifest_digest = definition_manifest["content_digest"]
    if supplied_manifest_digest != RUNTIME.calculate_digest(definition_manifest):
        raise RuntimeError("Six-layer definition manifest digest drifted")
    if definition_manifest["profile_ref"]["digest"] != profile["content_digest"]:
        raise RuntimeError("Six-layer manifest profile reference drifted")
    if definition_manifest["catalog_ref"]["digest"] != catalog["content_digest"]:
        raise RuntimeError("Six-layer manifest catalog reference drifted")

    capacity_registry = _read(RDS_V2 / "component-capacity-registry.json")
    supplied_capacity_digest = capacity_registry["content_digest"]
    capacity_registry["content_digest"] = ""
    if supplied_capacity_digest != _digest(capacity_registry):
        raise RuntimeError("Six-layer capacity registry digest drifted")

    rds = _read(RDS_PATH)
    rds_errors = list(
        Draft202012Validator(
            _read(RDS_V2 / "schema.json"), format_checker=FormatChecker()
        ).iter_errors(rds)
    )
    if rds_errors or rds["digest"] != _rds_digest(rds):
        raise RuntimeError("Six-layer RDS fixture is invalid")
    if rta["deployment_specification_ref"]["digest"] != rds["digest"]:
        raise RuntimeError("Six-layer RTA does not reference the canonical RDS")

    deployment_manifest = _read(DEPLOYMENT_MANIFEST_PATH)
    manifest_errors = list(
        Draft202012Validator(
            _read(MANIFEST_V4 / "schema.json"), format_checker=FormatChecker()
        ).iter_errors(deployment_manifest)
    )
    if manifest_errors:
        raise RuntimeError(
            "Six-layer deployment manifest is invalid: "
            + manifest_errors[0].message
        )
    if (
        deployment_manifest["resolved_twin_architecture"] != rta
        or deployment_manifest["resolved_twin_architecture_digest"]
        != rta["content_digest"]
        or deployment_manifest["resolved_deployment_specification"] != rds
        or deployment_manifest["resolved_deployment_specification_digest"]
        != rds["digest"]
    ):
        raise RuntimeError("Six-layer deployment manifest embeds stale evidence")

    forbidden = (
        "five-layer-baseline",
        "five-layer-v2",
        "five_layer_v2",
        "aws_thesis_demo",
        "azure_thesis_demo",
        "gcp_thesis_demo",
        "bootstrap_admin",
    )
    for root in (ARCH_ROOT, RDS_ROOT, MANIFEST_ROOT):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".json", ".md", ".py"}:
                text = path.read_text(encoding="utf-8")
                if any(token in text for token in forbidden):
                    raise RuntimeError(
                        f"Removed architecture or credential identity remains: {path}"
                    )


def _copy_tree(source: Path, targets: tuple[Path, ...]) -> None:
    marker = _tree_digest(source)
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (target / ".contract-sha256").write_text(marker + "\n", encoding="utf-8")


def synchronize() -> None:
    _copy_tree(ARCH_ROOT, ARCH_TARGETS)
    _copy_tree(RDS_ROOT, RDS_TARGETS)
    _copy_tree(MANIFEST_ROOT, MANIFEST_TARGETS)
    FLUTTER_DEMO_ROOT.mkdir(parents=True, exist_ok=True)
    for name, source in FLUTTER_ASSETS.items():
        shutil.copy2(source, FLUTTER_DEMO_ROOT / name)


def _check_tree(source: Path, targets: tuple[Path, ...]) -> None:
    expected = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file() and path.name != ".contract-sha256" and "__pycache__" not in path.parts
    }
    marker = _tree_digest(source)
    for target in targets:
        actual = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file() and path.name != ".contract-sha256" and "__pycache__" not in path.parts
        }
        if actual != expected:
            raise RuntimeError(f"Generated contract copy drifted: {target}")
        if (target / ".contract-sha256").read_text(encoding="utf-8").strip() != marker:
            raise RuntimeError(f"Generated contract marker drifted: {target}")


def check() -> None:
    validate_source()
    _check_tree(ARCH_ROOT, ARCH_TARGETS)
    _check_tree(RDS_ROOT, RDS_TARGETS)
    _check_tree(MANIFEST_ROOT, MANIFEST_TARGETS)
    for name, source in FLUTTER_ASSETS.items():
        target = FLUTTER_DEMO_ROOT / name
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"Generated Flutter Six-layer asset drifted: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.sync or args.check):
        parser.error("at least one action is required")
    try:
        validate_source()
        if args.sync:
            synchronize()
        if args.check:
            check()
    except (RuntimeError, RUNTIME.ContractError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "six-layer-contracts: OK "
        f"(architecture={_tree_digest(ARCH_ROOT)}, rds={_tree_digest(RDS_ROOT)}, "
        f"manifest={_tree_digest(MANIFEST_ROOT)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
