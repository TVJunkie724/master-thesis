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
        REPOSITORY_ROOT
        / "contracts/architecture-inventory/v1/five-layer-baseline-v1-decision.json",
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
        "research_cutoff": "2026-08-08",
        "pre_activation_refreeze": {
            "refrozen_on": "2026-08-14",
            "previous_package_digest": "sha256:b52e8d589b10d83219b92d2ac1624b6e3f2e227cd005435e1823a4669c9198a9",
            "reason": "reconcile topology-specific physical broker consumers, source-channel bridge fan-out, and the exact GCP Large StreamingPull worker allocation before the final offline audit",
            "scope_change": False,
            "activated_or_deployed_before_refreeze": False,
            "prior_refreeze": {
            "refrozen_on": "2026-08-08",
            "previous_package_digest": "sha256:05dfcce680ee12f287816a7babcf47e22b8ac6cf22f803787293db6b011e7296",
            "reason": "close Amazon Managed Grafana v12 service-account automation, explicit IAM Identity Center invitation admission, and the now-published JSON API support end before activation",
            "scope_change": False,
            "activated_or_deployed_before_refreeze": False,
            "prior_refreeze": {
                "refrozen_on": "2026-08-08",
                "previous_package_digest": "sha256:6eb06bea3e35d480a21e2dfb747cd2bf10aebd94d22f540b126548be2c6a14ae",
                "reason": "make the closed bridge registry explicitly cover the eight core event-domain channels plus the four profile-owned Twin-projection variants without changing standalone event-scope cost quantities",
                "scope_change": False,
                "activated_or_deployed_before_refreeze": False,
                "prior_refreeze": {
                    "refrozen_on": "2026-08-08",
                    "previous_package_digest": "sha256:a5c3b8b9333d0a584b52f7fe0111208c1778a284d2be537b9f27be2083c4f1ae",
                    "reason": "supersede the planning-only eventing-envelope with the shared canonical domain-event envelope, source ordering identity, and event-id idempotency before activation",
                    "scope_change": False,
                    "activated_or_deployed_before_refreeze": False,
                    "prior_refreeze": {
                        "refrozen_on": "2026-08-08",
                        "previous_package_digest": "sha256:546b980ce1b3d8dfc74cfb54f31ca0f0e87cb3cefeaa6cc037b77e4ec92a26b9",
                        "reason": "replace the planning-only unlimited route-fault wait with the selected six-attempt provider budget, application-safe terminal recording where the trigger exposes the attempt, and the already selected provider-native terminal fallback before activation",
                        "scope_change": False,
                        "activated_or_deployed_before_refreeze": False,
                        "prior_refreeze": {
                            "refrozen_on": "2026-08-08",
                            "previous_package_digest": "sha256:1009870a995648ad646bd54fa4465488a34e66c6a3856363f6b346c756182bd3",
                            "reason": "remove the duplicate device-command outcome assignment from the L2-to-L3 route after the direct L1-to-L3 contract was added before activation",
                            "scope_change": False,
                            "activated_or_deployed_before_refreeze": False,
                            "prior_refreeze": {
                                "refrozen_on": "2026-08-08",
                                "previous_package_digest": "sha256:f0ddf4dd60c898dcc23867e3e3bda8974fa8f20a0dc850fe1942b60947ec5f2f",
                                "reason": "repair the mandatory bidirectional L1-L2 domain-event cycle and align all Five-layer v2 edge contract identifiers with the approved common functional contract before activation",
                                "scope_change": False,
                                "activated_or_deployed_before_refreeze": False,
                                "prior_refreeze": {
                                    "refrozen_on": "2026-08-08",
                                    "previous_package_digest": "sha256:f5bbbb4d052458d70b3b079321729fc4f46a439f1bcde3e710b960b412968d90",
                                    "reason": "bind the approved Azure ACR Task and Container Apps scheduled storage mover to its actual source path before activation",
                                    "scope_change": False,
                                    "activated_or_deployed_before_refreeze": False,
                                    "prior_refreeze": {
                                        "refrozen_on": "2026-08-07",
                                        "previous_package_digest": "sha256:a3eef3b52915b8a3d696933fe3a91d7d24c2e7ea66099a55d7fb95b57d317c49",
                                        "reason": "expose exact provider storage task counts and provider-neutral content-addressed image publication stages before AWS and Azure runtime activation",
                                        "scope_change": False,
                                        "activated_or_deployed_before_refreeze": False,
                                        "prior_refreeze": {
                                            "refrozen_on": "2026-08-07",
                                            "previous_package_digest": "sha256:73a78f62858fcd3563205b84fd937a40a243a2d342e0e97b67c2b76f78f6243a",
                                            "reason": "bind the approved GCP content-addressed image publication stages, finite build-source bucket, dedicated build identity, and five-minute 1/1/3-task storage batches",
                                            "scope_change": False,
                                            "activated_or_deployed_before_refreeze": False,
                                            "prior_refreeze": {
                                                "refrozen_on": "2026-08-05",
                                                "previous_package_digest": "sha256:9c85a4c9ef2207a8e5b0eccadf8e24d6ae04fe968519d0b8b7056b523dd2e73a",
                                                "reason": "close the approved GCP L5 platform bindings for its conditional GKE cluster, static Persistent Disk PV, fixed load-balancer address, and L4-only direct IAP ownership",
                                                "scope_change": False,
                                                "activated_or_deployed_before_refreeze": False,
                                                "prior_refreeze": {
                                                    "refrozen_on": "2026-08-05",
                                                    "previous_package_digest": "sha256:aec13fde178fb9bc4ba9943b206d0aa7e2a7d60aeb685d4076c83c6492e2515a",
                                                    "reason": "bind the selected Cosmos DB data plane to its required managed-identity SQL role assignment",
                                                    "scope_change": False,
                                                    "activated_or_deployed_before_refreeze": False,
                                                    "prior_refreeze": {
                                                        "refrozen_on": "2026-08-05",
                                                        "previous_package_digest": "sha256:6404a4190b3342ec267be33ec1e86626152fde612287a2b7354a576248d9cd84",
                                                        "reason": "bind the already approved Azure Logic Apps Consumption workflow to its required HTTP trigger and fixed PoC action definition",
                                                        "scope_change": False,
                                                        "activated_or_deployed_before_refreeze": False,
                                                        "prior_refreeze": {
                                                            "refrozen_on": "2026-08-05",
                                                            "previous_package_digest": "sha256:647e8bec71b8f6b92a2ed5cc76070e54a3a00f8fca0a7132200a09dc2cbb8f1c",
                                                            "reason": "close missing Terraform bindings for Azure six-CU Dedicated capacity and the subscriptions required by the approved Azure Service Bus and AWS SNS FIFO broker paths",
                                                            "scope_change": False,
                                                            "activated_or_deployed_before_refreeze": False,
                                                            "prior_refreeze": {
                                                                "refrozen_on": "2026-08-05",
                                                                "previous_package_digest": "sha256:337dbf11eae56e62e69ebdbdc16d4dfe8c67277af935c8cb87b2df98f12f6646",
                                                                "reason": "restore the frozen directed-identity distinction: AWS outbound identity is used for Azure, while AWS-to-GCP uses GCP Workload Identity Federation's AWS provider",
                                                                "scope_change": False,
                                                                "activated_or_deployed_before_refreeze": False,
                                                                "prior_refreeze": {
                                                                    "refrozen_on": "2026-08-05",
                                                                    "previous_package_digest": "sha256:e11bbd03470434a0552151ce4b005fea7e05838c511795b45505e58bee5a7d3e",
                                                                    "reason": "incorrectly broaden the AWS account-level outbound-identity wording to GCP before implementation review detected the mismatch",
                                                                    "scope_change": False,
                                                                    "activated_or_deployed_before_refreeze": False,
                                                                    "prior_refreeze": {
                                                                        "refrozen_on": "2026-08-04",
                                                                        "previous_package_digest": "sha256:cc142504cc8c06927569ec1cce09fe4a9133a688b5f02a2ba114105a0e422245",
                                                                        "reason": "close the AWS-to-Azure implementation gap by admitting disclosed account-level outbound-identity enablement to thesis-demo-v2",
                                                                        "scope_change": True,
                                                                        "activated_or_deployed_before_refreeze": False,
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        },
        "regions": {
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1",
        },
        "profile_decisions": [
            {
                "profile_ref": "five-layer-baseline@1",
                "status": "historical_read_verify_destroy_only",
            },
            {
                "profile_ref": "five-layer-baseline@2",
                "status": "approved_for_offline_implementation_not_activated",
            },
            {
                "profile_ref": "six-layer-eventing@1",
                "status": "approved_service_delta_not_activated",
                "requires_reviewed_five_layer_digest": True,
            },
        ],
        "artifact_byte_digests": artifact_digests,
        "permission_artifact_byte_digests": permission_digests,
        "immutable_input_byte_digests": immutable_input_digests,
        "package_digest": package_digest(combined),
        "capacity_decision": {
            "small_medium_large": "theoretically_admissible_with_explicit_conditional_gates",
            "live_status": "live_capacity_pending",
            "azure_request_charge": "fixture_required_before_profile_activation",
            "gcp_large_worker_pool": "preview_fixed_size_non_autoscaling_preflight_required",
        },
        "plugin_decision": {
            "managed_aws_azure": "json_api_1.4.0_deprecated_support_ends_2027_02_01_catalog_preflight_required",
            "self_hosted_gcp": "infinity_3.10.1_digest_pinned",
            "silent_substitution": False,
        },
        "reviews": [
            {
                "review_id": "service-bundle-architecture-review-1",
                "reviewed_on": "2026-08-03",
                "scope": "profile parity, provider bundles, route ownership, single-cloud and multicloud cases, thesis PoC boundary",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-builder-review-2",
                "reviewed_on": "2026-08-03",
                "scope": "schemas, deterministic formulas, digests, permissions, sources, activation and live-readiness gates",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-iac-feasibility-review-3",
                "reviewed_on": "2026-08-03",
                "scope": "real Terraform and SDK bindings, provider version floor, staged GKE application, closed edge contracts",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-contract-integration-review-4",
                "reviewed_on": "2026-08-04",
                "scope": "provider-specific plugin ownership, atomic capacity dimensions, single-cloud omission of remote-only services, and all 729 admissible Five-layer assignments",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-aws-outbound-identity-review-5",
                "reviewed_on": "2026-08-04",
                "scope": "current AWS IAM outbound identity federation, Azure workload federation, account enablement, runtime token permission, and destroy ownership",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-azure-large-iac-binding-review-6",
                "reviewed_on": "2026-08-05",
                "scope": "Azure Standard and six-CU Dedicated Event Hubs plus Azure Service Bus and AWS SNS FIFO subscription bindings",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-azure-logic-app-iac-binding-review-7",
                "reviewed_on": "2026-08-05",
                "scope": "Azure Logic Apps Consumption workflow shell, callable trigger, and fixed PoC action binding",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-azure-cosmos-data-plane-binding-review-8",
                "reviewed_on": "2026-08-05",
                "scope": "Azure Cosmos DB NoSQL managed-identity data-plane access for raw/rollup runtime paths",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-gcp-image-tiering-binding-review-9",
                "reviewed_on": "2026-08-07",
                "scope": "GCP staged content-addressed image publication, bounded build support, five-minute storage windows, and 1/1/3 task capacity binding",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-provider-image-tiering-contract-review-10",
                "reviewed_on": "2026-08-07",
                "scope": "exact AWS 1/1/3, Azure 1/4/30, and GCP 1/1/3 storage task dimensions plus provider-native content-addressed image publication without a local Docker dependency",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-bounded-route-failure-review-11",
                "reviewed_on": "2026-08-08",
                "scope": "bounded route and trust failure retries, safe application terminal records, provider-native trigger fallbacks, and Azure Service Bus delivery-count semantics",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-canonical-event-envelope-review-12",
                "reviewed_on": "2026-08-08",
                "scope": "single canonical domain-event envelope for Five-layer v2 and Six-layer v1, source-id/source-sequence ordering, event-id idempotency, and payload-scoped replay identity",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-closed-event-registry-review-13",
                "reviewed_on": "2026-08-08",
                "scope": "explicit closed union of eight core event-domain types and four Twin-projection profile extensions, including separate cost ownership and runtime parity",
                "unresolved_findings": 0,
            },
            {
                "review_id": "service-bundle-aws-grafana-v12-access-review-14",
                "reviewed_on": "2026-08-08",
                "scope": "Amazon Managed Grafana v12 short-lived service-account automation, exact plugin and bounded dashboard probes, and explicit built-in IAM Identity Center invitation admission",
                "unresolved_findings": 0,
            },
        ],
        "activation_conditions": [
            "eventing_dependency_digest_matches",
            "historical_profile_and_thesis_demo_v1_digests_match",
            "all_package_artifacts_validate_and_are_byte_stable",
            "thesis_demo_v2_permission_manifest_matches_selected_graph",
            "provider_plugin_and_preview_resource_preflights_pass_before_mutation",
            "terraform_provider_versions_match_the_frozen_component_manifest",
            "provider_image_cloud_kubernetes_and_post_apply_stages_remain_separate_and_automatic",
            "azure_acr_task_subscription_eligibility_passes_before_mutation",
            "azure_request_charge_fixture_passes_before_five_layer_profile_activation",
            "no_live_cloud_claim_is_derived_from_offline_approval",
        ],
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
    if (
        not DECISION_PATH.exists()
        or DECISION_PATH.read_text(encoding="utf-8") != expected
    ):
        print("decision.json is stale; run freeze_decision.py --write")
        return 1
    print("phase-08-service-bundles decision digests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
