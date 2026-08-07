from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]


def load_module(filename: str):
    path = SCRIPT_ROOT / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DecisionPackageValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_module("validate_decision_package.py")
        cls.freezer = load_module("freeze_decision.py")
        cls.generator = load_module("generate_manifests.py")

    def test_frozen_package_has_no_findings(self) -> None:
        self.assertEqual(self.validator.validate(), [])

    def test_decision_freeze_is_reproducible(self) -> None:
        current = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "decision.json"
        )
        self.assertEqual(current, self.freezer.build())

    def test_route_tamper_is_rejected(self) -> None:
        routes = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "boundary-route-matrix.json"
        )
        tampered = copy.deepcopy(routes)
        tampered["directed_cross_cloud_pairs"].pop()
        errors: list[str] = []
        self.validator.validate_routes(tampered, errors)
        self.assertIn(
            "directed_cross_cloud_pairs must contain all six exact pairs", errors
        )

    def test_l3_hot_l5_split_is_explicitly_rejected(self) -> None:
        routes = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "boundary-route-matrix.json"
        )
        self.assertIn(
            {
                "condition": "l3_hot_provider_differs_from_l5_provider",
                "error_code": "PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED",
            },
            routes["negative_routes"],
        )

    def test_component_and_pricing_manifests_cover_same_73_components(self) -> None:
        manifest = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "implementation-component-manifest.json"
        )
        self.assertEqual(
            {item["runtime_state"] for item in manifest["components"]},
            {"decision_frozen_not_implemented"},
        )
        pricing = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "pricing-ownership-matrix.json"
        )
        self.assertEqual(len(manifest["components"]), 73)
        self.assertEqual(
            {item["component_id"] for item in manifest["components"]},
            {item["component_id"] for item in pricing["component_owners"]},
        )
        providers_by_component = {
            item["component_id"]: item["provider"] for item in manifest["components"]
        }
        self.assertEqual(
            providers_by_component["aws.grafana-marcusolsson-json-datasource"],
            "aws",
        )
        self.assertEqual(
            providers_by_component["azure.grafana-marcusolsson-json-datasource"],
            "azure",
        )

    def test_route_pricing_covers_four_classes_and_six_pairs(self) -> None:
        pricing = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "pricing-ownership-matrix.json"
        )
        self.assertEqual(len(pricing["route_owners"]), 24)
        self.assertEqual(
            len({item["deduplication_key"] for item in pricing["route_owners"]}),
            24,
        )

    def test_json_plugin_has_no_invented_end_date(self) -> None:
        bundle = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "complete-provider-bundles.json"
        )
        plugins = {item["plugin_id"]: item for item in bundle["plugin_decisions"]}
        self.assertIsNone(plugins["marcusolsson-json-datasource"]["hard_end_date"])
        tampered = copy.deepcopy(bundle)
        tampered["plugin_decisions"][0]["hard_end_date"] = "2027-02-01"
        errors: list[str] = []
        self.validator.validate_plugins(tampered, errors)
        self.assertIn(
            "JSON API decision must not invent a hard support-end date", errors
        )

    def test_gcp_permission_manifest_has_no_wildcards_or_bootstrap_authority(
        self,
    ) -> None:
        permission = self.validator.load_json(
            self.validator.PERMISSION_ROOT / "gcp_thesis_demo_v2.json"
        )
        self.assertFalse(any("*" in item for item in permission["custom_role_inputs"]))
        self.assertTrue(
            set(permission["forbidden_bootstrap_actions"]).isdisjoint(
                permission["custom_role_inputs"]
            )
        )
        self.assertTrue(
            {
                "artifactregistry.repositories.getIamPolicy",
                "artifactregistry.repositories.setIamPolicy",
                "cloudbuild.builds.create",
                "cloudbuild.builds.get",
                "storage.buckets.getIamPolicy",
                "storage.buckets.setIamPolicy",
            }.issubset(permission["custom_role_inputs"])
        )

    def test_runtime_manifest_does_not_claim_implementation(self) -> None:
        manifest = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "implementation-component-manifest.json"
        )

    def test_aws_image_publication_permissions_are_frozen(self) -> None:
        permission = self.validator.load_json(
            self.validator.PERMISSION_ROOT / "aws_thesis_demo_v2.json"
        )
        actions = {
            action
            for group in permission["policy_inputs"]
            for action in group["actions"]
        }
        self.assertTrue(
            {
                "codebuild:CreateProject",
                "codebuild:StartBuild",
                "codebuild:BatchGetBuilds",
                "ecr:DescribeImages",
                "s3:PutObject",
                "s3:GetObject",
            }.issubset(actions)
        )
        pass_role = next(
            item
            for item in permission["conditions"]
            if item["condition"] == "iam:PassedToService"
        )
        self.assertIn("codebuild.amazonaws.com", pass_role["values"])

    def test_exact_iac_boundaries_and_provider_upgrade_are_frozen(self) -> None:
        manifest = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "implementation-component-manifest.json"
        )
        components = {item["component_id"]: item for item in manifest["components"]}
        self.assertEqual(
            components["aws.iot-commands"]["terraform_resource_types"],
            ["awscc_iot_command"],
        )
        self.assertEqual(
            components["aws.iot-twinmaker-standard"]["terraform_resource_types"],
            ["awscc_iottwinmaker_workspace"],
        )
        self.assertTrue(
            components["aws.iot-twinmaker-standard"]["post_terraform_operations"]
        )
        self.assertEqual(
            manifest["terraform_provider_requirements"]["google"]["version_constraint"],
            ">= 7.22.0, < 8.0.0",
        )
        self.assertEqual(
            [item["stage"] for item in manifest["terraform_apply_stages"]],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(
            [item["owner"] for item in manifest["terraform_apply_stages"]],
            [
                "provider_image_foundation_when_required",
                "provider_content_addressed_image_publication_when_required",
                "cloud_provider_resources",
                "kubernetes_resources",
                "bounded_post_terraform_operations",
            ],
        )
        self.assertIn(
            "regional_codebuild_publish_content_addressed_images",
            components["aws.ecr-if-container-selected"][
                "post_terraform_operations"
            ],
        )
        self.assertIn(
            "aws_codebuild_project",
            components["aws.ecr-if-container-selected"][
                "terraform_resource_types"
            ],
        )
        self.assertIn(
            "regional_acr_task_publish_content_addressed_images",
            components["azure.acr-basic-if-container-selected"][
                "post_terraform_operations"
            ],
        )
        self.assertIn(
            "regional_cloud_build_publish_content_addressed_images",
            components["gcp.artifact-registry-if-container-selected"][
                "post_terraform_operations"
            ],
        )
        self.assertIn(
            "google_storage_bucket",
            components["gcp.artifact-registry-if-container-selected"][
                "terraform_resource_types"
            ],
        )
        for mover_id in (
            "aws.ecs-fargate-storage-mover",
            "azure.container-apps-scheduled-storage-job",
            "gcp.cloud-run-storage-job",
        ):
            self.assertIn("task_count", components[mover_id]["capacity_dimensions"])
        self.assertEqual(
            set(
                components["gcp.cloud-run-iap-twin-explorer"][
                    "terraform_resource_types"
                ]
            ),
            {
                "google_cloud_run_v2_service",
                "google_cloud_run_v2_service_iam_member",
                "google_iap_web_cloud_run_service_iam_member",
            },
        )
        self.assertEqual(
            set(components["grafana.oss-12-on-gke"]["terraform_resource_types"]),
            {
                "google_container_cluster",
                "kubernetes_namespace_v1",
                "kubernetes_deployment_v1",
            },
        )
        self.assertEqual(
            set(
                components["apache.bifromq-4.0.0-incubating-on-gke-standard"][
                    "terraform_resource_types"
                ]
            ),
            {
                "google_container_cluster",
                "google_container_node_pool",
                "kubernetes_namespace_v1",
                "kubernetes_deployment_v1",
            },
        )
        self.assertEqual(
            set(
                components["gcp.ordered-mqtt-pubsub-adapter"][
                    "terraform_resource_types"
                ]
            ),
            {
                "google_container_node_pool",
                "kubernetes_deployment_v1",
            },
        )
        self.assertIn(
            "kubernetes_persistent_volume_v1",
            components["gcp.persistent-disk-rwo"]["terraform_resource_types"],
        )
        self.assertIn(
            "google_compute_address",
            components["gcp.grafana-tls-load-balancer"]["terraform_resource_types"],
        )

    def test_gcp_human_access_support_is_owned_by_the_exact_layer(self) -> None:
        bundle = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "complete-provider-bundles.json"
        )
        gcp = next(item for item in bundle["providers"] if item["provider"] == "gcp")
        self.assertIn("gcp.direct-iap-layer-access", gcp["layers"]["l4_twin"])
        self.assertNotIn("gcp.direct-iap-layer-access", gcp["support_components"])
        self.assertIn(
            "gcp.grafana-tls-load-balancer",
            gcp["layers"]["l5_visualization"],
        )
        self.assertNotIn("gcp.grafana-tls-load-balancer", gcp["support_components"])

    def test_common_edge_contracts_are_closed_and_poc_bounded(self) -> None:
        contract = self.validator.load_json(
            self.validator.EVIDENCE_ROOT / "common-functional-contract.json"
        )
        definitions = contract["contract_definitions"]
        self.assertEqual(
            set(definitions),
            {
                "raw_history_query.v1",
                "twin_projection.v1",
                "storage_transition.v1",
                "canonical-domain-event.v1",
            },
        )
        self.assertFalse(
            definitions["storage_transition.v1"]["permanent_worker_or_cdc_allowed"]
        )
        self.assertTrue(definitions["twin_projection.v1"]["not_per_telemetry_message"])


if __name__ == "__main__":
    unittest.main()
