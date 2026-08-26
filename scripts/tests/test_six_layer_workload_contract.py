"""Tests for the synchronized Six-layer Workload v1 contract."""

from __future__ import annotations

import copy
import json
import unittest

from scripts import sync_six_layer_workload_contract as contract


class SixLayerWorkloadContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = contract.expected_documents()
        self.schema = json.loads(self.documents["v1/workload.schema.json"])
        self.catalog = json.loads(self.documents["v1/eventing-scenario-catalog.json"])
        self.small = json.loads(self.documents["v1/fixtures/valid/core-small.json"])

    def test_source_and_all_generated_copies_are_exact(self) -> None:
        expected = contract.contract_digest(self.documents)
        self.assertEqual(contract.check(), expected)

    def test_three_frozen_core_scenarios_validate(self) -> None:
        for size in ("small", "medium", "large"):
            contract.validate_workload(
                json.loads(self.documents[f"v1/fixtures/valid/core-{size}.json"]),
                schema=self.schema,
                catalog=self.catalog,
            )

    def test_retired_feature_and_implementation_flags_are_rejected(self) -> None:
        for field in contract.RETIRED_FIELDS:
            payload = copy.deepcopy(self.small)
            payload[field] = True
            with self.assertRaisesRegex(
                contract.WorkloadContractError,
                "Additional properties are not allowed",
            ):
                contract.validate_workload(
                    payload,
                    schema=self.schema,
                    catalog=self.catalog,
                )

    def test_retention_is_strictly_increasing(self) -> None:
        for hot, cool, archive in ((1, 1, 12), (2, 1, 12), (1, 12, 12)):
            payload = copy.deepcopy(self.small)
            payload["hotStorageDurationInMonths"] = hot
            payload["coolStorageDurationInMonths"] = cool
            payload["archiveStorageDurationInMonths"] = archive
            with self.assertRaises(contract.WorkloadContractError) as raised:
                contract.validate_workload(
                    payload,
                    schema=self.schema,
                    catalog=self.catalog,
                )
            self.assertEqual(
                raised.exception.code,
                "SIX_LAYER_WORKLOAD_V1_RETENTION_INVALID",
            )

    def test_eventing_scenario_is_a_closed_reference_not_inline_input(self) -> None:
        payload = copy.deepcopy(self.small)
        payload["eventingScenario"] = {"events_per_month": 1}
        with self.assertRaises(contract.WorkloadContractError) as raised:
            contract.validate_workload(
                payload,
                schema=self.schema,
                catalog=self.catalog,
            )
        self.assertEqual(
            raised.exception.code,
            "SIX_LAYER_WORKLOAD_V1_SCHEMA_INVALID",
        )

    def test_custom_eventing_scenario_id_is_rejected(self) -> None:
        payload = copy.deepcopy(self.small)
        payload["eventingScenarioId"] = "custom-eventing"
        with self.assertRaises(contract.WorkloadContractError) as raised:
            contract.validate_workload(
                payload,
                schema=self.schema,
                catalog=self.catalog,
            )
        self.assertEqual(
            raised.exception.code,
            "SIX_LAYER_WORKLOAD_V1_SCHEMA_INVALID",
        )

    def test_workload_field_set_is_exact(self) -> None:
        self.assertEqual(tuple(self.schema["properties"]), contract.WORKLOAD_FIELDS)
        self.assertEqual(set(self.schema["required"]), set(contract.WORKLOAD_FIELDS))
        self.assertTrue(
            set(contract.RETIRED_FIELDS).isdisjoint(self.schema["properties"])
        )

    def test_catalog_is_exactly_the_immutable_three_scenarios(self) -> None:
        self.assertEqual(
            tuple(item["scenario_id"] for item in self.catalog["scenarios"]),
            contract.SCENARIO_IDS,
        )
        self.assertEqual(
            self.catalog["decision_byte_digest"],
            contract.file_digest(contract.EVENTING_DECISION),
        )
        self.assertEqual(
            self.catalog["scenario_source_byte_digest"],
            contract.file_digest(contract.EVENTING_SOURCE),
        )
        self.assertEqual(
            self.catalog["scenario_source_content_digest"],
            contract.eventing_content_digest(
                contract.read_json(contract.EVENTING_SOURCE)
            ),
        )


if __name__ == "__main__":
    unittest.main()
