"""Regression tests for the additive Five-layer v2 contract bundle."""

from __future__ import annotations

import copy
import itertools
import unittest

from scripts import sync_five_layer_v2_contracts as contract


class FiveLayerV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (
            cls.runtime,
            cls.profile,
            cls.catalog,
            cls.provider_profiles,
            cls.registry,
            cls.groups,
        ) = contract.load_v2_bundle()
        cls.rds_schema = contract.read_json(contract.RDS_V2 / "schema.json")

    def test_source_and_generated_copies_are_exact(self) -> None:
        contract.check()

    def test_deployment_manifest_marker_matches_its_dedicated_synchronizer(
        self,
    ) -> None:
        from scripts import sync_deployment_manifest_contract

        self.assertEqual(
            contract.deployment_manifest_tree_digest(contract.DEPLOYMENT_MANIFEST_ROOT),
            sync_deployment_manifest_contract.validate_source(),
        )

    def test_aws_platform_artifact_is_bound_to_executable_runtime_source(self) -> None:
        artifact = next(
            item
            for item in self.catalog["package_artifacts"]
            if item["artifact_id"] == "artifact.platform.aws.five-layer-v2"
        )
        self.assertEqual(
            artifact["repository_source_path"], contract.AWS_V2_RUNTIME_SOURCE
        )
        self.assertEqual(
            artifact["included_paths"],
            [
                "handler.py",
                "storage-mover/Dockerfile",
                "storage-mover/constraints.txt",
                "storage-mover/requirements.txt",
                "storage-mover/storage_mover.py",
            ],
        )
        self.assertEqual(
            artifact["source_digest"],
            contract.package_source_digest(contract.AWS_V2_RUNTIME_SOURCE),
        )

    def test_historical_v1_contract_trees_remain_byte_stable(self) -> None:
        self.assertEqual(
            contract.tree_digest(contract.ARCH_V1),
            "sha256:8810b229e6546bc20dfb65714073b0e108afacadb1ee8abcc239fe8784c8068d",
        )
        self.assertEqual(
            contract.tree_digest(contract.RDS_ROOT / "v1"),
            "sha256:d0a1d08f7d0b13999a18c700cdc197ac1563aeab62c09e56bba9864b21b4391c",
        )

    def test_representative_fixtures_cover_single_two_and_three_cloud(self) -> None:
        paths = sorted((contract.RDS_V2 / "fixtures" / "valid").glob("*.json"))
        self.assertEqual(
            {path.stem for path in paths},
            {
                "single-cloud-aws-small",
                "two-cloud-azure-l3l5-gcp-l4-medium",
                "three-cloud-mixed-large",
                "six-layer-aws-azure-eventing-small",
            },
        )

    def test_all_online_placements_cover_all_three_sizes(self) -> None:
        count = 0
        for base, twin in contract.VALID_PLACEMENTS:
            for size in ("small", "medium", "large"):
                specification = contract.build_rds(
                    contract.assignment_for_bundle(base, twin),
                    self.profile,
                    self.catalog,
                    size=size,
                )
                contract.validate_rds(
                    specification,
                    self.rds_schema,
                    self.profile,
                    self.catalog,
                )
                count += 1
        self.assertEqual(count, 27)

    def test_representative_rtas_cover_single_two_and_three_cloud(self) -> None:
        paths = sorted(
            (contract.ARCH_V2 / "fixtures" / "valid").glob("*-resolved.json")
        )
        self.assertEqual(
            {path.stem for path in paths},
            {
                "single-cloud-aws-small-resolved",
                "two-cloud-azure-l3l5-gcp-l4-medium-resolved",
                "three-cloud-mixed-large-resolved",
                "six-layer-aws-azure-eventing-small-resolved",
            },
        )
        provider_counts = {
            len(
                {
                    assignment["provider"]
                    for assignment in contract.read_json(path)["component_assignments"]
                }
            )
            for path in paths
        }
        self.assertEqual(provider_counts, {1, 2, 3})

    def test_reviewed_definitions_are_active_together(self) -> None:
        self.assertEqual(self.profile["lifecycle_status"], "active")
        self.assertEqual(self.catalog["lifecycle_status"], "active")
        self.assertTrue(
            all(
                profile["lifecycle_status"] == "active"
                for profile in self.provider_profiles.values()
            )
        )
        self.assertNotIn(
            "gate.profile-activation-pending",
            contract.blocking_gate_ids(
                "small",
                ["aws"],
                {logical: "aws" for logical in contract.LOGICAL_COMPONENTS},
            ),
        )

    def test_all_729_layer_assignments_are_admissible_when_l3_hot_and_l5_match(
        self,
    ) -> None:
        count = 0
        for values in itertools.product(contract.PROVIDERS, repeat=6):
            assignment = dict(zip(contract.LOGICAL_COMPONENTS[:-1], values))
            assignment["component.visualization"] = assignment["component.hot-storage"]
            specification = contract.build_rds(
                assignment,
                self.profile,
                self.catalog,
                size="small",
            )
            contract.validate_rds(
                specification,
                self.rds_schema,
                self.profile,
                self.catalog,
            )
            resolution = contract.build_rta(
                assignment,
                specification,
                self.profile,
                self.provider_profiles,
                self.catalog,
                self.runtime,
            )
            self.assertEqual(
                resolution["deployment_specification_ref"]["digest"],
                specification["digest"],
            )
            self.assertEqual(
                {
                    item["logical_component_id"]: item["provider"]
                    for item in resolution["component_assignments"]
                },
                assignment,
            )
            self.assertEqual(
                len(resolution["resolved_edges"]), len(self.profile["edges"])
            )
            count += 1
        self.assertEqual(count, 729)

    def test_edge_terraform_bindings_use_declared_destination_ports(self) -> None:
        for edge in self.catalog["edge_implementations"]:
            self.assertEqual(
                edge["terraform_binding"]["destination_input_id"],
                edge["destination_input_port_id"],
            )

    def test_graph_models_bidirectional_device_events_and_canonical_contracts(
        self,
    ) -> None:
        edges = {item["edge_id"]: item for item in self.profile["edges"]}

        self.assertIn("edge.processing-to-ingestion", edges)
        self.assertIn("edge.ingestion-to-hot-storage", edges)
        self.assertEqual(
            edges["edge.ingestion-to-processing"]["edge_contract_id"],
            contract.DOMAIN_EVENT_CONTRACT_ID,
        )
        self.assertEqual(
            edges["edge.processing-to-ingestion"]["edge_contract_id"],
            contract.DOMAIN_EVENT_CONTRACT_ID,
        )
        self.assertEqual(
            edges["edge.ingestion-to-hot-storage"]["edge_contract_id"],
            contract.DOMAIN_EVENT_CONTRACT_ID,
        )
        self.assertEqual(
            edges["edge.processing-to-hot-storage"]["edge_contract_id"],
            contract.DOMAIN_EVENT_CONTRACT_ID,
        )
        self.assertEqual(
            edges["edge.hot-storage-to-twin-state"]["edge_contract_id"],
            contract.TWIN_PROJECTION_CONTRACT_ID,
        )
        self.assertEqual(
            self.profile["graph_policy"],
            {
                "cycle_policy": "allowlisted",
                "allowed_cycle_ids": ["cycle.ingestion.processing"],
                "optional_components": [],
                "user_topology_editable": False,
            },
        )
        self.assertIn(
            "cycle.ingestion.processing",
            {item["cycle_id"] for item in self.registry["cycle_contracts"]},
        )

    def test_device_command_outcome_has_one_source_owned_edge(self) -> None:
        functional = contract.read_json(
            contract.SERVICE_ROOT / "common-functional-contract.json"
        )
        owners = [
            edge["edge_id"]
            for edge in functional["logical_edges"]
            if "device.command.outcome.v1" in edge.get("channels", [])
        ]

        self.assertEqual(owners, ["ingestion-to-hot-storage-domain-events"])

    def test_single_cloud_omits_remote_only_event_services(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("aws", "aws"),
            self.profile,
            self.catalog,
        )
        component_ids = {
            item["implementation_component_id"]
            for item in specification["component_selections"]
        }
        self.assertFalse(
            any("only-for-reviewed-remote" in item for item in component_ids)
        )

    def test_remote_l4_adds_both_provider_event_and_access_support(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("aws", "azure"),
            self.profile,
            self.catalog,
        )
        component_ids = {
            item["implementation_component_id"]
            for item in specification["component_selections"]
        }
        self.assertIn(
            "aws.kinesis-only-for-reviewed-remote-telemetry-edge",
            component_ids,
        )
        self.assertIn(
            "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
            component_ids,
        )
        self.assertIn("azure.entra-layer-access-bindings", component_ids)
        self.assertIn("azure.monitor", component_ids)

    def test_gcp_iap_is_l4_only_and_grafana_has_complete_platform_resources(
        self,
    ) -> None:
        gcp_l5_aws_l4 = contract.build_rds(
            contract.assignment_for_bundle("gcp", "aws"),
            self.profile,
            self.catalog,
        )
        selected = {
            item["implementation_component_id"]
            for item in gcp_l5_aws_l4["component_selections"]
        }
        self.assertNotIn("gcp.direct-iap-layer-access", selected)
        self.assertIn("gcp.grafana-tls-load-balancer", selected)

        gcp_visualization = next(
            item
            for item in self.catalog["components"]
            if item["deployment_component_id"] == "deployment.gcp.visualization.v2"
        )
        resources = set(gcp_visualization["terraform_binding"]["resource_addresses"])
        self.assertIn("google_container_cluster.gcp_grafana_oss_12_on_gke", resources)
        self.assertIn("kubernetes_namespace_v1.gcp_grafana_oss_12_on_gke", resources)
        self.assertIn(
            "kubernetes_persistent_volume_v1.gcp_gcp_persistent_disk_rwo",
            resources,
        )
        self.assertIn(
            "google_compute_address.gcp_gcp_grafana_tls_load_balancer",
            resources,
        )
        self.assertNotIn("kubernetes_service_v1.gcp_grafana_oss_12_on_gke", resources)
        self.assertFalse(any("direct_iap" in item for item in resources))

        aws_l5_gcp_l4 = contract.build_rds(
            contract.assignment_for_bundle("aws", "gcp"),
            self.profile,
            self.catalog,
        )
        selected = {
            item["implementation_component_id"]
            for item in aws_l5_gcp_l4["component_selections"]
        }
        self.assertIn("gcp.direct-iap-layer-access", selected)
        self.assertNotIn("gcp.grafana-tls-load-balancer", selected)

    def test_capacity_dimensions_change_with_scenario(self) -> None:
        specifications = {
            provider: {
                size: contract.build_rds(
                    contract.assignment_for_bundle(provider, "aws"),
                    self.profile,
                    self.catalog,
                    size=size,
                )
                for size in ("small", "medium", "large")
            }
            for provider in ("aws", "azure", "gcp")
        }
        specifications["gcp_twin"] = {
            size: contract.build_rds(
                contract.assignment_for_bundle("gcp", "gcp"),
                self.profile,
                self.catalog,
                size=size,
            )
            for size in ("small", "medium", "large")
        }

        def dimension(
            provider: str,
            size: str,
            component_id: str,
            dimension_id: str,
        ):
            selection = next(
                item
                for item in specifications[provider][size]["component_selections"]
                if item["implementation_component_id"] == component_id
            )
            return next(
                item["value"]
                for item in selection["dimensions"]
                if item["dimension_id"].endswith(f".{dimension_id}")
            )

        self.assertEqual(
            [
                dimension(
                    "gcp",
                    size,
                    "gcp.firestore-native-standard-raw-and-rollup",
                    "timestamp_shards",
                )
                for size in ("small", "medium", "large")
            ],
            [1, 1, 16],
        )
        self.assertEqual(
            [
                dimension(
                    "azure",
                    size,
                    "azure.cosmos-db-nosql-raw-and-rollup",
                    "capacity_mode",
                )
                for size in ("small", "medium", "large")
            ],
            ["serverless", "serverless", "autoscale"],
        )
        self.assertEqual(
            dimension(
                "azure",
                "large",
                "azure.cosmos-db-nosql-raw-and-rollup",
                "autoscale_max_ru_per_second",
            ),
            108000,
        )
        self.assertEqual(
            dimension(
                "gcp_twin",
                "large",
                "gcp.persistent-disk-rwo",
                "stored_gib_month",
            ),
            "10",
        )
        self.assertEqual(
            dimension(
                "gcp_twin",
                "large",
                "gcp.external-load-balancer",
                "processed_bytes",
            ),
            10_616_832_000_000,
        )
        self.assertEqual(
            dimension(
                "gcp",
                "large",
                "gcp.grafana-tls-load-balancer",
                "processed_bytes",
            ),
            2_361_600_000_000,
        )
        self.assertEqual(
            dimension(
                "aws",
                "large",
                "aws.dynamodb-on-demand-raw",
                "stored_gib_month",
            ),
            "9887.6953125",
        )
        self.assertEqual(
            dimension(
                "aws",
                "large",
                "aws.dynamodb-on-demand-hourly-rollup",
                "stored_gib_month",
            ),
            "16.4794921875",
        )
        self.assertEqual(
            dimension(
                "aws",
                "large",
                "aws.dynamodb-on-demand-raw",
                "write_requests",
            ),
            25_920_000_000,
        )
        self.assertEqual(
            dimension(
                "aws",
                "large",
                "aws.dynamodb-on-demand-hourly-rollup",
                "read_requests",
            ),
            15_033_600_000,
        )
        self.assertEqual(
            dimension(
                "aws",
                "large",
                "aws.dynamodb-on-demand-hourly-rollup",
                "write_requests",
            ),
            25_920_000_000,
        )
        self.assertEqual(
            dimension(
                "azure",
                "large",
                "azure.cosmos-db-nosql-raw-and-rollup",
                "request_units",
            ),
            274_233_600_000,
        )
        self.assertEqual(
            dimension(
                "gcp",
                "large",
                "gcp.firestore-native-standard-raw-and-rollup",
                "stored_gib_month",
            ),
            "9904.1748046875",
        )
        self.assertEqual(
            dimension(
                "gcp",
                "large",
                "gcp.firestore-native-standard-raw-and-rollup",
                "document_reads",
            ),
            15_033_600_000,
        )
        self.assertEqual(
            dimension(
                "gcp",
                "large",
                "gcp.firestore-native-standard-raw-and-rollup",
                "document_writes",
            ),
            25_920_000_000,
        )
        self.assertEqual(
            dimension(
                "gcp",
                "large",
                "gcp.firestore-native-standard-raw-and-rollup",
                "document_deletes",
            ),
            12_981_600_000,
        )
        self.assertEqual(
            dimension(
                "gcp_twin",
                "large",
                "gcp.firestore-native-standard-bounded-twin",
                "document_writes",
            ),
            132_192_240,
        )
        self.assertEqual(
            dimension(
                "gcp_twin",
                "large",
                "gcp.firestore-native-standard-bounded-twin",
                "timestamp_shards",
            ),
            1,
        )
        self.assertEqual(
            [
                dimension(
                    "gcp",
                    size,
                    "apache.bifromq-4.0.0-incubating-on-gke-standard",
                    "resource_count",
                )
                for size in ("small", "medium", "large")
            ],
            [3, 3, 12],
        )
        self.assertEqual(
            [
                dimension(
                    "gcp",
                    size,
                    "apache.bifromq-4.0.0-incubating-on-gke-standard",
                    "node_count",
                )
                for size in ("small", "medium", "large")
            ],
            [3, 3, 12],
        )
        self.assertEqual(
            [
                dimension(
                    "gcp",
                    size,
                    "apache.bifromq-4.0.0-incubating-on-gke-standard",
                    "node_hours",
                )
                for size in ("small", "medium", "large")
            ],
            [2190, 2190, 8760],
        )
        self.assertEqual(
            [
                dimension(
                    "gcp",
                    size,
                    "gcp.ordered-mqtt-pubsub-adapter",
                    "node_count",
                )
                for size in ("small", "medium", "large")
            ],
            [0, 0, 4],
        )
        self.assertEqual(
            [
                dimension(
                    "gcp",
                    size,
                    "gcp.ordered-mqtt-pubsub-adapter",
                    "node_hours",
                )
                for size in ("small", "medium", "large")
            ],
            [0, 0, 2920],
        )

    def test_offline_fixtures_retain_exact_capacity_gates(self) -> None:
        assignment = contract.assignment_for_bundle("azure", "gcp")
        specification = contract.build_rds(
            assignment,
            self.profile,
            self.catalog,
            size="large",
        )
        self.assertEqual(
            specification["readiness"],
            {
                "status": "offline_contract_fixture",
                "blocking_gate_ids": contract.blocking_gate_ids(
                    "large", ["azure", "gcp"], assignment
                ),
            },
        )

    def test_every_atomic_dimension_has_one_typed_binding(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("azure", "gcp"),
            self.profile,
            self.catalog,
            size="large",
        )
        dimensions = [
            dimension
            for selection in specification["component_selections"]
            for dimension in selection["dimensions"]
        ]
        self.assertEqual(len(specification["bindings"]), len(dimensions))
        self.assertEqual(
            {item["source_ref"] for item in specification["bindings"]},
            {item["dimension_id"] for item in dimensions},
        )
        cosmos_mode = next(
            item
            for item in specification["bindings"]
            if item["source_ref"].endswith(".capacity_mode")
        )
        self.assertEqual(cosmos_mode["value_type"], "string")
        self.assertEqual(
            cosmos_mode["destination_input_id"],
            "input.deployable_selection.capacity_mode",
        )

    def test_tampered_dimension_evidence_is_rejected(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("aws", "gcp"),
            self.profile,
            self.catalog,
        )
        invalid = copy.deepcopy(specification)
        invalid["component_selections"][0]["dimensions"][0]["evidence_reference"] = (
            "sha256:" + ("0" * 64)
        )
        invalid["digest"] = contract.rds_digest(invalid)
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_rds(
                invalid,
                self.rds_schema,
                self.profile,
                self.catalog,
            )
        self.assertEqual(raised.exception.code, "RDS_V2_DIMENSION_MISMATCH")

    def test_unknown_eventing_reference_fails_with_stable_error(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("aws", "gcp"),
            self.profile,
            self.catalog,
        )
        invalid = copy.deepcopy(specification)
        invalid["optimization_context"]["eventing_scenario_ref"]["id"] = (
            "eventing-custom-v1"
        )
        invalid["digest"] = contract.rds_digest(invalid)
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_rds(
                invalid,
                self.rds_schema,
                self.profile,
                self.catalog,
            )
        self.assertEqual(raised.exception.code, "RDS_V2_EVENTING_MISMATCH")

    def test_pricing_evidence_must_match_selected_providers(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("aws", "gcp"),
            self.profile,
            self.catalog,
        )
        invalid = copy.deepcopy(specification)
        invalid["optimization_context"]["pricing_evidence_refs"] = [
            invalid["optimization_context"]["pricing_evidence_refs"][0]
        ]
        invalid["digest"] = contract.rds_digest(invalid)
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_rds(
                invalid,
                self.rds_schema,
                self.profile,
                self.catalog,
            )
        self.assertEqual(raised.exception.code, "RDS_V2_EVIDENCE_MISMATCH")

    def test_deployment_ready_large_cosmos_rejects_unresolved_ru_value(self) -> None:
        active_profile = copy.deepcopy(self.profile)
        active_profile["lifecycle_status"] = "active"
        contract.redigest_architecture(active_profile)
        active_catalog = copy.deepcopy(self.catalog)
        active_catalog["lifecycle_status"] = "active"
        contract.redigest_architecture(active_catalog)
        specification = contract.build_rds(
            contract.assignment_for_bundle("azure", "aws"),
            active_profile,
            active_catalog,
            size="large",
        )
        specification["readiness"] = {
            "status": "deployment_ready",
            "blocking_gate_ids": [],
        }
        specification["digest"] = contract.rds_digest(specification)
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_rds(
                specification,
                self.rds_schema,
                active_profile,
                active_catalog,
            )
        self.assertEqual(raised.exception.code, "RDS_V2_CAPACITY_UNRESOLVED")

    def test_offline_rta_fixtures_do_not_claim_optimizer_costs(self) -> None:
        paths = sorted(
            (contract.ARCH_V2 / "fixtures" / "valid").glob("*-resolved.json")
        )
        five_layer_fixture_count = 0
        for path in paths:
            resolution = contract.read_json(path)
            if (
                resolution["architecture_profile_ref"]["id"]
                != "five-layer-baseline"
            ):
                continue
            five_layer_fixture_count += 1
            with self.subTest(path=path.name):
                self.assertEqual(
                    resolution["resolution_status"],
                    "offline_contract_fixture",
                )
                self.assertEqual(resolution["cost_summary"]["monthly_total"], "0")
                self.assertTrue(
                    all(
                        item["cost_contribution"]["monthly_amount"] == "0"
                        for item in (
                            *resolution["component_assignments"],
                            *resolution["resolved_edges"],
                        )
                    )
                )
        self.assertGreater(five_layer_fixture_count, 0)

    def test_l3_hot_and_l5_mismatch_fails_before_selection(self) -> None:
        assignment = contract.assignment_for_bundle("aws", "azure")
        assignment["component.visualization"] = "gcp"
        with self.assertRaises(contract.ContractError) as raised:
            contract.build_rds(
                assignment,
                self.profile,
                self.catalog,
            )
        self.assertEqual(
            raised.exception.code,
            "PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED",
        )

    def test_provider_specific_json_api_plugins_have_distinct_ownership(self) -> None:
        index = contract.service_component_index()
        self.assertIn(
            ("aws", "aws.grafana-marcusolsson-json-datasource"),
            index,
        )
        self.assertIn(
            ("azure", "azure.grafana-marcusolsson-json-datasource"),
            index,
        )
        self.assertNotIn(("aws", "grafana.marcusolsson-json-datasource"), index)

    def test_tampered_dimension_value_is_rejected(self) -> None:
        specification = contract.build_rds(
            contract.assignment_for_bundle("aws", "gcp"),
            self.profile,
            self.catalog,
        )
        invalid = copy.deepcopy(specification)
        invalid["component_selections"][0]["dimensions"][0]["value"] = 99
        invalid["digest"] = contract.rds_digest(invalid)
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_rds(
                invalid,
                self.rds_schema,
                self.profile,
                self.catalog,
            )
        self.assertEqual(raised.exception.code, "RDS_V2_DIMENSION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
