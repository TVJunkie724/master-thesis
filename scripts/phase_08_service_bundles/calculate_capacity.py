#!/usr/bin/env python3
"""Calculate deterministic Phase 8 complete-service capacity evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_service_bundles"
SCENARIO_PATH = EVIDENCE_ROOT / "workload-scenarios.json"
CAPACITY_PATH = EVIDENCE_ROOT / "capacity-matrix.json"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def canonical_json(value: Any) -> bytes:
    def default(item: Any) -> Any:
        if isinstance(item, Decimal):
            return format(item, "f")
        raise TypeError(type(item).__name__)

    return json.dumps(
        value,
        default=default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def normalized_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def ceil_decimal(value: Decimal) -> int:
    return math.ceil(value)


def next_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def decimal_text(value: Decimal, places: int = 12) -> str:
    rendered = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def calculate_scenario(
    scenario: dict[str, Any],
    fixed: dict[str, Any],
    units: dict[str, Any],
) -> dict[str, Any]:
    # Device count and interval are the canonical integer inputs.  The
    # human-readable rate in the evidence is only a decimal projection and
    # must not introduce rounding drift into byte/capacity calculations.
    rate = Decimal(scenario["device_count"]) / Decimal(
        scenario["telemetry_interval_seconds"]
    )
    payload_bytes = Decimal(str(scenario["average_payload_kib"])) * Decimal(
        units["kib_bytes"]
    )
    batch_seconds = Decimal(fixed["storage_batch_interval_minutes"] * 60)
    batch_bytes = rate * payload_bytes * batch_seconds
    task_limit = Decimal(fixed["storage_task_max_input_mib"] * units["mib_bytes"])
    object_limit = Decimal(
        fixed["storage_object_max_uncompressed_mib"] * units["mib_bytes"]
    )
    byte_tasks = max(1, ceil_decimal(batch_bytes / task_limit))
    azure_partition_tasks = max(
        1,
        ceil_decimal(
            Decimal(scenario["device_count"])
            / Decimal(fixed["azure_mover_max_device_partitions_per_task"])
        ),
    )
    dashboard_qps = (
        Decimal(scenario["aggregate_dashboard_refreshes_per_hour"])
        * Decimal(scenario["api_calls_per_aggregate_dashboard_refresh"])
        / Decimal(3600)
    )
    reader_concurrency = max(
        2,
        ceil_decimal(
            dashboard_qps
            * Decimal(fixed["reader_timeout_seconds"])
            * Decimal("1.25")
        ),
    )
    raw_shards = next_power_of_two(max(1, ceil_decimal(rate / Decimal(400))))
    monthly_raw_bytes = Decimal(scenario["messages_per_month"]) * payload_bytes
    per_device_hot_bytes = (
        monthly_raw_bytes
        * Decimal(scenario["hot_boundary_months"])
        / Decimal(scenario["device_count"])
    )
    rollup_points = 30 * 24
    return {
        "scenario_id": scenario["scenario_id"],
        "size": scenario["size"],
        "derived": {
            "canonical_payload_bytes": decimal_text(payload_bytes),
            "canonical_batch_bytes": decimal_text(batch_bytes),
            "canonical_batch_mib": decimal_text(
                batch_bytes / Decimal(units["mib_bytes"])
            ),
            "storage_byte_derived_tasks": byte_tasks,
            "azure_partition_derived_tasks": azure_partition_tasks,
            "aws_storage_tasks": byte_tasks,
            "azure_storage_tasks": max(byte_tasks, azure_partition_tasks),
            "gcp_storage_tasks": byte_tasks,
            "storage_objects_per_batch_lower_bound": max(
                1, ceil_decimal(batch_bytes / object_limit)
            ),
            "aggregate_dashboard_query_rate_per_second": decimal_text(
                dashboard_qps
            ),
            "reader_max_concurrent_requests": reader_concurrency,
            "firestore_timestamp_shards": raw_shards,
            "firestore_planned_raw_writes_per_shard_second": decimal_text(
                rate / Decimal(raw_shards)
            ),
            "monthly_raw_payload_bytes": decimal_text(monthly_raw_bytes),
            "hot_payload_gib": decimal_text(
                monthly_raw_bytes
                * Decimal(scenario["hot_boundary_months"])
                / Decimal(units["gib_bytes"])
            ),
            "cool_payload_gib": decimal_text(
                monthly_raw_bytes
                * Decimal(
                    scenario["cool_boundary_months"]
                    - scenario["hot_boundary_months"]
                )
                / Decimal(units["gib_bytes"])
            ),
            "archive_payload_gib": decimal_text(
                monthly_raw_bytes
                * Decimal(
                    scenario["archive_boundary_months"]
                    - scenario["cool_boundary_months"]
                )
                / Decimal(units["gib_bytes"])
            ),
            "cosmos_max_hot_payload_bytes_per_device": decimal_text(
                per_device_hot_bytes
            ),
            "cosmos_logical_partition_below_20_gb": (
                per_device_hot_bytes < Decimal(20_000_000_000)
            ),
            "maximum_aggregate_rollup_points": rollup_points,
            "l4_inspection_reads_per_month": (
                fixed["l4_inspection_sessions_per_month"]
                * fixed["l4_reads_per_inspection_session"]
            ),
        },
        "provider_admission": {
            "aws": {
                "status": "theoretically_admissible",
                "live_gates": [
                    "dynamodb_partition_distribution",
                    "reader_latency_and_quota",
                    "twinmaker_query_behavior"
                ]
            },
            "azure": {
                "status": "conditionally_theoretically_admissible",
                "cosmos_capacity_mode": (
                    "autoscale" if scenario["size"] == "large" else "serverless"
                ),
                "published_serverless_partition_ru_per_second": 5000,
                "published_logical_partition_limit_bytes": 20000000000,
                "request_charge_fixture_required_before_activation": True,
                "live_gates": [
                    "cosmos_request_charge_fixture",
                    "cosmos_partition_distribution",
                    "reader_latency_and_quota"
                ]
            },
            "gcp": {
                "status": "conditionally_theoretically_admissible",
                "live_gates": [
                    "firestore_gradual_ramp_and_transaction_contention",
                    "reader_latency_and_quota",
                    "bifromq_cluster_behavior"
                ]
            }
        }
    }


def calculate() -> dict[str, Any]:
    inputs = load_json(SCENARIO_PATH)
    results = [
        calculate_scenario(
            scenario,
            inputs["fixed_dimensions"],
            inputs["unit_contract"],
        )
        for scenario in inputs["core_scenarios"]
    ]
    return {
        "$schema": "./schemas/package-artifact.schema.json",
        "schema_version": "1.0.0",
        "package_id": "phase-08-complete-service-bundles@1",
        "artifact_id": "capacity-matrix",
        "input_digest": normalized_digest(inputs),
        "formula_contract": {
            "firestore_timestamp_shards": "next_power_of_two(max(1, ceil(peak_raw_writes_per_second / 400)))",
            "reader_max_concurrent_requests": "max(2, ceil(aggregate_query_rate_per_second * 10 * 1.25))",
            "storage_byte_derived_tasks": "max(1, ceil(canonical_batch_bytes / 512_MiB))",
            "azure_storage_tasks": "max(byte_derived_tasks, ceil(device_count / 1000))",
            "storage_objects_per_batch_lower_bound": "max(1, ceil(canonical_batch_bytes / 64_MiB))",
            "hot_residence_months": "H",
            "cool_residence_months": "C-H",
            "archive_residence_months": "A-C"
        },
        "scenario_results": results,
        "global_live_status": "live_capacity_pending",
        "decision_scope": "offline_theoretical_admission_only"
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    calculated = calculate()
    rendered = json.dumps(calculated, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        CAPACITY_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {CAPACITY_PATH.relative_to(REPOSITORY_ROOT)}")
        return 0
    if not CAPACITY_PATH.exists():
        print(f"missing {CAPACITY_PATH.relative_to(REPOSITORY_ROOT)}")
        return 1
    current = CAPACITY_PATH.read_text(encoding="utf-8")
    if current != rendered:
        print("capacity-matrix.json is stale; run calculate_capacity.py --write")
        return 1
    print("phase-08-service-bundles capacity matrix: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
