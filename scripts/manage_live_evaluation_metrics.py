#!/usr/bin/env python3
"""Validate and summarize secret-free supervised evaluation measurements.

The utility is deliberately offline. It imports no cloud SDK, starts no
simulator, and invokes neither Terraform nor the Deployer. It validates
operator-recorded metrics and derives deterministic CSV/SVG artifacts for the
thesis evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from itertools import pairwise
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT / "docs/research/evaluation/schemas" / "live-evaluation-metrics.schema.json"
)


class LiveMetricsError(RuntimeError):
    """Raised when live-evaluation measurements are invalid or inconsistent."""


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveMetricsError(f"Cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise LiveMetricsError(f"Expected JSON object: {path}")
    return value


def _timestamp(value: str) -> datetime:
    rendered = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        result = datetime.fromisoformat(rendered)
    except ValueError as exc:
        raise LiveMetricsError(f"Invalid timestamp: {value}") from exc
    if result.tzinfo is None:
        raise LiveMetricsError(f"Timestamp has no timezone: {value}")
    return result


def _duration_ms(started_at: str, completed_at: str) -> float:
    return (_timestamp(completed_at) - _timestamp(started_at)).total_seconds() * 1000


def _validate_schema(record: Mapping[str, Any]) -> None:
    schema = _read(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(record),
        key=lambda error: tuple(str(value) for value in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(value) for value in error.absolute_path) or "$"
        raise LiveMetricsError(
            f"Metrics schema violation at {location}: {error.message}"
        )


def _validate_run_binding(record: Mapping[str, Any]) -> None:
    run_kind = record["run_kind"]
    scenario_id = record["scenario_id"]
    candidate_digest = record["candidate_evidence_digest"]
    provider_count = len(record["provider_scope"])
    if run_kind == "component_probe":
        if scenario_id is not None:
            raise LiveMetricsError("Component probes must not claim a final scenario")
    else:
        if scenario_id is None or candidate_digest is None:
            raise LiveMetricsError(
                "Final scenario metrics require scenario and candidate bindings"
            )
        if record["subject_id"] != scenario_id:
            raise LiveMetricsError("Final scenario subject must equal scenario_id")
    if run_kind == "provider_local" and provider_count != 1:
        raise LiveMetricsError("Provider-local metrics require exactly one provider")
    if run_kind == "directed_multicloud" and provider_count < 2:
        raise LiveMetricsError(
            "Directed multi-cloud metrics require multiple providers"
        )


def _validate_time_bounds(record: Mapping[str, Any]) -> None:
    if _timestamp(record["completed_at"]) < _timestamp(record["started_at"]):
        raise LiveMetricsError("Run completion precedes its start")
    observed_phases: set[tuple[str, str | None]] = set()
    tolerance_ms = max(5.0, float(record["clock"]["max_observed_skew_ms"]))
    for measurement in record["lifecycle"]:
        identity = (measurement["phase"], measurement["provider"])
        if identity in observed_phases:
            raise LiveMetricsError(f"Duplicate lifecycle measurement: {identity}")
        observed_phases.add(identity)
        if measurement["status"] != "completed":
            continue
        calculated = _duration_ms(
            measurement["started_at"], measurement["completed_at"]
        )
        if calculated < -tolerance_ms:
            raise LiveMetricsError(
                f"Lifecycle phase {measurement['phase']} completes before it starts"
            )
        if abs(max(0.0, calculated) - measurement["duration_ms"]) > tolerance_ms:
            raise LiveMetricsError(
                f"Lifecycle duration drifted for {measurement['phase']}"
            )


def _expected_paths(record: Mapping[str, Any]) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}
    for path in record["protocol"]["expected_paths"]:
        direction = path["direction"]
        if direction in paths:
            raise LiveMetricsError(f"Duplicate expected path: {direction}")
        paths[direction] = path["stage_ids"]
    directions = record["protocol"]["directions"]
    if set(paths) != set(directions):
        raise LiveMetricsError("Expected paths do not match protocol directions")
    return paths


def _validate_samples(record: Mapping[str, Any]) -> None:
    protocol = record["protocol"]
    expected_paths = _expected_paths(record)
    expected_counts = {
        "warmup": protocol["warmup_messages_per_direction"],
        "measured": protocol["measured_messages_per_direction"],
    }
    counts: dict[tuple[str, str], int] = defaultdict(int)
    trace_ids: set[str] = set()
    sequence_ids: set[tuple[str, str, int]] = set()
    skew_ms = float(record["clock"]["max_observed_skew_ms"])

    for sample in record["message_samples"]:
        trace_id = sample["trace_id"]
        if trace_id in trace_ids:
            raise LiveMetricsError(f"Duplicate trace_id: {trace_id}")
        trace_ids.add(trace_id)
        sequence_id = (
            sample["direction"],
            sample["sample_set"],
            sample["sequence"],
        )
        if sequence_id in sequence_ids:
            raise LiveMetricsError(f"Duplicate sample sequence: {sequence_id}")
        sequence_ids.add(sequence_id)
        counts[(sample["direction"], sample["sample_set"])] += 1

        if sample["payload_bytes"] != protocol["payload_bytes"]:
            raise LiveMetricsError(f"Payload size drifted for trace {trace_id}")
        stages = sample["stages"]
        stage_ids = [stage["stage_id"] for stage in stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise LiveMetricsError(f"Duplicate stage in trace {trace_id}")
        for previous, current in pairwise(stages):
            delta_ms = _duration_ms(previous["observed_at"], current["observed_at"])
            if delta_ms < -skew_ms:
                raise LiveMetricsError(
                    f"Trace {trace_id} exceeds recorded clock-skew tolerance"
                )
        if sample["status"] == "succeeded":
            if sample["failure_code"] is not None:
                raise LiveMetricsError(
                    f"Successful trace {trace_id} cannot contain a failure code"
                )
            if stage_ids != expected_paths[sample["direction"]]:
                raise LiveMetricsError(
                    f"Successful trace {trace_id} does not match its expected path"
                )
        elif sample["failure_code"] is None:
            raise LiveMetricsError(
                f"Failed or timed-out trace {trace_id} requires a failure code"
            )

    for direction in protocol["directions"]:
        for sample_set, expected in expected_counts.items():
            actual = counts[(direction, sample_set)]
            if actual != expected:
                raise LiveMetricsError(
                    f"{direction} {sample_set} count is {actual}; expected {expected}"
                )


def _validate_cleanup(record: Mapping[str, Any]) -> None:
    cleanup = record["cleanup"]
    if cleanup["inventory_clean"] is True and (
        cleanup["residual_count"] != 0 or cleanup["residual_types"]
    ):
        raise LiveMetricsError("Clean inventory cannot contain residual resources")
    if cleanup["residual_count"] != len(cleanup["residual_types"]):
        raise LiveMetricsError("Residual count and residual type list disagree")


def validate_metrics(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one metrics document and return a compact description."""

    _validate_schema(record)
    _validate_run_binding(record)
    _validate_time_bounds(record)
    _validate_samples(record)
    _validate_cleanup(record)
    measured = [
        sample
        for sample in record["message_samples"]
        if sample["sample_set"] == "measured"
    ]
    return {
        "run_id": record["run_id"],
        "run_kind": record["run_kind"],
        "subject_id": record["subject_id"],
        "measured_sample_count": len(measured),
    }


