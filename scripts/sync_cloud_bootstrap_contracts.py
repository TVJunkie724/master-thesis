#!/usr/bin/env python3
"""Validate and synchronize the canonical guided-bootstrap contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "contracts" / "cloud-bootstrap"
TARGETS = (
    REPO_ROOT / "twin2multicloud_backend" / "src" / "contracts" / "generated" / "cloud-bootstrap",
    REPO_ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated" / "cloud-bootstrap",
    REPO_ROOT / "twin2multicloud_flutter" / "assets" / "contracts" / "cloud-bootstrap",
)
IGNORED_NAMES = {".DS_Store", ".contract-sha256", "__pycache__"}


def _files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_NAMES for part in path.relative_to(root).parts)
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


def validate_source() -> str:
    required = {
        "README.md",
        "v1/bootstrap-authority-pack.schema.json",
        "v1/cloud-bootstrap-guide.schema.json",
        "v1/cloud-bootstrap-session.schema.json",
        "v1/fixtures/valid/aws-guide.json",
        "v1/fixtures/valid/aws-ready-session.json",
        "v1/fixtures/invalid/guide-secret-value.json",
        "v1/fixtures/invalid/session-secret-value.json",
    }
    present = {path.relative_to(SOURCE_ROOT).as_posix() for path in _files(SOURCE_ROOT)}
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"Missing canonical cloud-bootstrap files: {', '.join(missing)}")
    for path in sorted((SOURCE_ROOT / "v1").glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(document)
    guide_schema = json.loads(
        (SOURCE_ROOT / "v1" / "cloud-bootstrap-guide.schema.json").read_text(encoding="utf-8")
    )
    session_schema = json.loads(
        (SOURCE_ROOT / "v1" / "cloud-bootstrap-session.schema.json").read_text(encoding="utf-8")
    )
    validators = {
        "aws-guide.json": Draft202012Validator(guide_schema),
        "aws-ready-session.json": Draft202012Validator(session_schema),
    }
    for name, validator in validators.items():
        document = json.loads(
            (SOURCE_ROOT / "v1" / "fixtures" / "valid" / name).read_text(encoding="utf-8")
        )
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        if errors:
            raise ValueError(f"Valid fixture {name} failed: {errors[0].message}")
    invalid = {
        "guide-secret-value.json": Draft202012Validator(guide_schema),
        "session-secret-value.json": Draft202012Validator(session_schema),
    }
    for name, validator in invalid.items():
        document = json.loads(
            (SOURCE_ROOT / "v1" / "fixtures" / "invalid" / name).read_text(encoding="utf-8")
        )
        if not list(validator.iter_errors(document)):
            raise ValueError(f"Invalid fixture {name} unexpectedly passed")
    return _tree_digest(SOURCE_ROOT)


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
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        digest = check() if args.check else synchronize()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cloud-bootstrap-contracts: ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "cloud-bootstrap-contracts: OK "
        f"(source_digest={digest}, generated_copies={len(TARGETS)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
