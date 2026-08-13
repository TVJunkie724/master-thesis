from __future__ import annotations

import importlib.util
from decimal import Decimal
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync_six_layer_eventing_contracts.py"


def _load_contract_module():
    spec = importlib.util.spec_from_file_location("six_layer_contract_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CONTRACT = _load_contract_module()


class SixLayerEventingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime, cls.profile, cls.catalog, cls.providers, cls.registry = (
            CONTRACT.load_bundle()
        )
        cls.five = CONTRACT.five_profile()

    def test_contract_bundle_is_valid_and_digest_locked(self) -> None:
        CONTRACT.validate_source()
        self.assertEqual(self.profile["lifecycle_status"], "active")
        self.assertEqual(self.catalog["lifecycle_status"], "active")

    def test_only_eventing_component_is_added_and_inherited_ports_are_event_routed(
        self,
    ) -> None:
        five_components = {
            item["component_id"]: item for item in self.five["components"]
        }
        six_components = {
            item["component_id"]: item for item in self.profile["components"]
        }
        self.assertEqual(
            set(six_components) - set(five_components),
            {"component.eventing"},
        )
        event_routed_ports = {
            "component.ingestion": {
                "input_port_ids": ["port.ingestion.device-command-in"],
                "output_port_ids": ["port.ingestion.eventing-out"],
            },
            "component.processing": {
                "input_port_ids": ["port.processing.eventing-in"],
                "output_port_ids": ["port.processing.eventing-out"],
            },
            "component.hot-storage": {
                "input_port_ids": ["port.hot-storage.eventing-in"],
                "output_port_ids": five_components["component.hot-storage"][
                    "output_port_ids"
                ],
            },
        }
        for component_id, component in five_components.items():
            actual = dict(six_components[component_id])
            expected = dict(component)
            if component_id in event_routed_ports:
                for field, value in event_routed_ports[component_id].items():
                    expected[field] = value
            self.assertEqual(actual, expected)
        self.assertEqual(len(self.profile["responsibilities"]), 6)

    def test_event_edges_use_responsibility_named_logical_ports(self) -> None:
        self.assertEqual(
            {
                edge["edge_id"]: (
                    edge["source_port_id"],
                    edge["destination_port_id"],
                )
                for edge in self.profile["edges"]
                if "eventing" in edge["edge_id"]
            },
            {
                "edge.ingestion-to-eventing": (
                    "port.ingestion.eventing-out",
                    "port.eventing.ingestion-in",
                ),
                "edge.eventing-to-processing": (
                    "port.eventing.processing-out",
                    "port.processing.eventing-in",
                ),
                "edge.processing-to-eventing": (
                    "port.processing.eventing-out",
                    "port.eventing.processing-in",
                ),
                "edge.eventing-to-ingestion": (
                    "port.eventing.ingestion-out",
                    "port.ingestion.device-command-in",
                ),
                "edge.eventing-to-hot-storage": (
                    "port.eventing.hot-storage-out",
                    "port.hot-storage.eventing-in",
                ),
            },
        )

    def test_event_layer_provider_bundles_match_frozen_service_decision(self) -> None:
        expected = {
            provider: {item["service_id"] for item in CONTRACT.event_services(provider)}
            for provider in CONTRACT.PROVIDERS
        }
        actual = {
            item["provider"]: set(item["service_ids"])
            for item in self.catalog["components"]
            if item["logical_component_ids"] == ["component.eventing"]
        }
        self.assertEqual(actual, expected)

    def test_all_local_and_directed_event_routes_are_registered(self) -> None:
        event_edges = [
            item
            for item in self.catalog["edge_implementations"]
            if item["logical_edge_ids"][0] in CONTRACT.EVENT_EDGES
        ]
        self.assertEqual(
            len(event_edges),
            len(CONTRACT.EVENT_EDGES) * len(CONTRACT.PROVIDERS) ** 2,
        )
        directed_pairs = {
            (
                item["source_component_ids"][0].split(".")[1],
                item["destination_component_ids"][0].split(".")[1],
            )
            for item in event_edges
        }
        self.assertEqual(
            directed_pairs,
            {
                (source, destination)
                for source in CONTRACT.PROVIDERS
                for destination in CONTRACT.PROVIDERS
            },
        )
        for item in event_edges:
            local = item["transfer_route_class"] == "same_provider_same_region"
            self.assertEqual(item["glue_component_ids"] == [], local)
            self.assertEqual(
                item["mechanism"] == "provider_native_trigger",
                local,
            )

    def test_provider_profiles_cover_the_eventing_component_and_edges(self) -> None:
        for provider, document in self.providers.items():
            component = next(
                item
                for item in document["component_mappings"]
                if item["component_id"] == "component.eventing"
            )
            self.assertEqual(
                component["deployment_component_candidates"],
                [f"deployment.{provider}.eventing.v1"],
            )
            self.assertEqual(
                {
                    item["edge_id"]
                    for item in document["edge_mappings"]
                    if "eventing" in item["edge_id"]
                },
                set(CONTRACT.EVENT_EDGES),
            )

    def test_manifest_pins_the_reviewed_five_layer_boundary(self) -> None:
        manifest = CONTRACT.read_json(CONTRACT.MANIFEST_PATH)
        self.assertEqual(
            manifest["inherited_implementation_commit"],
            CONTRACT.INHERITED_IMPLEMENTATION_COMMIT,
        )
        self.assertEqual(
            manifest["inherited_audit_commit"],
            CONTRACT.INHERITED_AUDIT_COMMIT,
        )
        self.assertEqual(
            manifest["inherited_profile_ref"]["digest"],
            self.five["content_digest"],
        )
        self.assertEqual(
            manifest["inherited_catalog_ref"]["digest"],
            "sha256:3396848028a5b8862e1c948a8017cd8e7bb7d118a0ee5edc120cd3d7a3956c1d",
        )
        six_layer_sources = {
            artifact["artifact_id"]: artifact["repository_source_path"]
            for artifact in self.catalog["package_artifacts"]
            if artifact["artifact_id"]
            in {
                "artifact.platform.aws.six-layer-domain",
                "artifact.platform.azure.six-layer-domain",
                "artifact.platform.gcp.six-layer-domain",
                "artifact.shared.phase8-six-layer-bridge-runtime",
            }
        }
        self.assertEqual(
            six_layer_sources,
            {
                "artifact.platform.aws.six-layer-domain": (
                    "3-cloud-deployer/src/providers/aws/lambda_functions/"
                    "six-layer-domain"
                ),
                "artifact.platform.azure.six-layer-domain": (
                    "3-cloud-deployer/src/providers/azure/azure_functions/"
                    "six-layer-domain"
                ),
                "artifact.platform.gcp.six-layer-domain": (
                    "3-cloud-deployer/src/providers/gcp/containers/six-layer-domain"
                ),
                "artifact.shared.phase8-six-layer-bridge-runtime": (
                    "3-cloud-deployer/src/runtime/six_layer_eventing"
                ),
            },
        )
        self.assertEqual(
            set(manifest["supported_directed_provider_pairs"]),
            {
                f"{source}-to-{destination}"
                for source in CONTRACT.PROVIDERS
                for destination in CONTRACT.PROVIDERS
                if source != destination
            },
        )

    def test_topology_cost_registry_covers_and_reconciles_all_81_cases(self) -> None:
        registry = CONTRACT.read_json(CONTRACT.COST_REGISTRY_PATH)
        reviewed = json.loads(CONTRACT.EVENT_COST_RESULTS.read_text(encoding="utf-8"))
        reviewed_by_scenario = {
            item["scenario_id"]: item for item in reviewed["scenarios"]
        }
        self.assertEqual(len(registry["scenarios"]), 3)
        for scenario in registry["scenarios"]:
            placements = scenario["placements"]
            self.assertEqual(len(placements), 27)
            self.assertEqual(
                {
                    (
                        item["ingestion_provider"],
                        item["eventing_provider"],
                        item["processing_provider"],
                    )
                    for item in placements
                },
                {
                    (ingestion, eventing, processing)
                    for ingestion in CONTRACT.PROVIDERS
                    for eventing in CONTRACT.PROVIDERS
                    for processing in CONTRACT.PROVIDERS
                },
            )
            for placement in placements:
                allocated = sum(
                    (
                        Decimal(item["monthly_amount_usd"])
                        for item in placement["component_costs"]
                    ),
                    Decimal(0),
                ) + sum(
                    (
                        Decimal(item["monthly_transfer_amount_usd"])
                        for item in placement["route_transfer_costs"]
                    ),
                    Decimal(0),
                )
                self.assertEqual(
                    allocated,
                    Decimal(placement["event_scope_total_usd"]),
                )
                if placement["topology"] == "single_cloud":
                    self.assertEqual(
                        placement["bridge_addition_total_usd"],
                        "0.000000000",
                    )
                    self.assertEqual(placement["route_transfer_costs"], [])

            reviewed_three_provider = {
                item["placement_id"]: item
                for item in reviewed_by_scenario[scenario["scenario_id"]][
                    "three_provider_results"
                ]
            }
            generated_three_provider = {
                item["placement_id"]: item
                for item in placements
                if item["topology"] == "hub_and_spoke"
            }
            self.assertEqual(
                {
                    key: value["event_scope_total_usd"]
                    for key, value in generated_three_provider.items()
                },
                {
                    key: value["event_scope_total_usd"]
                    for key, value in reviewed_three_provider.items()
                },
            )


if __name__ == "__main__":
    unittest.main()
