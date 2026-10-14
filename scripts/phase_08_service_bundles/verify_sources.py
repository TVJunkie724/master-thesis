#!/usr/bin/env python3
"""Verify Phase 8 complete-service source ledger shape and optional reachability."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = REPOSITORY_ROOT / "docs/research/evidence/phase_08_service_bundles/source-ledger.json"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verify(online: bool) -> list[str]:
    ledger = load_json(SOURCE_PATH)
    errors: list[str] = []
    source_ids = {item["source_id"] for item in ledger["sources"]}
    for fact in ledger["facts"]:
        for source_id in fact["source_ids"]:
            if source_id not in source_ids:
                errors.append(f"{fact['fact_id']}: unknown source {source_id}")
    for source in ledger["sources"]:
        if "path" in source:
            path = REPOSITORY_ROOT / source["path"]
            if not path.is_file():
                errors.append(f"{source['source_id']}: missing {source['path']}")
            elif digest(path) != source["byte_digest"]:
                errors.append(f"{source['source_id']}: digest mismatch")
        if online and "url" in source:
            request = urllib.request.Request(
                source["url"],
                method="HEAD",
                headers={"User-Agent": "Twin2MultiCloud-Phase8-Evidence/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    if response.status >= 400:
                        errors.append(f"{source['source_id']}: HTTP {response.status}")
            except (urllib.error.URLError, TimeoutError) as exc:
                errors.append(f"{source['source_id']}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    errors = verify(args.online)
    if errors:
        for error in sorted(errors):
            print(f"ERROR: {error}")
        return 1
    mode = "online" if args.online else "offline"
    print(f"phase-08-service-bundles sources ({mode}): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
