#!/usr/bin/env python3
"""Validate and synchronize the canonical user-function extension contracts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "contracts" / "user-function-extension"
TARGETS = (
    REPO_ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "user-function-extension",
    REPO_ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "user-function-extension",
    REPO_ROOT
    / "twin2multicloud_flutter"
    / "assets"
    / "contracts"
    / "user-function-extension",
)
IGNORED_NAMES = {"__pycache__", ".DS_Store", ".contract-sha256"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_NAMES for part in path.relative_to(root).parts)
        and path.suffix not in IGNORED_SUFFIXES
    )


def _tree_digest(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in _files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        hasher.update(len(relative).to_bytes(4, "big"))
        hasher.update(relative)
        hasher.update(len(payload).to_bytes(8, "big"))
        hasher.update(payload)
    return f"sha256:{hasher.hexdigest()}"


def _load_runtime():
    target = SOURCE_ROOT / "v1" / "runtime.py"
    spec = importlib.util.spec_from_file_location(
        "canonical_user_function_extension_runtime",
        target,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load canonical extension runtime.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(REPO_ROOT)} must contain a JSON object")
    return value


def validate_source() -> str:
    required = (
        "README.md",
        "v1/extension-slot.schema.json",
        "v1/artifact-manifest.schema.json",
        "v1/runtime-envelope.schema.json",
        "v1/registry.json",
        "v1/runtime.py",
        "v1/examples/processor-slot.json",
        "v1/examples/valid-artifact.json",
        "v1/examples/valid-runtime-input.json",
        "v1/examples/valid-runtime-success.json",
        "v1/examples/source/valid/process.py",
        "v1/examples/source/valid/requirements.lock",
    )
    missing = [relative for relative in required if not (SOURCE_ROOT / relative).is_file()]
    if missing:
        raise ValueError(f"Missing canonical extension files: {', '.join(missing)}")

    for schema_path in sorted((SOURCE_ROOT / "v1").glob("*.schema.json")):
        Draft202012Validator.check_schema(_load_json(schema_path))

    runtime = _load_runtime()
    registry = runtime.load_registry()
    slot = _load_json(SOURCE_ROOT / "v1" / "examples" / "processor-slot.json")
    runtime.validate_extension_slot(slot)
    registered = runtime.get_slot(slot["slot_id"], slot["slot_version"])
    if runtime.canonical_json(slot) != runtime.canonical_json(registered):
        raise ValueError("Processor slot fixture must be byte-semantic registry content.")

    for name in ("valid-runtime-input.json", "valid-runtime-success.json"):
        runtime.validate_runtime_envelope(
            _load_json(SOURCE_ROOT / "v1" / "examples" / name),
            slot=slot,
        )

    manifest = _load_json(SOURCE_ROOT / "v1" / "examples" / "valid-artifact.json")
    runtime.validate_artifact_manifest(manifest)
    if registry["runtime"]["runtime_id"] != runtime.RUNTIME_ID:
        raise ValueError("Registry and runtime identifiers diverged.")
    return _tree_digest(SOURCE_ROOT)


def synchronize() -> str:
    digest = validate_source()
    for target in TARGETS:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            SOURCE_ROOT,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"),
        )
        (target / ".contract-sha256").write_text(f"{digest}\n", encoding="utf-8")
    return digest


def check() -> str:
    digest = validate_source()
    source_files = {
        path.relative_to(SOURCE_ROOT).as_posix(): path.read_bytes()
        for path in _files(SOURCE_ROOT)
    }
    failures: list[str] = []
    for target in TARGETS:
        if not target.is_dir():
            failures.append(f"missing target {target.relative_to(REPO_ROOT)}")
            continue
        target_files = {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in _files(target)
        }
        if target_files != source_files:
            failures.append(f"content drift in {target.relative_to(REPO_ROOT)}")
        digest_file = target / ".contract-sha256"
        if not digest_file.is_file() or digest_file.read_text(encoding="utf-8").strip() != digest:
            failures.append(f"digest drift in {target.relative_to(REPO_ROOT)}")
    if failures:
        raise ValueError("; ".join(failures))
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated copies differ instead of rewriting them.",
    )
    args = parser.parse_args()
    try:
        digest = check() if args.check else synchronize()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"user-function-extension-contracts: ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "user-function-extension-contracts: OK "
        f"(source_digest={digest}, generated_copies={len(TARGETS)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