def load_metrics(path: Path) -> dict[str, Any]:
    record = _read(path)
    validate_metrics(record)
    return record


def _sample_duration(sample: Mapping[str, Any]) -> float:
    stages = sample["stages"]
    return max(0.0, _duration_ms(stages[0]["observed_at"], stages[-1]["observed_at"]))


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise LiveMetricsError("Cannot calculate a percentile without values")
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _rounded(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def _summary_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        for direction in record["protocol"]["directions"]:
            measured = [
                sample
                for sample in record["message_samples"]
                if sample["sample_set"] == "measured"
                and sample["direction"] == direction
            ]
            successful = [
                _sample_duration(sample)
                for sample in measured
                if sample["status"] == "succeeded"
            ]
            successes = len(successful)
            total = len(measured)
            rows.append(
                {
                    "run_id": record["run_id"],
                    "run_kind": record["run_kind"],
                    "subject_id": record["subject_id"],
                    "scenario_id": record["scenario_id"] or "",
                    "providers": "+".join(record["provider_scope"]),
                    "direction": direction,
                    "measured_messages": total,
                    "successes": successes,
                    "failures": sum(
                        sample["status"] == "failed" for sample in measured
                    ),
                    "timeouts": sum(
                        sample["status"] == "timeout" for sample in measured
                    ),
                    "success_rate": _rounded(successes / total if total else None),
                    "mean_ms": _rounded(
                        statistics.fmean(successful) if successful else None
                    ),
                    "p50_ms": _rounded(
                        _percentile(successful, 0.50) if successful else None
                    ),
                    "p95_ms": _rounded(
                        _percentile(successful, 0.95) if successful else None
                    ),
                    "max_ms": _rounded(max(successful) if successful else None),
                }
            )
    return rows


def _stage_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    subjects: dict[str, str] = {}
    for record in records:
        subjects[record["run_id"]] = record["subject_id"]
        for sample in record["message_samples"]:
            if sample["sample_set"] != "measured" or sample["status"] != "succeeded":
                continue
            for previous, current in pairwise(sample["stages"]):
                key = (
                    record["run_id"],
                    sample["direction"],
                    previous["stage_id"],
                    current["stage_id"],
                )
                grouped[key].append(
                    max(
                        0.0,
                        _duration_ms(previous["observed_at"], current["observed_at"]),
                    )
                )
    rows = []
    for key in sorted(grouped):
        run_id, direction, source_stage, destination_stage = key
        values = grouped[key]
        rows.append(
            {
                "run_id": run_id,
                "subject_id": subjects[run_id],
                "direction": direction,
                "source_stage": source_stage,
                "destination_stage": destination_stage,
                "sample_count": len(values),
                "mean_ms": _rounded(statistics.fmean(values)),
                "p50_ms": _rounded(_percentile(values, 0.50)),
                "p95_ms": _rounded(_percentile(values, 0.95)),
                "max_ms": _rounded(max(values)),
            }
        )
    return rows


def _lifecycle_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": record["run_id"],
            "subject_id": record["subject_id"],
            "phase": measurement["phase"],
            "provider": measurement["provider"] or "",
            "status": measurement["status"],
            "duration_ms": _rounded(measurement["duration_ms"]),
        }
        for record in records
        for measurement in record["lifecycle"]
    ]


