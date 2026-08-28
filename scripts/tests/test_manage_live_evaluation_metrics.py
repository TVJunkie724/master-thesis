from __future__ import annotations

import csv
import json
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
    trace_prefix = "WARM" if sample_set == "warmup" else "MEAS"
    return {
        "trace_id": f"TRACE-{trace_prefix}{sequence:04d}",
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
                "phase": "terraform_plan",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(0),
                "completed_at": _at(100),
                "duration_ms": 100,
            },
            {
                "phase": "terraform_apply",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(100),
                "completed_at": _at(1000),
                "duration_ms": 900,
            },
            {
                "phase": "infrastructure_ready",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(1000),
                "completed_at": _at(1100),
                "duration_ms": 100,
            },
            {
                "phase": "l1_l3_eventing_ready",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(1100),
                "completed_at": _at(1200),
                "duration_ms": 100,
            },
            {
                "phase": "l4_ready",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(1200),
                "completed_at": _at(1300),
                "duration_ms": 100,
            },
            {
                "phase": "l5_ready",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(1300),
                "completed_at": _at(1400),
                "duration_ms": 100,
            },
            {
                "phase": "terraform_destroy",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(8000),
                "completed_at": _at(9000),
                "duration_ms": 1000,
            },
            {
                "phase": "inventory_reconciliation",
                "provider": "aws",
                "status": "completed",
                "started_at": _at(9000),
                "completed_at": _at(9100),
                "duration_ms": 100,
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
            "completed_at": _at(9100),
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


def test_run_cannot_exceed_cost_guardrail() -> None:
    record = _record()
    record["completed_at"] = _at(61 * 60 * 1000)

    with pytest.raises(metrics.LiveMetricsError, match="60-minute"):
        metrics.validate_metrics(record)


def test_final_run_requires_complete_lifecycle_coverage() -> None:
    record = _record()
    record["lifecycle"] = [
        phase for phase in record["lifecycle"] if phase["phase"] != "l4_ready"
    ]

    with pytest.raises(metrics.LiveMetricsError, match="Lifecycle coverage"):
        metrics.validate_metrics(record)


def test_successful_trace_preserves_one_event_id() -> None:
    record = _record()
    record["message_samples"][1]["stages"][-1]["event_id"] = "event-drifted"

    with pytest.raises(metrics.LiveMetricsError, match="one event ID"):
        metrics.validate_metrics(record)


def test_observed_cost_is_atomic_but_may_arrive_after_cleanup() -> None:
    record = _record()
    record["cost"]["observed_incremental_cost_usd"] = 1.25

    with pytest.raises(metrics.LiveMetricsError, match="requires value, interval"):
        metrics.validate_metrics(record)

    record["cost"].update(
        {
            "observation_started_at": _at(0),
            "observation_completed_at": _at(20_000),
            "source_artifact_path": "cost/aws-run-001.csv",
        }
    )
    assert metrics.validate_metrics(record)["run_id"] == record["run_id"]


def test_metric_collection_rejects_incomparable_final_runs() -> None:
    first = _record()
    second = _record()
    second["run_id"] = "run-small-local-aws-002"
    second["scenario_id"] = "small-local-aws-repeat"
    second["subject_id"] = "small-local-aws-repeat"
    second["source_revision"] = "deadbeef1234567"

    with pytest.raises(metrics.LiveMetricsError, match="not comparable"):
        metrics.validate_metric_collection([first, second])


def test_complete_matrix_gate_reports_missing_scenarios() -> None:
    with pytest.raises(metrics.LiveMetricsError, match="nine-scenario matrix"):
        metrics.validate_metric_collection([_record()], require_complete_matrix=True)


def test_summary_creates_csv_tables_and_svg_charts(tmp_path: Path) -> None:
    record = _record()
    output_dir = tmp_path / "summary"

    metrics.summarize_metrics([record], output_dir)

    expected = {
        "run-summary.csv",
        "stage-latency.csv",
        "lifecycle.csv",
        "resources.csv",
        "cost-observations.csv",
        "end-to-end-latency-p95.svg",
        "lifecycle-duration.svg",
    }
    assert {path.name for path in output_dir.iterdir()} == expected
    with (output_dir / "run-summary.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["measured_messages"] == "2"
    assert rows[0]["success_rate"] == "1.000"
    assert rows[0]["retries"] == "0"
    assert float(rows[0]["p95_ms"]) > 80
    assert "Measured end-to-end latency" in (
        output_dir / "end-to-end-latency-p95.svg"
    ).read_text(encoding="utf-8")


def test_summary_does_not_overwrite_existing_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "summary"
    output_dir.mkdir()

    with pytest.raises(metrics.LiveMetricsError, match="already exists"):
        metrics.summarize_metrics([_record()], output_dir)


def _collection_inputs() -> tuple[dict, dict, dict[str, list[dict]]]:
    record = _record()
    observed_samples = record.pop("message_samples")
    plan = {
        "schema_version": "live-evaluation-sample-plan.v1",
        "samples": [
            {key: value for key, value in sample.items() if key != "stages"}
            for sample in observed_samples
        ],
    }
    checkpoints: dict[str, list[dict]] = {}
    for sample in observed_samples:
        checkpoints[sample["trace_id"]] = [
            {
                "schema_version": "diagnostic-checkpoint.v1",
                "trace_id": sample["trace_id"],
                "stage": stage["stage_id"],
                "provider": stage["provider"] or "aws",
                "component": (
                    "simulator"
                    if stage["stage_id"] == "simulator_sent"
                    else "data-flow-verification"
                    if stage["stage_id"] == "l4_queryable"
                    else "runtime"
                ),
                "status": "passed",
                "observed_at": stage["observed_at"],
                "event_id": stage["event_id"],
                "event_type": "telemetry.received.v1",
            }
            for stage in sample["stages"]
        ]
    return record, plan, checkpoints


def test_checkpoint_collection_assembles_schema_valid_metrics() -> None:
    template, plan, checkpoints = _collection_inputs()

    record = metrics.assemble_metrics(template, plan, checkpoints)

    assert len(record["message_samples"]) == 3
    assert record["message_samples"][0]["stages"][0]["clock_source"] == "simulator"
    assert record["message_samples"][0]["stages"][-1]["clock_source"] == "application"


def test_checkpoint_collection_writes_once_and_rejects_duplicate_stage(
    tmp_path: Path,
) -> None:
    template, plan, checkpoints = _collection_inputs()
    template_path = tmp_path / "template.json"
    plan_path = tmp_path / "sample-plan.json"
    log_path = tmp_path / "checkpoints.jsonl"
    output_path = tmp_path / "evaluation-metrics.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    log_path.write_text(
        "\n".join(
            metrics.CHECKPOINT_PREFIX + json.dumps(checkpoint)
            for values in checkpoints.values()
            for checkpoint in values
        )
        + "\n",
        encoding="utf-8",
    )

    metrics.collect_metrics(template_path, plan_path, [log_path], output_path)
    assert metrics.load_metrics(output_path)["run_id"] == template["run_id"]
    with pytest.raises(metrics.LiveMetricsError, match="already exists"):
        metrics.collect_metrics(template_path, plan_path, [log_path], output_path)

    trace_id = next(iter(checkpoints))
    checkpoints[trace_id].append(dict(checkpoints[trace_id][0]))
    with pytest.raises(metrics.LiveMetricsError, match="Duplicate stage"):
        metrics.assemble_metrics(template, plan, checkpoints)


def test_checkpoint_parser_accepts_structured_provider_log_envelope() -> None:
    _template, _plan, checkpoints = _collection_inputs()
    checkpoint = next(iter(checkpoints.values()))[0]
    line = json.dumps(
        {"severity": "INFO", "message": metrics.CHECKPOINT_PREFIX + json.dumps(checkpoint)}
    )

    assert metrics._checkpoint_payload(line) == checkpoint


def test_command_receipt_is_a_distinct_valid_measurement_direction() -> None:
    record = _record()
    record["protocol"]["directions"] = ["command_receipt"]
    expected_path = [
        "command_issued",
        "event_layer_command_durable",
        "l1_command_published",
        "simulator_command_received",
    ]
    record["protocol"]["expected_paths"] = [
        {"direction": "command_receipt", "stage_ids": expected_path}
    ]
    for sample in record["message_samples"]:
        sample["direction"] = "command_receipt"
        sample["stages"] = [
            {
                "stage_id": stage_id,
                "provider": "aws",
                "layer": metrics.STAGE_LAYERS[stage_id],
                "observed_at": _at(1000 + index * 10 + sample["sequence"]),
                "clock_source": metrics.STAGE_CLOCK_SOURCES[stage_id],
                "event_id": f"command-{sample['sample_set']}-{sample['sequence']}",
            }
            for index, stage_id in enumerate(expected_path)
        ]
        sample["auxiliary_stages"] = [
            {
                "stage_id": "outcome_persisted",
                "provider": "aws",
                "layer": "L3-hot",
                "observed_at": _at(1050 + sample["sequence"]),
                "clock_source": "provider",
                "event_id": f"outcome-{sample['sample_set']}-{sample['sequence']}",
            }
        ]

    assert metrics.validate_metrics(record)["measured_sample_count"] == 2
