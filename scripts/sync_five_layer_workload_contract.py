#!/usr/bin/env python3
"""Generate, validate, synchronize, and drift-check Five-layer Workload v2."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "contracts" / "five-layer-workload"
SOURCE_V2 = SOURCE_ROOT / "v2"
EVENTING_SOURCE = (
    ROOT / "docs" / "research" / "evidence" / "phase_08_eventing" / "scenario-inputs.json"
)
EVENTING_DECISION = EVENTING_SOURCE.with_name("decision.json")
CORE_SOURCE = (
    ROOT
    / "docs"
    / "research"
    / "evidence"
    / "phase_08_service_bundles"
    / "workload-scenarios.json"
)
TARGETS = (
    ROOT / "2-twin2clouds" / "backend" / "contracts" / "generated" / "five-layer-workload",
    ROOT / "twin2multicloud_backend" / "src" / "contracts" / "generated" / "five-layer-workload",
    ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated" / "five-layer-workload",
    ROOT / "twin2multicloud_flutter" / "assets" / "contracts" / "five-layer-workload",
)
SCENARIO_IDS = (
    "eventing-small-v1",
    "eventing-medium-v1",
    "eventing-large-v1",
)
WORKLOAD_FIELDS = (
    "schemaVersion",
    "numberOfDevices",
    "deviceSendingIntervalInMinutes",
    "averageSizeOfMessageInKb",
    "numberOfDeviceTypes",
    "hotStorageDurationInMonths",
    "coolStorageDurationInMonths",
    "archiveStorageDurationInMonths",
    "twinEntityCount",
    "aggregateDashboardRefreshesPerHour",
    "apiCallsPerAggregateDashboardRefresh",
    "dashboardActiveHoursPerDay",
    "monthlyEditorSeats",
    "monthlyViewerSeats",
    "twinStateMaterializationsPerSecond",
    "twinGraphUpdatesPerSecond",
    "eventingScenarioId",
    "currency",
)
RETIRED_FIELDS = (
    "useEventChecking",
    "triggerNotificationWorkflow",
    "returnFeedbackToDevice",
    "allowGcpSelfHostedL4",
    "allowGcpSelfHostedL5",
    "entityCount",
    "needs3DModel",
    "average3DModelSizeInMB",
    "amountOfActiveEditors",
    "amountOfActiveViewers",
    "dashboardRefreshesPerHour",
    "apiCallsPerDashboardRefresh",
    "integrateErrorHandling",
    "orchestrationActionsPerMessage",
    "eventsPerMessage",
    "numberOfEventActions",
    "eventTriggerRate",
)
EXPECTED_FILES = frozenset(
    {
        "README.md",
        "v2/workload.schema.json",
        "v2/eventing-scenario-catalog.schema.json",
        "v2/eventing-scenario-catalog.json",
        "v2/fixtures/valid/core-small.json",
        "v2/fixtures/valid/core-medium.json",
        "v2/fixtures/valid/core-large.json",
        "v2/fixtures/invalid/retired-event-flag.json",
        "v2/fixtures/invalid/inline-eventing-scenario.json",
        "v2/fixtures/invalid/missing-event-scenario.json",
        "v2/fixtures/invalid/non-increasing-retention.json",
    }
)


class WorkloadContractError(ValueError):
    """Stable offline contract error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode()).hexdigest()}"