def _resource_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": record["run_id"],
            "subject_id": record["subject_id"],
            **resource,
            "sku": resource["sku"] or "",
        }
        for record in records
        for resource in record["resources"]
    ]


def _write_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_bar_chart(
    path: Path,
    rows: Sequence[tuple[str, float]],
    *,
    title: str,
    unit: str,
) -> None:
    width = 1200
    margin_left = 320
    row_height = 34
    height = max(150, 90 + row_height * len(rows))
    chart_width = width - margin_left - 80
    maximum = max((value for _, value in rows), default=1.0) or 1.0
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="24" y="34" font-family="sans-serif" font-size="22" font-weight="bold">{escape(title)}</text>',
    ]
    if not rows:
        lines.append(
            '<text x="24" y="80" font-family="sans-serif" font-size="16">No completed measurements</text>'
        )
    for index, (label, value) in enumerate(rows):
        y = 62 + index * row_height
        bar_width = chart_width * value / maximum
        lines.extend(
            [
                f'<text x="24" y="{y + 18}" font-family="sans-serif" font-size="13">{escape(label)}</text>',
                f'<rect x="{margin_left}" y="{y}" width="{bar_width:.2f}" height="22" fill="#2563eb"/>',
                f'<text x="{margin_left + bar_width + 8:.2f}" y="{y + 17}" font-family="sans-serif" font-size="13">{value:.3f} {escape(unit)}</text>',
            ]
        )
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_metrics(records: Sequence[Mapping[str, Any]], output_dir: Path) -> None:
    if output_dir.exists():
        raise LiveMetricsError(f"Summary output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    summary_rows = _summary_rows(records)
    stage_rows = _stage_rows(records)
    lifecycle_rows = _lifecycle_rows(records)
    resource_rows = _resource_rows(records)
    _write_csv(
        output_dir / "run-summary.csv",
        summary_rows,
        (
            "run_id",
            "run_kind",
            "subject_id",
            "scenario_id",
            "providers",
            "direction",
            "measured_messages",
            "successes",
            "failures",
            "timeouts",
            "success_rate",
            "mean_ms",
            "p50_ms",
            "p95_ms",
            "max_ms",
        ),
    )
    _write_csv(
        output_dir / "stage-latency.csv",
        stage_rows,
        (
            "run_id",
            "subject_id",
            "direction",
            "source_stage",
            "destination_stage",
            "sample_count",
            "mean_ms",
            "p50_ms",
            "p95_ms",
            "max_ms",
        ),
    )
    _write_csv(
        output_dir / "lifecycle.csv",
        lifecycle_rows,
        ("run_id", "subject_id", "phase", "provider", "status", "duration_ms"),
    )
    _write_csv(
        output_dir / "resources.csv",
        resource_rows,
        (
            "run_id",
            "subject_id",
            "provider",
            "region",
            "layer",
            "service",
            "sku",
            "count",
        ),
    )
    latency_bars = [
        (f"{row['subject_id']} / {row['direction']}", float(row["p95_ms"]))
        for row in summary_rows
        if row["p95_ms"]
    ]
    lifecycle_bars = [
        (f"{row['subject_id']} / {row['phase']}", float(row["duration_ms"]))
        for row in lifecycle_rows
        if row["status"] == "completed" and row["duration_ms"]
    ]
    _write_bar_chart(
        output_dir / "end-to-end-latency-p95.svg",
        latency_bars,
        title="Measured end-to-end latency (p95)",
        unit="ms",
    )
    _write_bar_chart(
        output_dir / "lifecycle-duration.svg",
        lifecycle_bars,
        title="Deployment lifecycle duration",
        unit="ms",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize live-evaluation metrics without cloud access."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate metrics JSON files.")
    validate.add_argument("--record", type=Path, action="append", required=True)
    summarize = subparsers.add_parser(
        "summarize", help="Create deterministic CSV tables and SVG charts."
    )
    summarize.add_argument("--record", type=Path, action="append", required=True)
    summarize.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    records = [load_metrics(path) for path in arguments.record]
    if arguments.command == "summarize":
        summarize_metrics(records, arguments.output_dir)
        print(
            "live-evaluation-metrics: summarized "
            f"{len(records)} run(s) into {arguments.output_dir}"
        )
        return 0
    for record in records:
        result = validate_metrics(record)
        print(
            "live-evaluation-metrics: OK "
            f"(run={result['run_id']}, kind={result['run_kind']}, "
            f"measured={result['measured_sample_count']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
