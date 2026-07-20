from __future__ import annotations

import copy
import importlib.util
import math
import unittest
from decimal import Decimal
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "calculate_scenarios.py"
SPEC = importlib.util.spec_from_file_location(
    "phase_08_calculate_scenarios",
    SCRIPT_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT_PATH}")
CALCULATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CALCULATOR)


class ScenarioCalculationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario = CALCULATOR.load_json(CALCULATOR.SCENARIO_PATH)
        cls.domain = CALCULATOR.load_json(CALCULATOR.DOMAIN_PATH)
        cls.pricing = CALCULATOR.load_json(CALCULATOR.PRICE_PATH)
        cls.formula = CALCULATOR.load_json(CALCULATOR.FORMULA_PATH)
        cls.capability = CALCULATOR.load_json(CALCULATOR.CAPABILITY_PATH)
        cls.sources = CALCULATOR.load_json(CALCULATOR.SOURCE_PATH)

    def build(
        self,
        *,
        pricing: dict | None = None,
        sources: dict | None = None,
    ) -> dict:
        return CALCULATOR.build_result_from_documents(
            copy.deepcopy(self.scenario),
            copy.deepcopy(self.domain),
            copy.deepcopy(pricing or self.pricing),
            copy.deepcopy(self.formula),
            copy.deepcopy(self.capability),
            copy.deepcopy(sources or self.sources),
        )

    def test_committed_result_is_byte_identical(self) -> None:
        expected = self.build()
        committed = CALCULATOR.load_json(CALCULATOR.RESULT_PATH)
        self.assertEqual(expected, committed)

    def test_source_and_pricing_row_order_do_not_change_result(self) -> None:
        shuffled_sources = copy.deepcopy(self.sources)
        shuffled_sources["sources"].reverse()
        shuffled_pricing = copy.deepcopy(self.pricing)
        for key in (
            "price_intents",
            "selected_bundle_intents",
            "bridge_source_intents",
            "bridge_destination_intents",
            "rejected_member_dimensions",
        ):
            shuffled_pricing[key].reverse()

        self.assertEqual(
            self.build(),
            self.build(
                pricing=shuffled_pricing,
                sources=shuffled_sources,
            ),
        )

    def test_price_mutation_changes_dependent_result_and_digest(self) -> None:
        mutated = copy.deepcopy(self.pricing)
        target = next(
            item
            for item in mutated["price_intents"]
            if item["intent_id"] == "intent.aws.kinesis.shard-hour"
        )
        target["unit_price_usd"] = Decimal("0.019")
        target["tier_schedule"][0]["unit_price_usd"] = Decimal("0.019")

        baseline = self.build()
        changed = self.build(pricing=mutated)
        self.assertNotEqual(
            baseline["result_digest"],
            changed["result_digest"],
        )
        baseline_large = baseline["scenarios"][2]["event_layer_bundle_results"][0][
            "total_monthly_usd"
        ]
        changed_large = changed["scenarios"][2]["event_layer_bundle_results"][0][
            "total_monthly_usd"
        ]
        self.assertNotEqual(baseline_large, changed_large)

    def test_free_tier_boundary_plus_one_request(self) -> None:
        sqs = next(
            item
            for item in self.pricing["price_intents"]
            if item["intent_id"] == "intent.aws.sqs-fifo.request"
        )
        self.assertEqual(
            CALCULATOR.progressive_cost(1_000_000, sqs),
            Decimal(0),
        )
        self.assertEqual(
            CALCULATOR.progressive_cost(1_000_001, sqs),
            Decimal("0.0000005"),
        )

    def test_large_processed_fanout_is_channel_aware(self) -> None:
        channels = CALCULATOR.derive_channels(
            self.scenario["scenarios"][2],
            self.scenario["shared_assumptions"],
        )
        processed = next(
            item for item in channels if item["channel_id"] == "telemetry.processed.v1"
        )
        self.assertEqual(processed["consumer_count"], 5)
        self.assertEqual(processed["base_delivery_count"], 500_000_000)
        self.assertEqual(processed["retry_delivery_count"], 5_000_000)
        self.assertEqual(processed["dead_letter_count"], 500_000)
        self.assertEqual(processed["replay_publish_count"], 2_000_000)
        self.assertEqual(processed["replay_delivery_count"], 10_000_000)

    def test_missing_required_price_intent_fails_closed(self) -> None:
        incomplete = copy.deepcopy(self.pricing)
        incomplete["price_intents"] = [
            item
            for item in incomplete["price_intents"]
            if item["intent_id"] != "intent.azure.functions.compute"
        ]
        with self.assertRaises(KeyError):
            self.build(pricing=incomplete)

    def test_bridge_runtime_is_provider_and_channel_specific(self) -> None:
        result = self.build()
        small = result["scenarios"][0]["directed_pair_bridge_results"]
        aws_small = next(item for item in small if item["source_provider"] == "aws")
        gcp_small = next(item for item in small if item["source_provider"] == "gcp")

        def egress(route: dict) -> dict:
            return next(
                item
                for item in route["cost_contributions"]
                if item["contribution_id"].endswith(".egress")
            )

        aws_quantities = egress(aws_small)["normalized_quantities"]
        gcp_quantities = egress(gcp_small)["normalized_quantities"]
        self.assertEqual(
            aws_quantities["bridge_invocations"],
            sum(
                math.ceil(row["attempts"] / 10)
                for row in aws_quantities["channel_attempts"]
            ),
        )
        self.assertEqual(
            gcp_quantities["bridge_invocations"],
            gcp_quantities["bridge_event_attempts"],
        )
        self.assertEqual(
            gcp_quantities["actual_batch_rule"],
            "one_push_request_per_attempt",
        )

    def test_gcp_large_bridge_worker_count_follows_telemetry_channels(self) -> None:
        result = self.build()
        large = result["scenarios"][2]
        gcp_pair = next(
            item
            for item in large["directed_pair_bridge_results"]
            if item["source_provider"] == "gcp"
        )
        pair_worker = next(
            item
            for item in gcp_pair["cost_contributions"]
            if item["contribution_id"].endswith(".forwarder.worker-pool")
        )
        self.assertEqual(
            pair_worker["normalized_quantities"]["telemetry_channel_count"],
            2,
        )
        self.assertEqual(pair_worker["normalized_quantities"]["instances"], 42)

        gcp_source_placement = next(
            item
            for item in large["three_provider_results"]
            if item["ingress_provider"] == "gcp"
        )
        route_worker = next(
            item
            for item in gcp_source_placement["bridge_cost_contributions"]
            if ".ingress-to-eventing.forwarder.worker-pool" in item["contribution_id"]
        )
        self.assertEqual(
            route_worker["normalized_quantities"]["telemetry_channel_count"],
            1,
        )
        self.assertEqual(route_worker["normalized_quantities"]["instances"], 21)


if __name__ == "__main__":
    unittest.main()
