#!/usr/bin/env python3
"""Validate and synchronize the repository-owned DeploymentManifest v3 contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "contracts" / "deployment-manifest"
SOURCE_V3 = SOURCE_ROOT / "v3"
SCHEMA_PATH = SOURCE_V3 / "schema.json"
VALID_ROOT = SOURCE_V3 / "fixtures" / "valid"
INVALID_ROOT = SOURCE_V3 / "fixtures" / "invalid"
TARGETS = (
    ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest",
    ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest",
)
EXPECTED_VALID = frozenset(
    {"all-aws.json", "all-azure.json", "mixed-providers.json"}
)


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read JSON contract file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _source_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in SOURCE_V3.rglob("*")
            if path.is_file() and path.name != ".contract-sha256"
        )
    )


def _tree_digest() -> str:
    entries = [
        {
            "path": path.relative_to(SOURCE_V3).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in _source_files()
    ]
    return f"sha256:{hashlib.sha256(canonical_json(entries).encode()).hexdigest()}"


def validate_source() -> str:
    schema = _read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid_names = {path.name for path in VALID_ROOT.glob("*.json")}
    if valid_names != EXPECTED_VALID:
        raise RuntimeError(
            "DeploymentManifest valid fixtures must be exactly "
            f"{sorted(EXPECTED_VALID)}"
        )
    for path in sorted(VALID_ROOT.glob("*.json")):
        errors = sorted(
            validator.iter_errors(_read_json(path)),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        if errors:
            location = ".".join(str(part) for part in errors[0].absolute_path)
            raise RuntimeError(
                f"{path.name} is invalid at {location or '$'}: {errors[0].message}"
            )
    for path in sorted(INVALID_ROOT.glob("*.json")):
        wrapper = _read_json(path)
        manifest = wrapper.get("manifest")
        if not isinstance(manifest, dict) or not list(
            validator.iter_errors(manifest)
        ):
            raise RuntimeError(f"{path.name} must contain an invalid manifest")
    return _tree_digest()


def synchronize() -> str:
    digest = validate_source()
    for target in TARGETS:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(SOURCE_ROOT, target)
        (target / ".contract-sha256").write_text(
            f"{digest}\n",
            encoding="utf-8",
        )
    return digest


def check() -> str:
    digest = validate_source()
    for target in TARGETS:
        marker = target / ".contract-sha256"
        if not marker.exists() or marker.read_text(encoding="utf-8").strip() != digest:
            raise RuntimeError(f"DeploymentManifest contract marker drift: {target}")
        for source in _source_files():
            relative = source.relative_to(SOURCE_ROOT)
            generated = target / relative
            if not generated.exists() or generated.read_bytes() != source.read_bytes():
                raise RuntimeError(
                    f"DeploymentManifest generated copy drift: {generated}"
                )
        generated_files = {
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file() and path.name != ".contract-sha256"
        }
        expected_files = {
            path.relative_to(SOURCE_ROOT).as_posix()
            for path in _source_files()
        }
        if generated_files != expected_files:
            raise RuntimeError(f"DeploymentManifest generated file-set drift: {target}")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated copies differ from canonical source.",
    )
    args = parser.parse_args()
    digest = check() if args.check else synchronize()
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
