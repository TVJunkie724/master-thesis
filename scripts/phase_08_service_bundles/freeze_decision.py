#!/usr/bin/env python3
"""Freeze byte digests for the Phase 8 complete-service decision package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_service_bundles"
DECISION_PATH = EVIDENCE_ROOT / "decision.json"
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
V2_PERMISSION_NAMES = (
    "aws_thesis_demo_v2.json",
    "aws_thesis_demo_v2_scope_review.json",
    "azure_thesis_demo_v2.json",
    "azure_thesis_demo_v2_scope_review.json",
    "gcp_thesis_demo_v2.json",
    "gcp_thesis_demo_v2_scope_review.json",
    "deployer_permission_inventory_v2.json",
)
V1_PERMISSION_NAMES = (
    "aws_thesis_demo_v1.json",
    "aws_thesis_demo_v1_scope_review.json",
    "azure_thesis_demo_v1.json",
    "azure_thesis_demo_v1_scope_review.json",
    "gcp_thesis_demo_v1.json",
    "gcp_thesis_demo_v1_scope_review.json",
    "deployer_permission_inventory.json",
)
PERMISSION_ROOT = REPOSITORY_ROOT / "3-cloud-deployer/docs/references/permission_sets"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def digest_map(paths: list[Path] | tuple[Path, ...]) -> dict[str, str]:
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
    permission_digests = digest_map(
        tuple(PERMISSION_ROOT / name for name in V2_PERMISSION_NAMES)
    )
    immutable_input_paths = tuple(
        PERMISSION_ROOT / name for name in V1_PERMISSION_NAMES
    ) + (
        REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing/decision.json",
        REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing/source-ledger.json",
        REPOSITORY_ROOT / "contracts/architecture-inventory/v1/five-layer-baseline-v1-decision.json",
    )
    immutable_input_digests = digest_map(immutable_input_paths)
    combined = {
        **artifact_digests,
        **permission_digests,
        **immutable_input_digests,
    }
    return {
        "$schema": "./schemas/package-artifact.schema.json",
        "schema_version": "1.0.0",
        "package_id": "phase-08-complete-service-bundles@1",
        "artifact_id": "decision",
        "decision_status": "approved",
        "approval_scope": "offline_contract_capacity_and_implementation_authority",
        "approved_on": "2026-08-03",
        "research_cutoff": "2026-08-03",
        "regions": {
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1"
        },
        "profile_decisions": [
            {
                "profile_ref": "five-layer-baseline@1",
                "status": "historical_read_verify_destroy_only"
            },
            {
                "profile_ref": "five-layer-baseline@2",
                "status": "approved_for_offline_implementation_not_activated"
            },
            {
                "profile_ref": "six-layer-eventing@1",
                "status": "approved_service_delta_not_activated",
                "requires_reviewed_five_layer_digest": True
            }
        ],
        "artifact_byte_digests": artifact_digests,
        "permission_artifact_byte_digests": permission_digests,
        "immutable_input_byte_digests": immutable_input_digests,
        "package_digest": package_digest(combined),
        "capacity_decision": {
            "small_medium_large": "theoretically_admissible_with_explicit_conditional_gates",
            "live_status": "live_capacity_pending",
            "azure_request_charge": "fixture_required_before_profile_activation",
            "gcp_large_worker_pool": "preview_fixed_size_non_autoscaling_preflight_required"
        },
        "plugin_decision": {
            "managed_aws_azure": "json_api_1.4.0_maintenance_mode_catalog_preflight_required",
            "self_hosted_gcp": "infinity_3.10.1_digest_pinned",
            "silent_substitution": False
        },
        "reviews": [
            {
                "review_id": "service-bundle-architecture-review-1",
                "reviewed_on": "2026-08-03",
                "scope": "profile parity, provider bundles, route ownership, single-cloud and multicloud cases, thesis PoC boundary",
                "unresolved_findings": 0
            },
            {
                "review_id": "service-bundle-builder-review-2",
                "reviewed_on": "2026-08-03",
                "scope": "schemas, deterministic formulas, digests, permissions, sources, activation and live-readiness gates",
                "unresolved_findings": 0
            },
            {
                "review_id": "service-bundle-iac-feasibility-review-3",
                "reviewed_on": "2026-08-03",
                "scope": "real Terraform and SDK bindings, provider version floor, staged GKE application, closed edge contracts",
                "unresolved_findings": 0
            }
        ],
        "activation_conditions": [
            "eventing_dependency_digest_matches",
            "historical_profile_and_thesis_demo_v1_digests_match",
            "all_package_artifacts_validate_and_are_byte_stable",
            "thesis_demo_v2_permission_manifest_matches_selected_graph",
            "provider_plugin_and_preview_resource_preflights_pass_before_mutation",
            "terraform_provider_versions_match_the_frozen_component_manifest",
            "gke_cloud_and_kubernetes_apply_stages_remain_separate_and_automatic",
            "azure_request_charge_fixture_passes_before_five_layer_profile_activation",
            "no_live_cloud_claim_is_derived_from_offline_approval"
        ]
    }


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = render(build())
    if args.write:
        DECISION_PATH.write_text(expected, encoding="utf-8")
        print(f"wrote {DECISION_PATH.relative_to(REPOSITORY_ROOT)}")
        return 0
    if not DECISION_PATH.exists() or DECISION_PATH.read_text(encoding="utf-8") != expected:
        print("decision.json is stale; run freeze_decision.py --write")
        return 1
    print("phase-08-service-bundles decision digests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
