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
PERMISSION_SET_ROOT = (
    REPO_ROOT / "3-cloud-deployer" / "docs" / "references" / "permission_sets"
)
AUTHORITY_PACK_SOURCES = {
    "v1/authority-packs/aws.json": PERMISSION_SET_ROOT / "aws_bootstrap_admin_v2.json",
    "v1/authority-packs/azure.json": PERMISSION_SET_ROOT
    / "azure_bootstrap_admin_v2.json",
    "v1/authority-packs/gcp.json": PERMISSION_SET_ROOT / "gcp_bootstrap_admin_v2.json",
}
DEPLOYMENT_PACK_SOURCES = {
    f"v1/deployment-packs/{provider}.json": PERMISSION_SET_ROOT
    / f"{provider}_thesis_demo_v2.json"
    for provider in ("aws", "azure", "gcp")
}
DEPLOYMENT_IDENTITY_BINDINGS = {
    provider: SOURCE_ROOT
    / "v1"
    / "deployment-identity-bindings"
    / f"{provider}.json"
    for provider in ("aws", "azure")
}
TARGETS = (
    REPO_ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "cloud-bootstrap",
    REPO_ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "cloud-bootstrap",
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


def _source_documents() -> dict[str, bytes]:
    documents = {
        path.relative_to(SOURCE_ROOT).as_posix(): path.read_bytes()
        for path in _files(SOURCE_ROOT)
    }
    for relative, path in {**AUTHORITY_PACK_SOURCES, **DEPLOYMENT_PACK_SOURCES}.items():
        documents[relative] = path.read_bytes()
    return documents


def _tree_digest(documents: dict[str, bytes]) -> str:
    hasher = hashlib.sha256()
    for name, payload in sorted(documents.items()):
        relative = name.encode("utf-8")
        hasher.update(len(relative).to_bytes(4, "big"))
        hasher.update(relative)
        hasher.update(len(payload).to_bytes(8, "big"))
        hasher.update(payload)
    return f"sha256:{hasher.hexdigest()}"


def _document_digest(document: dict) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def validate_source() -> str:
    required = {
        "README.md",
        "v1/bootstrap-authority-pack.schema.json",
        "v1/deployment-identity-binding.schema.json",
        "v1/cloud-bootstrap-guide.schema.json",
        "v1/cloud-bootstrap-session.schema.json",
        "v1/deployment-identity-bindings/aws.json",
        "v1/deployment-identity-bindings/azure.json",
        "v1/fixtures/valid/aws-guide.json",
        "v1/fixtures/valid/aws-ready-session.json",
        "v1/fixtures/invalid/guide-secret-value.json",
        "v1/fixtures/invalid/session-secret-value.json",
    }
    present = {path.relative_to(SOURCE_ROOT).as_posix() for path in _files(SOURCE_ROOT)}
    missing = sorted(required - present)
    if missing:
        raise ValueError(
            f"Missing canonical cloud-bootstrap files: {', '.join(missing)}"
        )
    schemas: dict[str, dict] = {}
    for path in sorted((SOURCE_ROOT / "v1").glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(document)
        schemas[path.name] = document
    authority_validator = Draft202012Validator(
        schemas["bootstrap-authority-pack.schema.json"]
    )
    for provider, path in zip(
        ("aws", "azure", "gcp"), AUTHORITY_PACK_SOURCES.values(), strict=True
    ):
        document = json.loads(path.read_text(encoding="utf-8"))
        authority_validator.validate(document)
        if document["provider"] != provider:
            raise ValueError(
                f"Authority pack provider mismatch: {path.relative_to(REPO_ROOT)}"
            )
    for provider, path in zip(
        ("aws", "azure", "gcp"), DEPLOYMENT_PACK_SOURCES.values(), strict=True
    ):
        document = json.loads(path.read_text(encoding="utf-8"))
        if (
            document.get("provider") != provider
            or document.get("permission_set_version") != "thesis-demo-v2"
        ):
            raise ValueError(f"Deployment pack mismatch: {path.relative_to(REPO_ROOT)}")
        if provider in DEPLOYMENT_IDENTITY_BINDINGS:
            binding_path = DEPLOYMENT_IDENTITY_BINDINGS[provider]
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            Draft202012Validator(
                schemas["deployment-identity-binding.schema.json"]
            ).validate(binding)
            if (
                binding["provider"] != provider
                or binding["permission_set_version"]
                != document["permission_set_version"]
                or binding["base_pack_digest"] != _document_digest(document)
                or not binding["self_check_permissions"]
                or len(binding["self_check_permissions"])
                != len(set(binding["self_check_permissions"]))
            ):
                raise ValueError(
                    f"{provider.upper()} deployment identity binding does not "
                    "match the frozen "
                    "deployment pack or implemented CloudConnection path"
                )
            expected_identity = {
                "aws": ("iam_user", "access_key", "customer_managed_policy"),
                "azure": (
                    "service_principal",
                    "client_secret",
                    "custom_role_assignment",
                ),
            }[provider]
            if (
                binding["identity_kind"],
                binding["connection_auth_type"],
                binding["policy_attachment_kind"],
            ) != expected_identity:
                raise ValueError(
                    f"{provider.upper()} deployment identity binding does not "
                    "match the implemented CloudConnection path"
                )
    guide_schema = json.loads(
        (SOURCE_ROOT / "v1" / "cloud-bootstrap-guide.schema.json").read_text(
            encoding="utf-8"
        )
    )
    session_schema = json.loads(
        (SOURCE_ROOT / "v1" / "cloud-bootstrap-session.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validators = {
        "aws-guide.json": Draft202012Validator(guide_schema),
        "aws-ready-session.json": Draft202012Validator(session_schema),
    }
    for name, validator in validators.items():
        document = json.loads(
            (SOURCE_ROOT / "v1" / "fixtures" / "valid" / name).read_text(
                encoding="utf-8"
            )
        )
        errors = sorted(
            validator.iter_errors(document), key=lambda error: list(error.path)
        )
        if errors:
            raise ValueError(f"Valid fixture {name} failed: {errors[0].message}")
        if name == "aws-guide.json":
            declared = document.pop("guide_digest")
            calculated = (
                "sha256:"
                + hashlib.sha256(
                    json.dumps(
                        document,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest()
            )
            if declared != calculated:
                raise ValueError(
                    "Valid guide fixture digest does not match its content"
                )
    guide_fixture = json.loads(
        (SOURCE_ROOT / "v1" / "fixtures" / "valid" / "aws-guide.json").read_text(
            encoding="utf-8"
        )
    )
    session_fixture = json.loads(
        (
            SOURCE_ROOT / "v1" / "fixtures" / "valid" / "aws-ready-session.json"
        ).read_text(encoding="utf-8")
    )
    if (
        session_fixture.get("guide_digest") != guide_fixture.get("guide_digest")
        or session_fixture.get("bootstrap_authority_pack")
        != {
            key: guide_fixture["bootstrap_authority_pack"][key]
            for key in ("id", "version", "digest")
        }
        or session_fixture.get("generated_deployment_pack")
        != {
            key: guide_fixture["generated_deployment_pack"][key]
            for key in ("id", "version", "digest")
        }
    ):
        raise ValueError(
            "Valid AWS guide and ready-session fixtures do not pin one contract"
        )
    invalid = {
        "guide-secret-value.json": Draft202012Validator(guide_schema),
        "session-secret-value.json": Draft202012Validator(session_schema),
    }
    for name, validator in invalid.items():
        document = json.loads(
            (SOURCE_ROOT / "v1" / "fixtures" / "invalid" / name).read_text(
                encoding="utf-8"
            )
        )
        if not list(validator.iter_errors(document)):
            raise ValueError(f"Invalid fixture {name} unexpectedly passed")
    return _tree_digest(_source_documents())


def synchronize() -> str:
    digest = validate_source()
    for target in TARGETS:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(SOURCE_ROOT, target, ignore=shutil.ignore_patterns(".DS_Store"))
        for relative, source in {
            **AUTHORITY_PACK_SOURCES,
            **DEPLOYMENT_PACK_SOURCES,
        }.items():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (target / ".contract-sha256").write_text(f"{digest}\n", encoding="utf-8")
    return digest


def check() -> str:
    digest = validate_source()
    source_files = _source_documents()
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
        if (
            not digest_file.is_file()
            or digest_file.read_text(encoding="utf-8").strip() != digest
        ):
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
