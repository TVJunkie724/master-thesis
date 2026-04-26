#!/usr/bin/env python3
"""Report repository hygiene issues without reading secret file contents."""

from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    message: str


FORBIDDEN_PATH_PATTERNS = {
    "root-credential": [
        "config_credentials.json",
        "gcp_credentials.json",
        "google-credentials.json",
    ],
    "upload-credential": [
        "3-cloud-deployer/upload/**/config_credentials.json",
        "3-cloud-deployer/upload/**/gcp_credentials.json",
        "3-cloud-deployer/upload/**/google-credentials.json",
    ],
    "upload-runtime-state": [
        "3-cloud-deployer/upload/*/terraform.tfstate",
        "3-cloud-deployer/upload/*/terraform.tfstate.backup",
        "3-cloud-deployer/upload/*/versions",
        "3-cloud-deployer/upload/*/.build",
        "3-cloud-deployer/upload/*/.terraform_zips",
        "3-cloud-deployer/upload/*/terraform/generated.tfvars.json",
    ],
    "local-artifact": [
        ".DS_Store",
        "**/.DS_Store",
        "3-cloud-deployer/upload/template/Archive.zip",
    ],
}


LEGACY_BACKLOG_FILES = [
    "TODOS.md",
    "integration_todo.md",
    "docs/future-work.md",
    "2-twin2clouds/TODOs.md",
    "3-cloud-deployer/TODOs.md",
    "twin2multicloud_backend/docs/TODO_infrastructure_deployment.md",
    "twin2multicloud_flutter/docs/TODO_infrastructure_deployment.md",
    "2-twin2clouds/docs/docs-future-work.html",
    "3-cloud-deployer/docs/future-work-resolved.md",
    "3-cloud-deployer/implementation_plans/2025-12-11_azure_hot_reader_future_work.md",
    "3-cloud-deployer/implementation_plans/2025-12-11_gcp_hot_reader_future_work.md",
]


SERVICE_HTML_DOC_PATTERNS = [
    "2-twin2clouds/docs/*.html",
    "3-cloud-deployer/docs/*.html",
]


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def iter_paths() -> Iterable[Path]:
    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        yield path


def matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern)


def scan_forbidden_paths() -> list[Finding]:
    findings: list[Finding] = []
    paths = list(iter_paths())

    for category, patterns in FORBIDDEN_PATH_PATTERNS.items():
        for pattern in patterns:
            for path in paths:
                relative = rel(path)
                if matches(relative, pattern):
                    findings.append(
                        Finding(
                            severity="error",
                            category=category,
                            path=relative,
                            message="Forbidden workspace artifact is present.",
                        )
                    )
    return sorted(set(findings), key=lambda item: (item.category, item.path))


def scan_legacy_backlog_files() -> list[Finding]:
    findings: list[Finding] = []
    for relative in LEGACY_BACKLOG_FILES:
        path = REPO_ROOT / relative
        if path.exists():
            findings.append(
                Finding(
                    severity="warning",
                    category="legacy-backlog",
                    path=relative,
                    message=(
                        "Legacy TODO/future-work source still exists. "
                        "GitHub Issues and Milestones are the active backlog."
                    ),
                )
            )
    return findings


def scan_service_html_docs() -> list[Finding]:
    findings: list[Finding] = []
    paths = [rel(path) for path in iter_paths() if path.is_file()]
    for pattern in SERVICE_HTML_DOC_PATTERNS:
        for relative in paths:
            if matches(relative, pattern):
                findings.append(
                    Finding(
                        severity="warning",
                        category="service-html-doc",
                        path=relative,
                        message=(
                            "Service-local HTML documentation should be migrated "
                            "or archived after docs-site becomes canonical."
                        ),
                    )
                )
    return sorted(findings, key=lambda item: item.path)


def collect_findings() -> list[Finding]:
    return [
        *scan_forbidden_paths(),
        *scan_legacy_backlog_files(),
        *scan_service_html_docs(),
    ]


def print_text(findings: list[Finding]) -> None:
    if not findings:
        print("Repo hygiene check passed: no findings.")
        return

    errors = sum(1 for item in findings if item.severity == "error")
    warnings = sum(1 for item in findings if item.severity == "warning")
    print(f"Repo hygiene findings: {errors} error(s), {warnings} warning(s)")
    print()

    for finding in findings:
        print(f"[{finding.severity.upper()}] {finding.category}: {finding.path}")
        print(f"  {finding.message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["report", "enforce"],
        default="report",
        help="report exits 0 with findings; enforce exits non-zero on error findings.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = collect_findings()

    if args.format == "json":
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        print_text(findings)

    has_errors = any(finding.severity == "error" for finding in findings)
    return 1 if args.mode == "enforce" and has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
