#!/usr/bin/env python3
"""Offline verification for the frozen Phase 8 Eventing source ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing"
LEDGER_PATH = EVIDENCE_ROOT / "source-ledger.json"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def normalized_capture(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "provider": source["provider"],
        "service_family": source["service_family"],
        "claim_type": source["claim_type"],
        "source_type": source["source_type"],
        "canonical_url": source["canonical_url"],
        "effective_at": source["effective_at"],
        "region": source["region"],
        "currency": source["currency"],
        "facts": source["facts"],
    }


def content_digest(source: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(normalized_capture(source))
    ).hexdigest()


def iter_source_references(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "source_id" and isinstance(nested, str):
                yield nested
            elif key == "source_ids" and isinstance(nested, list):
                yield from (item for item in nested if isinstance(item, str))
            else:
                yield from iter_source_references(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_source_references(nested)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def verify(strict: bool) -> list[str]:
    ledger = load_json(LEDGER_PATH)
    errors: list[str] = []
    source_ids: set[str] = set()
    fact_ids: set[str] = set()

    for source in ledger["sources"]:
        source_id = source["source_id"]
        if source_id in source_ids:
            errors.append(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)

        expected = content_digest(source)
        if source["content_digest"] != expected:
            errors.append(
                f"digest mismatch: {source_id}: "
                f"expected {expected}, found {source['content_digest']}"
            )
        if not source["canonical_url"].startswith("https://"):
            errors.append(f"non-HTTPS canonical_url: {source_id}")
        if strict and source["review_status"] != "reviewed":
            errors.append(
                f"strict mode rejects {source['review_status']}: {source_id}"
            )

        for fact in source["facts"]:
            fact_id = fact["fact_id"]
            if fact_id in fact_ids:
                errors.append(f"duplicate fact_id: {fact_id}")
            fact_ids.add(fact_id)

    referenced_files = [
        EVIDENCE_ROOT / "provider-capability-matrix.json",
        EVIDENCE_ROOT / "pricing-model-matrix.json",
    ]
    for path in referenced_files:
        if not path.exists():
            if strict:
                errors.append(f"missing reference-bearing artifact: {path.name}")
            continue
        for source_id in iter_source_references(load_json(path)):
            if source_id not in source_ids:
                errors.append(f"unresolved source reference in {path.name}: {source_id}")

    return errors


def refresh_digests() -> None:
    ledger = load_json(LEDGER_PATH)
    for source in ledger["sources"]:
        source["content_digest"] = content_digest(source)
    write_json(LEDGER_PATH, ledger)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Confirm that no online refresh is requested.",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--refresh-digests",
        action="store_true",
        help="Explicitly rewrite content digests from frozen normalized facts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.offline:
        print("error: only explicit --offline verification is supported")
        return 2
    if args.refresh_digests:
        refresh_digests()

    errors = verify(strict=args.strict)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1

    ledger = load_json(LEDGER_PATH)
    print(
        "verified "
        f"{len(ledger['sources'])} reviewed sources and all known references"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
