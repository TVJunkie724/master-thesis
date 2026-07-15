#!/usr/bin/env python3
"""Fail-closed architecture and secret-surface checks for the Flutter app."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, order=True)
class Finding:
    rule_id: str
    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"{self.rule_id} {self.path}:{self.line} {self.message}"


_DIRECT_SERVICE = re.compile(
    r"(?:https?://[^\s'\"]*:(?:5003|5004)\b|localhost:(?:5003|5004)\b)"
)
_PRESENTATION_HTTP = re.compile(
    r"(?:package:dio/dio\.dart|services/(?:api_service|management_api)\.dart|"
    r"\b(?:ApiService|ManagementApi)\b)"
)
_DIAGNOSTIC = re.compile(r"\b(?:print|debugPrint)\s*\(|\b(?:TODO|FIXME|HACK)\b")
_HIGH_CONFIDENCE_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bAIza[0-9A-Za-z_-]{20,}\b|"
    r"\bsk-[A-Za-z0-9_-]{16,}\b|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)[\"']?(?:client_secret|access_token|refresh_token|private_key)[\"']?"
    r"\s*[:=]\s*[\"']([^\"']+)[\"']"
)
_ABSOLUTE_CREDENTIAL_PATH = re.compile(
    r"(?:/[A-Za-z0-9_. -]+){2,}/[^\s'\"]*(?:credentials?|service[-_]?account)[^\s'\"]*\.json|"
    r"[A-Za-z]:\\[^\r\n'\"]*(?:credentials?|service[-_]?account)[^\r\n'\"]*\.json",
    re.IGNORECASE,
)
_SAFE_PLACEHOLDER = re.compile(
    r"^(?:\*+|<[^>]+>|\$\{[^}]+\}|(?:your|example|sample|test|demo|fake|dummy)[-_ ].*|"
    r"change[-_ ]?me|redacted)$",
    re.IGNORECASE,
)

_APPROVED_RUNTIME_FILES = {
    "twin2multicloud_flutter/lib/config/app_runtime.dart",
    "twin2multicloud_flutter/lib/config/docs_config.dart",
    "twin2multicloud_flutter/config/dev.example.json",
    "twin2multicloud_flutter/config/production.example.json",
}
_RUNTIME_MARKER = re.compile(
    r"API_BASE_URL|DOCS_BASE_URL|DEV_AUTH_TOKEN|http://localhost:(?:5005|5010)\b"
)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _read(path: Path, root: Path) -> tuple[str | None, list[Finding]]:
    relative = _relative(path, root)
    try:
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeError):
        return None, [
            Finding(
                "FLUTTER-SOURCE-READ",
                relative,
                1,
                "source could not be read as UTF-8",
            )
        ]


def _matches(
    rule_id: str,
    path: Path,
    root: Path,
    text: str,
    pattern: re.Pattern[str],
    message: str,
) -> list[Finding]:
    relative = _relative(path, root)
    return [
        Finding(rule_id, relative, _line_number(text, match.start()), message)
        for match in pattern.finditer(text)
    ]


def _is_presentation(relative: str) -> bool:
    return relative.startswith(
        (
            "twin2multicloud_flutter/lib/screens/",
            "twin2multicloud_flutter/lib/widgets/",
        )
    ) or "/presentation/" in relative


def _is_secret_surface(relative: str) -> bool:
    return (
        _is_presentation(relative)
        or relative.startswith("twin2multicloud_flutter/lib/demo/")
        or relative == "twin2multicloud_flutter/config/demo.json"
        or relative.startswith("twin2multicloud_flutter/assets/demo/")
    )


def _dart_sources(root: Path) -> Iterable[Path]:
    lib = root / "twin2multicloud_flutter" / "lib"
    return sorted(lib.rglob("*.dart")) if lib.is_dir() else []


def audit(root: Path) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    sources = list(_dart_sources(root))

    extra_sources = [
        root / "twin2multicloud_flutter" / "config" / "dev.example.json",
        root / "twin2multicloud_flutter" / "config" / "production.example.json",
        root / "twin2multicloud_flutter" / "config" / "demo.json",
    ]
    demo_assets = root / "twin2multicloud_flutter" / "assets" / "demo"
    if demo_assets.is_dir():
        extra_sources.extend(sorted(demo_assets.rglob("*.json")))

    for path in [*sources, *(item for item in extra_sources if item.is_file())]:
        text, read_findings = _read(path, root)
        findings.extend(read_findings)
        if text is None:
            continue

        relative = _relative(path, root)
        if path.suffix == ".dart":
            findings.extend(
                _matches(
                    "FLUTTER-DIRECT-SERVICE",
                    path,
                    root,
                    text,
                    _DIRECT_SERVICE,
                    "direct Optimizer or Deployer endpoint is forbidden",
                )
            )
            findings.extend(
                _matches(
                    "FLUTTER-DIAGNOSTIC",
                    path,
                    root,
                    text,
                    _DIAGNOSTIC,
                    "unsafe diagnostic or unresolved work marker",
                )
            )
            if _is_presentation(relative):
                findings.extend(
                    _matches(
                        "FLUTTER-PRESENTATION-HTTP",
                        path,
                        root,
                        text,
                        _PRESENTATION_HTTP,
                        "presentation must use typed state callbacks, not HTTP services",
                    )
                )

        if relative not in _APPROVED_RUNTIME_FILES:
            findings.extend(
                _matches(
                    "FLUTTER-RUNTIME-CONFIG",
                    path,
                    root,
                    text,
                    _RUNTIME_MARKER,
                    "runtime endpoint or dev-auth literal is outside approved config",
                )
            )

        if _is_secret_surface(relative):
            findings.extend(
                _matches(
                    "FLUTTER-SECRET-LITERAL",
                    path,
                    root,
                    text,
                    _HIGH_CONFIDENCE_SECRET,
                    "concrete secret-like value is present on a UI/demo surface",
                )
            )
            findings.extend(
                _matches(
                    "FLUTTER-SECRET-LITERAL",
                    path,
                    root,
                    text,
                    _ABSOLUTE_CREDENTIAL_PATH,
                    "absolute credential path is present on a UI/demo surface",
                )
            )
            for match in _SECRET_ASSIGNMENT.finditer(text):
                if not _SAFE_PLACEHOLDER.fullmatch(match.group(1).strip()):
                    findings.append(
                        Finding(
                            "FLUTTER-SECRET-LITERAL",
                            relative,
                            _line_number(text, match.start()),
                            "concrete assigned secret is present on a UI/demo surface",
                        )
                    )

    return sorted(set(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Flutter architecture and secret-surface boundaries."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    findings = audit(args.root)
    if findings:
        for finding in findings:
            print(finding.render())
        print(f"Flutter architecture gate failed with {len(findings)} finding(s).")
        return 1

    print("Flutter architecture gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
