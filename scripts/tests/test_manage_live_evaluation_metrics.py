from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import manage_live_evaluation_metrics as metrics

DIGEST = "sha256:" + "a" * 64


def _at(offset_ms: int) -> str:
    instant = datetime(2026, 8, 28, 12, tzinfo=timezone.utc) + timedelta(
        milliseconds=offset_ms
    )
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sample(sequence: int, sample_set: str, start_ms: int) -> dict:
    return {
        "trace_id": f"trace-{sample_set}-{sequence}",
        "sequence": sequence,
        "sample_set": sample_set,
        "direction": "telemetry",
        "payload_bytes": 256,
        "status": "succeeded",
        "stages": [
            {
                "stage_id": "simulator_sent",
                "provider": None,
                "layer": "simulator",
                "observed_at": _at(start_ms),
                "clock_source": "simulator",
                "event_id": f"event-{sample_set}-{sequence}",
            },
            {
                "stage_id": "l1_accepted",
                "provider": "aws",
                "layer": "L1",
                "observed_at": _at(start_ms + 10),
                "clock_source": "provider",
                "event_id": f"event-{sample_set}-{sequence}",
            },
            {
                "stage_id": "event_layer_durable",
                "provider": "aws",
                "layer": "LE",
                "observed_at": _at(start_ms + 30),
                "clock_source": "provider",
                "event_id": f"event-{sample_set}-{sequence}",
            },
            {
                "stage_id": "l4_queryable",
                "provider": "aws",
                "layer": "L4",
                "observed_at": _at(start_ms + 80 + sequence),
                "clock_source": "application",
                "event_id": f"event-{sample_set}-{sequence}",
            },
        ],
        "retry_count": 0,
        "duplicate_count": 0,
        "ordering_ok": True,
        "dlq_observed": False,
        "failure_code": None,
    }


def _record() -> dict:
    return {
        "schema_version": "live-evaluation-metrics.v1",
        "evidence_status": "live_observation",
        "run_id": "run-small-local-aws-001",
        "run_kind": "provider_local",
        "subject_id": "small-local-aws",
        "scenario_id": "small-local-aws",
        "candidate_evidence_digest": DIGEST,
        "architecture_contract": "six-layer-eventing@1",
        "source_revision": "abcdef1234567",
        "workload_digest": DIGEST,
        "simulator_digest": DIGEST,
        "provider_scope": ["aws"],
        "started_at": _at(0),
        "completed_at": _at(10000),
        "clock": {
            "synchronized": True,
            "method": "ntp-and-provider-timestamps",
            "checked_at": _at(0),
            "max_observed_skew_ms": 5,
        },
        "protocol": {
            "warmup_messages_per_direction": 1,
            "measured_messages_per_direction": 2,
            "payload_bytes": 256,
            "cadence_ms": 1000,
            "cold_start_observed": True,
            "directions": ["telemetry"],
            "expected_paths": [
                {
                    "direction": "telemetry",
                    "stage_ids": [
                        "simulator_sent",
                        "l1_accepted",
                        "event_layer_durable",
                        "l4_queryable",
                    ],
                }
            ],
            "notes": ["Unit-test fixture; not live evidence."],
        },
        "lifecycle": [
            {
                "phase": "terraform_apply",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(0),
                "completed_at": _at(1000),
                "duration_ms": 1000,
            },
            {
                "phase": "terraform_destroy",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(8000),
                "completed_at": _at(9000),
                "duration_ms": 1000,
            },
        ],
        "message_samples": [
            _sample(1, "warmup", 1000),
            _sample(1, "measured", 2000),
            _sample(2, "measured", 4000),
        ],
        "resources": [
            {
                "provider": "aws",
                "region": "eu-central-1",
                "layer": "L1",
                "service": "iot-core",
                "sku": None,
                "count": 1,
            }
        ],
        "cost": {
            "currency": "USD",
            "budget_cap_usd": 10,
            "estimated_monthly_total_usd": "100.00",
            "observed_incremental_cost_usd": None,
            "observation_started_at": None,
            "observation_completed_at": None,
            "source_artifact_path": None,
        },
        "cleanup": {
            "completed_at": _at(9000),
            "inventory_clean": True,
            "residual_count": 0,
            "residual_types": [],
        },
        "limitations": ["Synthetic test fixture."],
    }


def test_metrics_record_validates_semantic_counts_and_paths() -> None:
    result = metrics.validate_metrics(_record())

    assert result == {
        "run_id": "run-small-local-aws-001",
        "run_kind": "provider_local",
        "subject_id": "small-local-aws",
        "measured_sample_count": 2,
    }


def test_missing_measurement_is_rejected() -> None:
    record = _record()
    record["message_samples"].pop()

    with pytest.raises(metrics.LiveMetricsError, match="measured count"):
        metrics.validate_metrics(record)


def test_successful_trace_must_match_declared_path() -> None:
    record = _record()
    record["message_samples"][1]["stages"].pop(1)

    with pytest.raises(metrics.LiveMetricsError, match="expected path"):
        metrics.validate_metrics(record)


def test_component_probe_cannot_claim_final_scenario() -> None:
    record = _record()
    record["run_kind"] = "component_probe"

    with pytest.raises(metrics.LiveMetricsError, match="must not claim"):
        metrics.validate_metrics(record)


def test_summary_creates_csv_tables_and_svg_charts(tmp_path: Path) -> None:
    record = _record()
    output_dir = tmp_path / "summary"

    metrics.summarize_metrics([record], output_dir)

    expected = {
        "run-summary.csv",
        "stage-latency.csv",
        "lifecycle.csv",
        "resources.csv",
        "end-to-end-latency-p95.svg",
        "lifecycle-duration.svg",
    }
    assert {path.name for path in output_dir.iterdir()} == expected
    with (output_dir / "run-summary.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["measured_messages"] == "2"
    assert rows[0]["success_rate"] == "1.000"
    assert float(rows[0]["p95_ms"]) > 80
    assert "Measured end-to-end latency" in (
        output_dir / "end-to-end-latency-p95.svg"
    ).read_text(encoding="utf-8")


def test_summary_does_not_overwrite_existing_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "summary"
    output_dir.mkdir()

    with pytest.raises(metrics.LiveMetricsError, match="already exists"):
        metrics.summarize_metrics([_record()], output_dir)
