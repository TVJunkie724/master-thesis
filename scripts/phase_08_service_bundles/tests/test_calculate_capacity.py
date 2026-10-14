from __future__ import annotations

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


class CapacityCalculatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calculator = load_module("calculate_capacity.py")
        cls.result = cls.calculator.calculate()
        cls.by_size = {
            item["size"]: item["derived"]
            for item in cls.result["scenario_results"]
        }

    def test_exact_scenario_ids_and_live_boundary(self) -> None:
        self.assertEqual(
            {item["scenario_id"] for item in self.result["scenario_results"]},
            {"core-small-v2", "core-medium-v2", "core-large-v2"},
        )
        self.assertEqual(self.result["global_live_status"], "live_capacity_pending")

    def test_firestore_shards_are_exact(self) -> None:
        self.assertEqual(
            [self.by_size[size]["firestore_timestamp_shards"] for size in ("small", "medium", "large")],
            [1, 1, 16],
        )

    def test_reader_concurrency_is_exact(self) -> None:
        self.assertEqual(
            [self.by_size[size]["reader_max_concurrent_requests"] for size in ("small", "medium", "large")],
            [2, 3, 42],
        )

    def test_storage_tasks_and_objects_are_exact(self) -> None:
        self.assertEqual(
            [self.by_size[size]["azure_storage_tasks"] for size in ("small", "medium", "large")],
            [1, 4, 30],
        )
        self.assertEqual(self.by_size["large"]["storage_byte_derived_tasks"], 3)
        self.assertEqual(self.by_size["large"]["storage_objects_per_batch_lower_bound"], 19)

    def test_calculation_uses_exact_integer_primary_inputs(self) -> None:
        self.assertEqual(self.by_size["small"]["canonical_batch_bytes"], "64000")
        self.assertEqual(self.by_size["medium"]["canonical_batch_bytes"], "20480000")
        self.assertEqual(self.by_size["large"]["canonical_batch_bytes"], "1228800000")

    def test_cosmos_partition_and_rollup_bounds(self) -> None:
        for derived in self.by_size.values():
            self.assertTrue(derived["cosmos_logical_partition_below_20_gb"])
            self.assertEqual(derived["maximum_aggregate_rollup_points"], 720)


if __name__ == "__main__":
    unittest.main()
