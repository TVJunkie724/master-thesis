#!/usr/bin/env python3
"""Verify the tracked, non-mutating Phase 8 runtime-image readiness record."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = ROOT / "docs/research/evaluation/small-runtime-image-readiness.json"
DEFAULT_SCHEMA = (
    ROOT
    / "docs/research/evaluation/schemas/live-evaluation-image-readiness.schema.json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def verify(record_path: Path, schema_path: Path) -> dict[str, Any]:
    record = _load(record_path)
    schema = _load(schema_path)
    Draft202012Validator(schema).validate(record)

    payload = {key: value for key, value in record.items() if key != "record_digest"}
    expected_digest = _digest(payload)
    if record["record_digest"] != expected_digest:
        raise ValueError(
            "image-readiness record digest mismatch: "
            f"expected {expected_digest}, got {record['record_digest']}"
        )

    image_ids = [
        item["image_id"]
        for item in [
            *record["custom_runtime_images"],
            *record["dynamic_runtime_images"],
        ]
    ]
    if len(image_ids) != len(set(image_ids)):
        raise ValueError("custom runtime image IDs must be unique")

    for image in [
        *record["public_runtime_images"],
        *record["pinned_build_inputs"],
    ]:
        reference_digest = "sha256:" + image["reference"].rsplit("@sha256:", 1)[1]
        if image["resolved_digest"] != reference_digest:
            raise ValueError(
                f"resolved digest for {image['purpose']} does not match its pinned reference"
            )

    for image in record["custom_runtime_images"]:
        source = ROOT / image["source"]
        if not source.exists():
            raise ValueError(f"custom runtime source does not exist: {source}")

    plan = _load(ROOT / "docs/research/evaluation/small-scenario-matrix.json")
    expected_gcp_processing_scenarios = {
        item["scenario_id"]
        for item in plan["scenarios"]
        if item["assignments"]["component.processing"] == "gcp"
    }
    dynamic = record["dynamic_runtime_images"][0]
    if set(dynamic["applicable_scenarios"]) != expected_gcp_processing_scenarios:
        raise ValueError("GCP processor image scenario binding drifted")
    for field in ("source", "builder", "artifact_manifest"):
        path = ROOT / dynamic[field]
        if not path.exists():
            raise ValueError(f"dynamic runtime {field} does not exist: {path}")

    manifest = _load(ROOT / dynamic["artifact_manifest"])
    if dynamic["artifact_digest"] != manifest.get("artifact_digest"):
        raise ValueError("GCP processor artifact digest drifted")
    source_metadata = manifest.get("source")
    if (
        not isinstance(source_metadata, dict)
        or dynamic["source_payload_digest"]
        != source_metadata.get("payload_digest")
    ):
        raise ValueError("GCP processor source payload digest drifted")
    source_root = ROOT / dynamic["source"]
    for item in source_metadata.get("files", []):
        path = source_root / item["relative_path"]
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"GCP processor source file is unavailable: {path}")
        content = path.read_bytes()
        if len(content) != item["size_bytes"] or (
            "sha256:" + hashlib.sha256(content).hexdigest()
            != item["content_digest"]
        ):
            raise ValueError(f"GCP processor source file digest drifted: {path}")

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    record = verify(args.record.resolve(), args.schema.resolve())
    print(
        "Runtime-image readiness record verified "
        f"({record['record_digest']}); cloud mutations remain disabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
