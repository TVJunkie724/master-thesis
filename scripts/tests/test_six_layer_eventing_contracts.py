from __future__ import annotations

import importlib.util
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

    def test_only_eventing_component_is_added_to_inherited_l1_l5(self) -> None:
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
        for component_id, component in five_components.items():
            self.assertEqual(six_components[component_id], component)
        self.assertEqual(len(self.profile["responsibilities"]), 6)

    def test_event_layer_provider_bundles_match_frozen_service_decision(self) -> None:
        expected = {
            provider: {
                item["service_id"] for item in CONTRACT.event_services(provider)
            }
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
        self.assertEqual(len(event_edges), 36)
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
            set(manifest["supported_directed_provider_pairs"]),
            {
                f"{source}-to-{destination}"
                for source in CONTRACT.PROVIDERS
                for destination in CONTRACT.PROVIDERS
                if source != destination
            },
        )


if __name__ == "__main__":
    unittest.main()