def file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def eventing_content_digest(document: dict[str, Any]) -> str:
    """Use the Eventing package's own normalization algorithm."""
    calculator_path = ROOT / "scripts" / "phase_08_eventing" / "calculate_scenarios.py"
    spec = importlib.util.spec_from_file_location(
        "phase_08_eventing_calculator_for_workload_v2",
        calculator_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Eventing calculator {calculator_path}")
    calculator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calculator)
    return calculator.normalized_digest(calculator.normalize_for_digest(document))


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read JSON contract source {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain an object")
    return value


def workload_schema() -> dict[str, Any]:
    positive_number = {"type": "number", "exclusiveMinimum": 0}
    non_negative_number = {"type": "number", "minimum": 0}
    positive_integer = {"type": "integer", "minimum": 1}
    non_negative_integer = {"type": "integer", "minimum": 0}
    properties: dict[str, Any] = {
        "schemaVersion": {"const": "five-layer-workload.v2"},
        "numberOfDevices": positive_integer,
        "deviceSendingIntervalInMinutes": positive_number,
        "averageSizeOfMessageInKb": {
            "type": "number",
            "exclusiveMinimum": 0,
            "maximum": 64,
        },
        "numberOfDeviceTypes": positive_integer,
        "hotStorageDurationInMonths": positive_integer,
        "coolStorageDurationInMonths": positive_integer,
        "archiveStorageDurationInMonths": {
            "type": "integer",
            "minimum": 6,
        },
        "twinEntityCount": positive_integer,
        "aggregateDashboardRefreshesPerHour": non_negative_integer,
        "apiCallsPerAggregateDashboardRefresh": positive_integer,
        "dashboardActiveHoursPerDay": {
            "type": "integer",
            "minimum": 0,
            "maximum": 24,
        },
        "monthlyEditorSeats": non_negative_integer,
        "monthlyViewerSeats": non_negative_integer,
        "twinStateMaterializationsPerSecond": non_negative_number,
        "twinGraphUpdatesPerSecond": non_negative_number,
        "eventingScenarioId": {"enum": list(SCENARIO_IDS)},
        "currency": {"enum": ["USD", "EUR"]},
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://twin2multicloud.local/contracts/five-layer-workload/v2/workload.schema.json",
        "title": "Five-layer Workload v2",
        "description": (
            "Editable core workload plus one immutable mandatory Eventing scenario reference. "
            "Retired feature flags and provider implementation switches are forbidden."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }
    if tuple(properties) != WORKLOAD_FIELDS:
        raise RuntimeError("Five-layer Workload v2 field set drifted")
    return schema


def scenario_catalog_schema() -> dict[str, Any]:
    scenario_fields = {
        "scenario_id": {"enum": list(SCENARIO_IDS)},
        "events_per_month": {"type": "integer", "minimum": 1},
        "publish_requests_per_month": {"type": "integer", "minimum": 1},
        "average_event_payload_bytes": {"type": "integer", "minimum": 1},
        "mandatory_processed_consumers": {
            "type": "array",
            "minItems": 3,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "extra_processed_consumers": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "retry_share": {"type": "number", "minimum": 0, "maximum": 1},
        "dead_letter_share": {"type": "number", "minimum": 0, "maximum": 1},
        "replay_share": {"type": "number", "minimum": 0, "maximum": 1},
        "retention_hours": {"type": "integer", "minimum": 1},
        "ordering_scope": {"const": "per_device"},
        "required_delivery_semantics": {"const": "at_least_once"},
        "max_delivery_latency_seconds": {"type": "number", "exclusiveMinimum": 0},
        "peak_events_per_second": {"type": "number", "exclusiveMinimum": 0},
        "active_partition_keys": {"type": "integer", "minimum": 1},
        "concurrent_device_connections": {"type": "integer", "minimum": 1},
        "rule_match_share": {"type": "number", "minimum": 0, "maximum": 1},
        "workflow_start_share_of_matches": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "device_command_share_of_matches": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "bounded_synthetic_scenario": {"const": True},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://twin2multicloud.local/contracts/five-layer-workload/v2/eventing-scenario-catalog.schema.json",
        "title": "Eventing Scenario Catalog v1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "package_id",
            "decision_ref",
            "decision_byte_digest",
            "scenario_source_ref",
            "scenario_source_byte_digest",
            "scenario_source_content_digest",
            "scenarios",
            "scenario_digests",
            "content_digest",
        ],
        "properties": {
            "schema_version": {"const": "eventing-scenario-catalog.v1"},
            "package_id": {"const": "phase-08-eventing-implementation@1"},
            "decision_ref": {
                "const": "docs/research/evidence/phase_08_eventing/decision.json"
            },
            "decision_byte_digest": {"$ref": "#/$defs/digest"},
            "scenario_source_ref": {
                "const": "docs/research/evidence/phase_08_eventing/scenario-inputs.json"
            },
            "scenario_source_byte_digest": {"$ref": "#/$defs/digest"},
            "scenario_source_content_digest": {"$ref": "#/$defs/digest"},
            "scenarios": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(scenario_fields),
                    "properties": scenario_fields,
                },
            },
            "scenario_digests": {
                "type": "object",
                "additionalProperties": False,
                "required": list(SCENARIO_IDS),
                "properties": {
                    scenario_id: {"$ref": "#/$defs/digest"}
                    for scenario_id in SCENARIO_IDS
                },
            },
            "content_digest": {"$ref": "#/$defs/digest"},
        },
        "$defs": {
            "digest": {
                "type": "string",
                "pattern": "^sha256:[0-9a-f]{64}$",
            }
        },
    }


