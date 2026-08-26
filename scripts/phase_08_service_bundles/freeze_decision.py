#!/usr/bin/env python3
"""Freeze byte digests for the standalone Six-layer service-bundle evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_service_bundles"
ARTIFACT_NAMES = (
    "common-functional-contract.json",
    "complete-provider-bundles.json",
    "boundary-route-matrix.json",
    "workload-scenarios.json",
    "capacity-matrix.json",
    "pricing-ownership-matrix.json",
    "source-ledger.json",
    "implementation-component-manifest.json",
)
IMMUTABLE_INPUT_PATHS = (
    REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing/decision.json",
    REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing/source-ledger.json",
)


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def digest_map(paths: tuple[Path, ...]) -> dict[str, str]:
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix(): file_digest(path)
        for path in sorted(paths)
    }


def package_digest(values: dict[str, str]) -> str:
    encoded = json.dumps(
        values, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build() -> dict[str, Any]:
    artifact_digests = digest_map(
        tuple(EVIDENCE_ROOT / name for name in ARTIFACT_NAMES)
    )
    immutable_input_digests = digest_map(IMMUTABLE_INPUT_PATHS)
    combined = {**artifact_digests, **immutable_input_digests}
    reviews = [
        {
            "review_id": review_id,
            "reviewed_on": "2026-08-26",
            "scope": scope,
            "unresolved_findings": 0,
        }
        for review_id, scope in (
            ("six-layer-architecture", "standalone Six-layer architecture"),
            ("provider-bundles", "provider service bundles"),
            ("capacity-model", "capacity and workload mappings"),
            ("pricing-model", "pricing ownership and formulas"),
            ("iac-boundary", "Terraform and runtime ownership"),
        )
    ]
    return {
        "$schema": "./schemas/package-artifact.schema.json",
        "schema_version": "1.0.0",
        "package_id": "phase-08-complete-service-bundles@1",
        "artifact_id": "decision",
        "decision_status": "approved",
        "approval_scope": "standalone_six_layer_offline_contract_and_capacity",
        "approved_on": "2026-08-26",
        "research_cutoff": "2026-08-26",
        "pre_activation_refreeze": {
            "refrozen_on": "2026-08-26",
            "reason": "remove intermediate-profile inheritance and deployment-identity provisioning from the PoC scope",
            "scope_change": True,
            "activated_or_deployed_before_refreeze": False,
        },
        "regions": {
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1",
        },
        "profile_decisions": [
            {
                "profile_ref": "six-layer-eventing@1",
                "status": "approved_standalone_poc_profile",
            }
        ],
        "artifact_byte_digests": artifact_digests,
        "immutable_input_byte_digests": immutable_input_digests,
        "package_digest": package_digest(combined),
        "reviews": reviews,
    }


def main() -> int:
    expected = build()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    decision_path = EVIDENCE_ROOT / "decision.json"
    if args.check:
        actual = json.loads(decision_path.read_text(encoding="utf-8"))
        if actual != expected:
            raise SystemExit("Phase 8 service-bundle decision digest drifted")
        print("phase-08-service-bundle-freeze: OK")
        return 0
    decision_path.write_text(
        json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {decision_path.relative_to(REPOSITORY_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
