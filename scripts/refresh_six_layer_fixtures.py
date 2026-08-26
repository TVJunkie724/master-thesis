#!/usr/bin/env python3
"""Refresh the sole Six-layer RTA, RDS, and deployment-manifest fixtures."""

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
FIXTURE_ID = "six-layer-aws-azure-eventing-small"
RTA_PATH = ARCH_ROOT / "v2" / "fixtures" / "valid" / f"{FIXTURE_ID}-resolved.json"
RDS_PATH = (
    ROOT
    / "contracts"
    / "resolved-deployment-specification"
    / "v2"
    / "fixtures"
    / "valid"
    / f"{FIXTURE_ID}.json"
)
MANIFEST_PATH = (
    ROOT
    / "contracts"
    / "deployment-manifest"
    / "v4"
    / "fixtures"
    / "valid"
    / f"{FIXTURE_ID}.json"
)
WORKLOAD_DIGEST = "sha256:51745c9efac65afd11fdd10c0a74b60c4443d0ba65a97a1647b736eadc01b7f5"
PROVIDERS = ("aws", "azure", "gcp")


def _load_runtime() -> ModuleType:
    path = ARCH_ROOT / "v2" / "runtime.py"
    spec = importlib.util.spec_from_file_location("six_layer_fixture_runtime", path)
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


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _rds_digest(document: dict[str, Any]) -> str:
    value = dict(document)
    value.pop("digest", None)
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


def _replace_refs(
    value: object,
    *,
    profile: dict[str, Any],
    catalog: dict[str, Any],
    providers: dict[str, dict[str, Any]],
) -> object:
    if isinstance(value, dict):
        result = {
            key: _replace_refs(
                nested,
                profile=profile,
                catalog=catalog,
                providers=providers,
            )
            for key, nested in value.items()
        }
        identity = result.get("id")
        if identity == "six-layer-eventing" and "digest" in result:
            result.update(version="1", digest=profile["content_digest"])
        elif identity == "six-layer-eventing-component-catalog" and "digest" in result:
            result.update(version="1", digest=catalog["content_digest"])
        elif identity == "six-layer-workload" and "digest" in result:
            result.update(version="1", digest=WORKLOAD_DIGEST)
        else:
            for document in providers.values():
                if identity == document["implementation_profile_id"] and "digest" in result:
                    result.update(
                        version=document["implementation_profile_version"],
                        digest=document["content_digest"],
                    )
                    break
        return result
    if isinstance(value, list):
        return [
            _replace_refs(item, profile=profile, catalog=catalog, providers=providers)
            for item in value
        ]
    if isinstance(value, str):
        return value
    return value


def main() -> int:
    profile = _read(
        DEFINITIONS / "profiles" / "six-layer-eventing" / "1" / "profile.json"
    )
    catalog = _read(
        DEFINITIONS
        / "component-catalogs"
        / "six-layer-eventing"
        / "1"
        / "catalog.json"
    )
    providers = {
        provider: _read(
            DEFINITIONS
            / "provider-implementations"
            / "six-layer-eventing"
            / "1"
            / provider
            / "1.json"
        )
        for provider in PROVIDERS
    }

    rds = _replace_refs(
        _read(RDS_PATH), profile=profile, catalog=catalog, providers=providers
    )
    assert isinstance(rds, dict)
    rds["digest"] = _rds_digest(rds)
    _write(RDS_PATH, rds)

    rta = _replace_refs(
        _read(RTA_PATH), profile=profile, catalog=catalog, providers=providers
    )
    assert isinstance(rta, dict)
    rta["optimization_bundle_ref"] = {
        key: value
        for key, value in profile["optimization_bundle"].items()
        if key
        in {
            "optimization_strategy_id",
            "optimization_strategy_version",
            "calculation_strategy_id",
            "calculation_strategy_version",
            "formula_set_id",
            "formula_set_version",
            "scoring_strategy_id",
            "scoring_strategy_version",
            "compatibility_digest",
        }
    }
    rta["deployment_specification_ref"]["digest"] = rds["digest"]
    validation_payload = {
        "capabilities": sorted(
            capability
            for component in profile["components"]
            for capability in component["required_capability_ids"]
        ),
        "profile_digest": profile["content_digest"],
        "catalog_digest": catalog["content_digest"],
    }
    rta["functional_completeness"]["validation_digest"] = (
        f"sha256:{hashlib.sha256(_canonical_json(validation_payload).encode()).hexdigest()}"
    )
    rta["resolution_id"] = RUNTIME.calculate_resolution_id(rta)
    rta["content_digest"] = RUNTIME.calculate_digest(rta)
    _write(RTA_PATH, rta)

    manifest = _replace_refs(
        _read(MANIFEST_PATH), profile=profile, catalog=catalog, providers=providers
    )
    assert isinstance(manifest, dict)
    manifest["resolved_twin_architecture"] = rta
    manifest["resolved_twin_architecture_digest"] = rta["content_digest"]
    manifest["resolved_deployment_specification"] = rds
    manifest["resolved_deployment_specification_digest"] = rds["digest"]
    _write(MANIFEST_PATH, manifest)

    print(
        "six-layer-fixtures: OK "
        f"(rta={rta['content_digest']}, rds={rds['digest']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