def scenario_catalog() -> dict[str, Any]:
    source = read_json(EVENTING_SOURCE)
    decision = read_json(EVENTING_DECISION)
    core_source = read_json(CORE_SOURCE)
    dependency = core_source.get("eventing_dependency")
    if not isinstance(dependency, dict):
        raise RuntimeError("Core workload source has no Eventing dependency")
    decision_byte_digest = file_digest(EVENTING_DECISION)
    if dependency.get("package_id") != "phase-08-eventing-implementation@1":
        raise RuntimeError("Core workload Eventing package ID drifted")
    if dependency.get("decision_byte_digest") != decision_byte_digest:
        raise RuntimeError("Core workload Eventing decision digest drifted")
    if dependency.get("scenario_ids") != list(SCENARIO_IDS):
        raise RuntimeError("Core workload Eventing scenario IDs drifted")
    input_digests = decision.get("input_digests")
    if not isinstance(input_digests, dict):
        raise RuntimeError("Eventing decision has no input digest map")
    scenario_source_content_digest = eventing_content_digest(source)
    if input_digests.get("scenario_inputs") != scenario_source_content_digest:
        raise RuntimeError("Eventing decision scenario source digest drifted")
    scenarios = source.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(SCENARIO_IDS):
        raise RuntimeError("Eventing source must contain exactly three scenarios")
    if not all(isinstance(item, dict) for item in scenarios):
        raise RuntimeError("Eventing scenarios must be objects")
    by_id = {
        str(item.get("scenario_id")): copy.deepcopy(item)
        for item in scenarios
    }
    if tuple(by_id) != SCENARIO_IDS:
        raise RuntimeError("Eventing scenarios must use the canonical order")
    catalog: dict[str, Any] = {
        "schema_version": "eventing-scenario-catalog.v1",
        "package_id": "phase-08-eventing-implementation@1",
        "decision_ref": "docs/research/evidence/phase_08_eventing/decision.json",
        "decision_byte_digest": decision_byte_digest,
        "scenario_source_ref": "docs/research/evidence/phase_08_eventing/scenario-inputs.json",
        "scenario_source_byte_digest": file_digest(EVENTING_SOURCE),
        "scenario_source_content_digest": scenario_source_content_digest,
        "scenarios": [by_id[scenario_id] for scenario_id in SCENARIO_IDS],
        "scenario_digests": {
            scenario_id: digest(by_id[scenario_id]) for scenario_id in SCENARIO_IDS
        },
        "content_digest": "",
    }
    catalog["content_digest"] = digest(
        {key: value for key, value in catalog.items() if key != "content_digest"}
    )
    return catalog


def valid_workloads() -> dict[str, dict[str, Any]]:
    source = read_json(CORE_SOURCE)
    scenarios = source.get("core_scenarios")
    pairing = source.get("scenario_pairing")
    if not isinstance(scenarios, list) or not isinstance(pairing, list):
        raise RuntimeError("Core workload source is incomplete")
    event_by_core = {
        str(item["core_scenario_id"]): str(item["eventing_scenario_id"])
        for item in pairing
        if isinstance(item, dict)
    }
    expected_pairing = {
        "core-small-v2": "eventing-small-v1",
        "core-medium-v2": "eventing-medium-v1",
        "core-large-v2": "eventing-large-v1",
    }
    if len(pairing) != len(expected_pairing) or event_by_core != expected_pairing:
        raise RuntimeError("Core-to-Eventing scenario pairing drifted")
    workloads: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise RuntimeError("Core workload scenario must be an object")
        size = str(scenario["size"])
        workloads[size] = {
            "schemaVersion": "five-layer-workload.v2",
            "numberOfDevices": scenario["device_count"],
            "deviceSendingIntervalInMinutes": scenario["telemetry_interval_seconds"] / 60,
            "averageSizeOfMessageInKb": scenario["average_payload_kib"],
            "numberOfDeviceTypes": 1,
            "hotStorageDurationInMonths": scenario["hot_boundary_months"],
            "coolStorageDurationInMonths": scenario["cool_boundary_months"],
            "archiveStorageDurationInMonths": scenario["archive_boundary_months"],
            "twinEntityCount": scenario["twin_entity_count"],
            "aggregateDashboardRefreshesPerHour": scenario[
                "aggregate_dashboard_refreshes_per_hour"
            ],
            "apiCallsPerAggregateDashboardRefresh": scenario[
                "api_calls_per_aggregate_dashboard_refresh"
            ],
            "dashboardActiveHoursPerDay": scenario["dashboard_active_hours_per_day"],
            "monthlyEditorSeats": scenario["monthly_editor_seats"],
            "monthlyViewerSeats": scenario["monthly_viewer_seats"],
            "twinStateMaterializationsPerSecond": scenario[
                "twin_state_materializations_per_second"
            ],
            "twinGraphUpdatesPerSecond": scenario["twin_graph_updates_per_second"],
            "eventingScenarioId": event_by_core[str(scenario["scenario_id"])],
            "currency": "USD",
        }
    if tuple(workloads) != ("small", "medium", "large"):
        raise RuntimeError("Core workloads must use Small, Medium, Large order")
    return workloads


def validate_workload(
    workload: dict[str, Any],
    *,
    schema: dict[str, Any],
    catalog: dict[str, Any],
) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(workload),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path) or "$"
        raise WorkloadContractError(
            "WORKLOAD_V2_SCHEMA_INVALID",
            f"Workload schema failed at {location}: {errors[0].message}",
        )
    hot = workload["hotStorageDurationInMonths"]
    cool = workload["coolStorageDurationInMonths"]
    archive = workload["archiveStorageDurationInMonths"]
    if not 1 <= hot < cool < archive:
        raise WorkloadContractError(
            "WORKLOAD_V2_RETENTION_INVALID",
            "Retention must satisfy 1 <= hot < cool < archive",
        )
    known_scenarios = {
        item["scenario_id"] for item in catalog["scenarios"]
    }
    if workload["eventingScenarioId"] not in known_scenarios:
        raise WorkloadContractError(
            "WORKLOAD_V2_EVENTING_SCENARIO_UNKNOWN",
            "Eventing scenario is not present in the immutable catalog",
        )


def expected_documents() -> dict[str, bytes]:
    schema = workload_schema()
    catalog_schema = scenario_catalog_schema()
    catalog = scenario_catalog()
    workloads = valid_workloads()
    invalid_retired = copy.deepcopy(workloads["small"])
    invalid_retired["useEventChecking"] = True
    invalid_inline = copy.deepcopy(workloads["small"])
    invalid_inline["eventingScenario"] = {"scenario_id": "eventing-small-v1"}
    invalid_missing = copy.deepcopy(workloads["small"])
    invalid_missing.pop("eventingScenarioId")
    invalid_retention = copy.deepcopy(workloads["small"])
    invalid_retention["coolStorageDurationInMonths"] = 1
    documents: dict[str, object] = {
        "v2/workload.schema.json": schema,
        "v2/eventing-scenario-catalog.schema.json": catalog_schema,
        "v2/eventing-scenario-catalog.json": catalog,
        **{
            f"v2/fixtures/valid/core-{size}.json": workload
            for size, workload in workloads.items()
        },
        "v2/fixtures/invalid/retired-event-flag.json": invalid_retired,
        "v2/fixtures/invalid/inline-eventing-scenario.json": invalid_inline,
        "v2/fixtures/invalid/missing-event-scenario.json": invalid_missing,
        "v2/fixtures/invalid/non-increasing-retention.json": invalid_retention,
    }
    rendered = {
        path: (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode()
        for path, value in documents.items()
    }
    rendered["README.md"] = (
        "# Five-layer Workload v2\n\n"
        "Strict editable core workload plus one immutable Eventing scenario reference. "
        "Generated by `scripts/sync_five_layer_workload_contract.py`; do not edit generated copies.\n"
    ).encode()
    return rendered


def contract_digest(documents: dict[str, bytes]) -> str:
    entries = [
        {"path": path, "sha256": hashlib.sha256(value).hexdigest()}
        for path, value in sorted(documents.items())
    ]
    return digest(entries)


def validate_expected(documents: dict[str, bytes]) -> None:
    if set(documents) != EXPECTED_FILES:
        raise RuntimeError("Five-layer workload generated file set drifted")
    schema = json.loads(documents["v2/workload.schema.json"])
    catalog_schema = json.loads(
        documents["v2/eventing-scenario-catalog.schema.json"]
    )
    catalog = json.loads(documents["v2/eventing-scenario-catalog.json"])
    Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(catalog_schema)
    catalog_errors = list(
        Draft202012Validator(
            catalog_schema,
            format_checker=FormatChecker(),
        ).iter_errors(catalog)
    )
    if catalog_errors:
        raise RuntimeError(f"Eventing scenario catalog is invalid: {catalog_errors[0].message}")
    expected_catalog_digest = digest(
        {key: value for key, value in catalog.items() if key != "content_digest"}
    )
    if catalog["content_digest"] != expected_catalog_digest:
        raise RuntimeError("Eventing scenario catalog digest drifted")
    for scenario in catalog["scenarios"]:
        if catalog["scenario_digests"][scenario["scenario_id"]] != digest(scenario):
            raise RuntimeError("Eventing scenario digest drifted")
    for path in sorted(path for path in documents if "/valid/" in path):
        validate_workload(json.loads(documents[path]), schema=schema, catalog=catalog)
    for path in sorted(path for path in documents if "/invalid/" in path):
        try:
            validate_workload(json.loads(documents[path]), schema=schema, catalog=catalog)
        except WorkloadContractError:
            continue
        raise RuntimeError(f"Invalid workload fixture was accepted: {path}")


def _write_tree(root: Path, documents: dict[str, bytes], marker: str | None) -> None:
    if root.exists():
        shutil.rmtree(root)
    for relative, value in documents.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    if marker is not None:
        (root / ".contract-sha256").write_text(f"{marker}\n", encoding="utf-8")


def synchronize() -> str:
    documents = expected_documents()
    validate_expected(documents)
    marker = contract_digest(documents)
    _write_tree(SOURCE_ROOT, documents, None)
    for target in TARGETS:
        _write_tree(target, documents, marker)
    return marker


def _check_tree(root: Path, documents: dict[str, bytes], marker: str | None) -> None:
    actual = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != ".contract-sha256"
    }
    if actual != documents:
        raise RuntimeError(f"Five-layer workload contract drift: {root}")
    if marker is not None:
        marker_path = root / ".contract-sha256"
        if not marker_path.exists() or marker_path.read_text().strip() != marker:
            raise RuntimeError(f"Five-layer workload marker drift: {root}")


def check() -> str:
    documents = expected_documents()
    validate_expected(documents)
    marker = contract_digest(documents)
    _check_tree(SOURCE_ROOT, documents, None)
    for target in TARGETS:
        _check_tree(target, documents, marker)
    return marker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    marker = check() if args.check else synchronize()
    print(f"five-layer-workload: OK (source_digest={marker}, generated_copies={len(TARGETS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
