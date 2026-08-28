#!/usr/bin/env python3
"""Create and validate the secret-free supervised evaluation evidence index.

This utility never imports a cloud SDK and never invokes the Deployer. It binds
the operator-maintained evidence index to the checked plan, the offline
candidate pack, and digest-verified evidence files produced by the normal Twin
workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from itertools import permutations
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

try:
    from scripts.manage_live_evaluation_metrics import (
        LiveMetricsError,
        validate_metrics,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from manage_live_evaluation_metrics import LiveMetricsError, validate_metrics

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs/research/evaluation/small-scenario-matrix.json"
SCHEMA_PATH = (
    ROOT / "docs/research/evaluation/schemas" / "live-evaluation-evidence.schema.json"
)
PROVIDERS = ("aws", "azure", "gcp")
MAX_EVIDENCE_FILE_BYTES = 8 * 1024 * 1024
EVIDENCE_SUFFIXES = frozenset({".json", ".jsonl", ".csv", ".log", ".txt"})
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "clientsecret",
        "azureclientsecret",
        "secretaccesskey",
        "awssecretaccesskey",
        "accesskeyid",
        "awsaccesskeyid",
        "sessiontoken",
        "awssessiontoken",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "privatekey",
        "privatekeyid",
        "gcpcredentialsfile",
        "authorization",
        "cookie",
        "setcookie",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\bAccountKey\s*=\s*[^;\s]{8,}"),
)
SENSITIVE_TEXT_FIELD_PATTERN = re.compile(
    r"(?i)\b(?:client[_ -]?secret|secret[_ -]?access[_ -]?key|"
    r"access[_ -]?token|refresh[_ -]?token|session[_ -]?token|"
    r"private[_ -]?key|password|authorization|set-cookie)\b\s*[:=,]"
)
CANDIDATE_COMPONENT_ORDER = (
    "component.ingestion",
    "component.processing",
    "component.hot-storage",
    "component.cool-storage",
    "component.archive-storage",
    "component.twin-state",
    "component.visualization",
    "component.eventing",
)
REQUIRED_SCENARIO_ARTIFACTS = frozenset(
    {
        "readiness",
        "terraform_plan",
        "apply_operation",
        "replay",
        "access",
        "telemetry",
        "evaluation_metrics",
        "destroy_operation",
        "cleanup",
        "provider_cost",
    }
)
METRIC_STAGE_COMPONENT = {
    "l1_accepted": "component.ingestion",
    "event_layer_durable": "component.eventing",
    "l2_started": "component.processing",
    "l2_completed": "component.processing",
    "l3_hot_persisted": "component.hot-storage",
    "l3_cool_persisted": "component.cool-storage",
    "l3_archive_persisted": "component.archive-storage",
    "l4_queryable": "component.twin-state",
    "command_issued": "component.processing",
    "event_layer_command_durable": "component.eventing",
    "l1_command_published": "component.ingestion",
    "outcome_event_durable": "component.eventing",
    "outcome_persisted": "component.hot-storage",
    "outcome_queryable": "component.twin-state",
}


class LiveEvidenceError(RuntimeError):
    """Raised when live-evaluation evidence is incomplete or inconsistent."""


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveEvidenceError(f"Cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise LiveEvidenceError(f"Expected JSON object: {path}")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _document_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LiveEvidenceError(f"Cannot read evidence file: {path}") from exc
    return "sha256:" + digest.hexdigest()


def _without_digest(document: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in document.items() if name != key}


def _safe_relative_path(value: object, *, label: str) -> PurePosixPath:
    if not isinstance(value, str):
        raise LiveEvidenceError(f"{label} must be a relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise LiveEvidenceError(f"{label} must not escape its evidence directory")
    if len(path.parts) == 0:
        raise LiveEvidenceError(f"{label} must not be empty")
    return path


def _resolve_under(root: Path, relative: PurePosixPath, *, label: str) -> Path:
    root = root.resolve()
    path = root / Path(*relative.parts)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise LiveEvidenceError(f"{label} is missing: {relative.as_posix()}") from exc
    if not resolved.is_relative_to(root):
        raise LiveEvidenceError(f"{label} escapes its evidence directory")
    if not resolved.is_file():
        raise LiveEvidenceError(f"{label} is not a file: {relative.as_posix()}")
    return resolved


def _normalized_field(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _contains_sensitive_field(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _normalized_field(str(key))
            if (
                normalized in SENSITIVE_FIELD_NAMES
                or normalized.endswith(("password", "clientsecret", "privatekey"))
            ):
                return True
            if _contains_sensitive_field(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_field(item) for item in value)
    return False


def _validate_secret_free_evidence(path: Path, *, label: str) -> None:
    if path.suffix.lower() not in EVIDENCE_SUFFIXES:
        raise LiveEvidenceError(
            f"{label} uses an unsupported, non-inspectable evidence format"
        )
    try:
        size = path.stat().st_size
        if size > MAX_EVIDENCE_FILE_BYTES:
            raise LiveEvidenceError(
                f"{label} exceeds the bounded evidence-file size"
            )
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LiveEvidenceError(f"{label} must be UTF-8 text evidence") from exc
    except OSError as exc:
        raise LiveEvidenceError(f"Cannot inspect {label}") from exc

    if any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS) or (
        SENSITIVE_TEXT_FIELD_PATTERN.search(text)
    ):
        raise LiveEvidenceError(f"{label} contains credential-like material")

    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            parsed: object = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LiveEvidenceError(f"{label} is not valid JSON evidence") from exc
        if _contains_sensitive_field(parsed):
            raise LiveEvidenceError(f"{label} contains a sensitive field")
    elif suffix == ".jsonl":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LiveEvidenceError(
                    f"{label} contains invalid JSONL at line {line_number}"
                ) from exc
            if _contains_sensitive_field(parsed):
                raise LiveEvidenceError(f"{label} contains a sensitive field")
    elif suffix == ".csv":
        reader = csv.reader(text.splitlines())
        header = next(reader, [])
        if any(_normalized_field(field) in SENSITIVE_FIELD_NAMES for field in header):
            raise LiveEvidenceError(f"{label} contains a sensitive CSV field")


def _scenario_ids(plan: Mapping[str, Any]) -> list[str]:
    scenarios = plan.get("scenarios")
    if not isinstance(scenarios, list):
        raise LiveEvidenceError("Evaluation plan scenarios are unavailable")
    result = [item.get("scenario_id") for item in scenarios]
    if any(not isinstance(value, str) for value in result) or len(set(result)) != 9:
        raise LiveEvidenceError("Evaluation plan must contain nine unique scenarios")
    return result


def _candidate_regions(candidate: Mapping[str, Any]) -> dict[str, set[str]]:
    specification = candidate.get("resolved_deployment_specification")
    if not isinstance(specification, dict):
        raise LiveEvidenceError("Candidate has no resolved deployment specification")
    selections = specification.get("component_selections")
    if not isinstance(selections, list):
        raise LiveEvidenceError("Candidate has no component selections")
    regions: dict[str, set[str]] = {provider: set() for provider in PROVIDERS}
    for selection in selections:
        if not isinstance(selection, dict):
            raise LiveEvidenceError("Candidate component selection must be an object")
        provider = selection.get("provider")
        region = selection.get("region")
        if provider in regions and isinstance(region, str) and region:
            regions[provider].add(region)
    return regions


def load_candidate_pack(
    candidate_pack_dir: Path,
    *,
    plan_path: Path = PLAN_PATH,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], dict[str, str]]:
    """Validate a candidate pack and return all digest-bound source objects."""

    plan = _read(plan_path)
    manifest = _read(candidate_pack_dir / "candidate-pack-manifest.json")
    if manifest.get("schema_version") != "six-layer-evaluation-candidate-pack.v1":
        raise LiveEvidenceError("Unsupported candidate-pack manifest version")
    if manifest.get("evidence_status") != "offline_planned_candidates":
        raise LiveEvidenceError("Candidate pack must remain explicitly offline")
    if manifest.get("scenario_count") != 9:
        raise LiveEvidenceError("Candidate pack must contain exactly nine scenarios")
    if manifest.get("plan_digest") != _document_digest(plan):
        raise LiveEvidenceError("Candidate pack does not match the checked plan")
    if manifest.get("manifest_digest") != _document_digest(
        _without_digest(manifest, "manifest_digest")
    ):
        raise LiveEvidenceError("Candidate-pack manifest digest is invalid")

    entries = manifest.get("candidates")
    if not isinstance(entries, list) or len(entries) != 9:
        raise LiveEvidenceError("Candidate-pack manifest entries are incomplete")
    expected_ids = _scenario_ids(plan)
    plan_scenarios = {item["scenario_id"]: item for item in plan["scenarios"]}
    if [entry.get("scenario_id") for entry in entries] != expected_ids:
        raise LiveEvidenceError("Candidate-pack scenario order or coverage drifted")

    candidates: dict[str, dict[str, Any]] = {}
    observed_regions: dict[str, set[str]] = {provider: set() for provider in PROVIDERS}
    for entry in entries:
        scenario_id = str(entry["scenario_id"])
        relative = _safe_relative_path(
            entry.get("candidate_file"),
            label=f"{scenario_id} candidate_file",
        )
        if len(relative.parts) != 1:
            raise LiveEvidenceError("Candidate files must be pack-root files")
        candidate = _read(
            _resolve_under(
                candidate_pack_dir,
                relative,
                label=f"{scenario_id} candidate file",
            )
        )
        if candidate.get("scenario_id") != scenario_id:
            raise LiveEvidenceError(f"{scenario_id}: candidate identity drifted")
        if candidate.get("evidence_status") != "offline_planned_candidate":
            raise LiveEvidenceError(f"{scenario_id}: candidate is not offline evidence")
        if candidate.get("plan_digest") != manifest["plan_digest"]:
            raise LiveEvidenceError(f"{scenario_id}: candidate plan binding drifted")
        digest = candidate.get("evidence_digest")
        if digest != _document_digest(_without_digest(candidate, "evidence_digest")):
            raise LiveEvidenceError(f"{scenario_id}: candidate digest is invalid")
        if digest != entry.get("candidate_evidence_digest"):
            raise LiveEvidenceError(f"{scenario_id}: manifest digest binding drifted")
        if candidate.get("candidate_id") != entry.get("candidate_id"):
            raise LiveEvidenceError(f"{scenario_id}: candidate ID binding drifted")
        expected_assignments = plan_scenarios[scenario_id]["assignments"]
        if candidate.get("assignments") != expected_assignments:
            raise LiveEvidenceError(f"{scenario_id}: candidate assignments drifted")
        expected_candidate_id = "|".join(
            expected_assignments[component_id]
            for component_id in CANDIDATE_COMPONENT_ORDER
        )
        if candidate.get("candidate_id") != expected_candidate_id:
            raise LiveEvidenceError(f"{scenario_id}: candidate ID is not canonical")
        cost = candidate.get("cost_evaluation")
        if (
            not isinstance(cost, dict)
            or str(cost.get("monthly_total")) != entry.get("monthly_total")
            or cost.get("currency") != entry.get("currency")
            or entry.get("currency") != "USD"
        ):
            raise LiveEvidenceError(f"{scenario_id}: cost binding drifted")
        for provider, regions in _candidate_regions(candidate).items():
            observed_regions[provider].update(regions)
        candidates[scenario_id] = candidate

    regions: dict[str, str] = {}
    for provider, values in observed_regions.items():
        if len(values) != 1:
            raise LiveEvidenceError(
                f"Candidate pack must resolve one region for {provider}: {sorted(values)}"
            )
        regions[provider] = next(iter(values))
    return plan, manifest, candidates, regions


def create_template(
    candidate_pack_dir: Path,
    *,
    plan_path: Path = PLAN_PATH,
) -> dict[str, Any]:
    """Create the exact not-started evidence index for one candidate pack."""

    plan, manifest, candidates, regions = load_candidate_pack(
        candidate_pack_dir,
        plan_path=plan_path,
    )
    plan_scenarios = {item["scenario_id"]: item for item in plan["scenarios"]}
    manifest_entries = {item["scenario_id"]: item for item in manifest["candidates"]}
    return {
        "schema_version": "six-layer-live-evaluation-evidence.v1",
        "status": "planned_not_executed",
        "plan_digest": manifest["plan_digest"],
        "candidate_pack_manifest_digest": manifest["manifest_digest"],
        "operator_label": None,
        "cleanup_timer_owner_label": None,
        "started_at": None,
        "completed_at": None,
        "phase_8": {
            "provider_checks": [
                {
                    "provider": provider,
                    "region": regions[provider],
                    "account_scope_label": None,
                    "principal_label": None,
                    "status": "not_started",
                    "evidence_refs": [],
                    "blocker_code": None,
                }
                for provider in PROVIDERS
            ],
            "identity_exchanges": [
                {
                    "source_provider": source,
                    "destination_provider": destination,
                    "status": "not_started",
                    "cleanup_status": "not_started",
                    "evidence_refs": [],
                    "blocker_code": None,
                }
                for source, destination in permutations(PROVIDERS, 2)
            ],
        },
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "candidate_evidence_digest": candidates[scenario_id]["evidence_digest"],
                "estimated_monthly_total_usd": manifest_entries[scenario_id][
                    "monthly_total"
                ],
                "budget_cap_usd": plan_scenarios[scenario_id]["budget_cap_usd"],
                "budget_reviewed": False,
                "status": "not_started",
                "started_at": None,
                "completed_at": None,
                "artifacts": [],
                "blocker_code": None,
            }
            for scenario_id in _scenario_ids(plan)
        ],
    }


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
        raise LiveEvidenceError(
            f"Evidence schema violation at {location}: {error.message}"
        )


def _validate_evidence_refs(
    references: Sequence[Mapping[str, Any]],
    *,
    evidence_root: Path,
    label: str,
) -> None:
    seen: set[str] = set()
    for reference in references:
        relative = _safe_relative_path(reference.get("path"), label=f"{label} path")
        rendered = relative.as_posix()
        if rendered in seen:
            raise LiveEvidenceError(f"{label} contains a duplicate evidence path")
        seen.add(rendered)
        path = _resolve_under(evidence_root, relative, label=f"{label} evidence file")
        _validate_secret_free_evidence(path, label=f"{label} evidence file")
        if _file_digest(path) != reference.get("digest"):
            raise LiveEvidenceError(f"{label} evidence digest is invalid: {rendered}")


def _validate_pack_bindings(
    record: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    manifest: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    regions: Mapping[str, str],
) -> None:
    if record["plan_digest"] != manifest["plan_digest"]:
        raise LiveEvidenceError("Evidence index plan digest drifted")
    if record["candidate_pack_manifest_digest"] != manifest["manifest_digest"]:
        raise LiveEvidenceError("Evidence index candidate-pack digest drifted")

    checks = record["phase_8"]["provider_checks"]
    if [item["provider"] for item in checks] != list(PROVIDERS):
        raise LiveEvidenceError("Provider prerequisite coverage or order drifted")
    if any(item["region"] != regions[item["provider"]] for item in checks):
        raise LiveEvidenceError("Provider prerequisite region drifted")

    expected_pairs = list(permutations(PROVIDERS, 2))
    observed_pairs = [
        (item["source_provider"], item["destination_provider"])
        for item in record["phase_8"]["identity_exchanges"]
    ]
    if observed_pairs != expected_pairs:
        raise LiveEvidenceError("Directed identity-exchange coverage or order drifted")

    plan_scenarios = {item["scenario_id"]: item for item in plan["scenarios"]}
    manifest_entries = {item["scenario_id"]: item for item in manifest["candidates"]}
    scenarios = record["scenarios"]
    if [item["scenario_id"] for item in scenarios] != _scenario_ids(plan):
        raise LiveEvidenceError("Scenario evidence coverage or order drifted")
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        if (
            scenario["candidate_evidence_digest"]
            != candidates[scenario_id]["evidence_digest"]
        ):
            raise LiveEvidenceError(f"{scenario_id}: candidate evidence drifted")
        if (
            scenario["estimated_monthly_total_usd"]
            != manifest_entries[scenario_id]["monthly_total"]
        ):
            raise LiveEvidenceError(f"{scenario_id}: estimated cost drifted")
        if scenario["budget_cap_usd"] != plan_scenarios[scenario_id]["budget_cap_usd"]:
            raise LiveEvidenceError(f"{scenario_id}: approved budget drifted")


def _has_phase_8_blocker(record: Mapping[str, Any]) -> bool:
    checks = record["phase_8"]["provider_checks"]
    exchanges = record["phase_8"]["identity_exchanges"]
    return any(item["status"] == "blocked" for item in checks) or any(
        item["status"] == "blocked" or item["cleanup_status"] == "residual"
        for item in exchanges
    )


def _validate_planned(record: Mapping[str, Any]) -> None:
    if any(
        record[field] is not None
        for field in (
            "operator_label",
            "cleanup_timer_owner_label",
            "started_at",
            "completed_at",
        )
    ):
        raise LiveEvidenceError(
            "Planned evidence must not claim live ownership or time"
        )
    checks = record["phase_8"]["provider_checks"]
    exchanges = record["phase_8"]["identity_exchanges"]
    if any(
        item["status"] != "not_started"
        or item["evidence_refs"]
        or item["blocker_code"] is not None
        or item["account_scope_label"] is not None
        or item["principal_label"] is not None
        for item in checks
    ):
        raise LiveEvidenceError("Planned provider checks must remain unexecuted")
    if any(
        item["status"] != "not_started"
        or item["cleanup_status"] != "not_started"
        or item["evidence_refs"]
        or item["blocker_code"] is not None
        for item in exchanges
    ):
        raise LiveEvidenceError("Planned identity exchanges must remain unexecuted")
    if any(
        item["status"] != "not_started"
        or item["budget_reviewed"]
        or item["started_at"] is not None
        or item["completed_at"] is not None
        or item["artifacts"]
        or item["blocker_code"] is not None
        for item in record["scenarios"]
    ):
        raise LiveEvidenceError("Planned scenarios must remain unexecuted")


def _require_ready_plan(plan: Mapping[str, Any]) -> None:
    if (
        plan.get("status") != "approved_for_supervised_execution"
        or plan.get("execution_enabled") is not True
    ):
        raise LiveEvidenceError("Live evidence requires an approved ready plan")
    if any(
        not isinstance(item.get("budget_cap_usd"), (int, float))
        or item["budget_cap_usd"] <= 0
        for item in plan["scenarios"]
    ):
        raise LiveEvidenceError("Live evidence requires nine positive budget caps")


def _validate_phase_8_claims(
    record: Mapping[str, Any], *, allow_blockers: bool
) -> None:
    for check in record["phase_8"]["provider_checks"]:
        if check["status"] == "not_started" or not check["evidence_refs"]:
            raise LiveEvidenceError("Phase 8 provider claims require evidence")
        if check["account_scope_label"] is None or check["principal_label"] is None:
            raise LiveEvidenceError("Phase 8 provider claims require scope labels")
        if (check["status"] == "blocked") != (check["blocker_code"] is not None):
            raise LiveEvidenceError("Provider blocker status/code disagree")
        if check["status"] == "blocked" and not allow_blockers:
            raise LiveEvidenceError("Completed prerequisites cannot contain blockers")
    for exchange in record["phase_8"]["identity_exchanges"]:
        if exchange["status"] == "not_started" or not exchange["evidence_refs"]:
            raise LiveEvidenceError("Phase 8 identity claims require evidence")
        blocked = exchange["status"] == "blocked"
        if blocked != (exchange["blocker_code"] is not None):
            raise LiveEvidenceError("Identity blocker status/code disagree")
        if exchange["status"] == "succeeded" and exchange["cleanup_status"] != "clean":
            raise LiveEvidenceError("Successful identity probes require clean cleanup")
        if (blocked or exchange["cleanup_status"] == "residual") and not allow_blockers:
            raise LiveEvidenceError("Completed prerequisites cannot contain blockers")


def _validate_scenario_claims(record: Mapping[str, Any]) -> None:
    for scenario in record["scenarios"]:
        kinds = [artifact["kind"] for artifact in scenario["artifacts"]]
        if scenario["status"] == "not_started":
            if (
                scenario["started_at"] is not None
                or scenario["completed_at"] is not None
                or scenario["artifacts"]
                or scenario["blocker_code"] is not None
            ):
                raise LiveEvidenceError(
                    "Not-started scenario cannot contain runtime evidence"
                )
        elif scenario["status"] == "running":
            if (
                scenario["completed_at"] is not None
                or scenario["blocker_code"] is not None
            ):
                raise LiveEvidenceError(
                    "Running scenario cannot claim completion or a blocker"
                )
        elif scenario["status"] == "completed":
            missing = REQUIRED_SCENARIO_ARTIFACTS - set(kinds)
            if missing:
                raise LiveEvidenceError(
                    f"{scenario['scenario_id']}: completed evidence misses "
                    f"{sorted(missing)}"
                )
            if scenario["blocker_code"] is not None:
                raise LiveEvidenceError("Completed scenario cannot contain a blocker")
            ambiguous = sorted(
                kind for kind in REQUIRED_SCENARIO_ARTIFACTS if kinds.count(kind) != 1
            )
            if ambiguous:
                raise LiveEvidenceError(
                    f"{scenario['scenario_id']}: completed evidence requires exactly "
                    f"one artifact for each required kind; invalid={ambiguous}"
                )
        elif scenario["status"] == "blocked":
            if scenario["blocker_code"] is None or not scenario["artifacts"]:
                raise LiveEvidenceError("Blocked scenario requires evidence and a code")
            if "apply_operation" in kinds and not {
                "destroy_operation",
                "cleanup",
            }.issubset(kinds):
                raise LiveEvidenceError(
                    "A blocked scenario with Apply evidence requires Destroy and cleanup"
                )
        if scenario["status"] in {"running", "completed", "blocked"} and (
            scenario["started_at"] is None
        ):
            raise LiveEvidenceError("Started scenario requires a start timestamp")
        if scenario["status"] in {"completed", "blocked"} and (
            scenario["completed_at"] is None
        ):
            raise LiveEvidenceError("Terminal scenario requires a completion timestamp")


def _validate_state(record: Mapping[str, Any], *, plan: Mapping[str, Any]) -> None:
    status = record["status"]
    if status == "planned_not_executed":
        _validate_planned(record)
        return
    _require_ready_plan(plan)
    if (
        record["operator_label"] is None
        or record["cleanup_timer_owner_label"] is None
        or record["started_at"] is None
    ):
        raise LiveEvidenceError(
            "Live evaluation requires operator, timer owner, and start"
        )
    if any(
        scenario["budget_cap_usd"] is None or not scenario["budget_reviewed"]
        for scenario in record["scenarios"]
    ):
        raise LiveEvidenceError("Live evaluation requires nine reviewed budget caps")

    terminal = status in {"completed", "completed_with_blockers"}
    _validate_phase_8_claims(
        record,
        allow_blockers=status == "completed_with_blockers",
    )
    _validate_scenario_claims(record)
    scenario_statuses = [scenario["status"] for scenario in record["scenarios"]]
    if status == "prerequisites_complete" and any(
        value != "not_started" for value in scenario_statuses
    ):
        raise LiveEvidenceError("Prerequisite-complete evidence cannot claim scenarios")
    if status == "in_progress" and scenario_statuses.count("running") > 1:
        raise LiveEvidenceError("At most one live scenario may be running")
    if terminal:
        if any(value not in {"completed", "blocked"} for value in scenario_statuses):
            raise LiveEvidenceError("Final evidence requires nine terminal scenarios")
        if record["completed_at"] is None:
            raise LiveEvidenceError("Final evidence requires a completion timestamp")
        has_blocker = _has_phase_8_blocker(record) or "blocked" in scenario_statuses
        if (status == "completed_with_blockers") != has_blocker:
            raise LiveEvidenceError("Final status does not match recorded blockers")
    elif record["completed_at"] is not None:
        raise LiveEvidenceError("Non-final evidence cannot claim completion time")


def _validate_metrics_candidate_placement(
    metrics_record: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    scenario_id: str,
) -> None:
    assignments = candidate["assignments"]
    expected_scope = set(assignments.values())
    if set(metrics_record["provider_scope"]) != expected_scope:
        raise LiveEvidenceError(
            f"{scenario_id}: metrics provider scope does not match candidate placement"
        )
    for sample in metrics_record["message_samples"]:
        for stage in [*sample["stages"], *sample.get("auxiliary_stages", [])]:
            stage_id = stage["stage_id"]
            if stage_id in {"simulator_sent", "simulator_command_received"}:
                if stage["provider"] is not None:
                    raise LiveEvidenceError(
                        f"{scenario_id}: simulator checkpoint claims a cloud provider"
                    )
                continue
            component = METRIC_STAGE_COMPONENT.get(stage_id)
            if component is None:
                raise LiveEvidenceError(
                    f"{scenario_id}: metrics stage has no placement binding: {stage_id}"
                )
            if stage["provider"] != assignments[component]:
                raise LiveEvidenceError(
                    f"{scenario_id}: metrics stage {stage_id} does not match "
                    "candidate placement"
                )


def _validate_cleanup_artifact(
    cleanup: Mapping[str, Any],
    *,
    scenario_id: str,
    provider_scope: set[str],
    completed: bool,
) -> None:
    if cleanup.get("schema_version") != "cleanup-evidence.v1":
        raise LiveEvidenceError(f"{scenario_id}: cleanup evidence version is invalid")
    terraform = cleanup.get("terraform")
    providers = cleanup.get("providers")
    residuals = cleanup.get("residual_failures")
    if (
        not isinstance(terraform, dict)
        or not isinstance(providers, list)
        or not providers
        or any(not isinstance(item, dict) for item in providers)
        or not isinstance(residuals, list)
    ):
        raise LiveEvidenceError(f"{scenario_id}: cleanup evidence is incomplete")
    observed_providers = {
        item.get("provider") for item in providers if isinstance(item, dict)
    }
    if observed_providers != provider_scope:
        raise LiveEvidenceError(
            f"{scenario_id}: cleanup provider inventory does not match placement"
        )
    if completed and (
        cleanup.get("status") != "complete"
        or terraform.get("destroy_status") != "completed"
        or terraform.get("post_destroy_inventory") != "empty"
        or terraform.get("residual_resource_count") != 0
        or residuals
        or any(
            item.get("cleanup_status") != "completed"
            or item.get("post_destroy_inventory") != "empty"
            or item.get("residual_resource_count") != 0
            for item in providers
        )
    ):
        raise LiveEvidenceError(
            f"{scenario_id}: completed scenario requires clean terminal inventory"
        )


def _validate_metrics_cost_binding(
    metrics_record: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> None:
    scenario_id = scenario["scenario_id"]
    cost = metrics_record["cost"]
    if (
        cost["budget_cap_usd"] != scenario["budget_cap_usd"]
        or cost["estimated_monthly_total_usd"]
        != scenario["estimated_monthly_total_usd"]
    ):
        raise LiveEvidenceError(f"{scenario_id}: metrics cost binding drifted")
    provider_cost_paths = {
        artifact["path"]
        for artifact in scenario["artifacts"]
        if artifact["kind"] == "provider_cost"
    }
    source_path = cost["source_artifact_path"]
    if source_path is not None and source_path not in provider_cost_paths:
        raise LiveEvidenceError(
            f"{scenario_id}: observed cost source is not the indexed cost artifact"
        )
    if scenario["status"] == "completed" and (
        cost["observed_incremental_cost_usd"] is None
        or len(provider_cost_paths) != 1
    ):
        raise LiveEvidenceError(
            f"{scenario_id}: completed evidence requires one reconciled cost artifact"
        )


def validate_record(
    record: Mapping[str, Any],
    *,
    candidate_pack_dir: Path,
    evidence_root: Path,
    plan_path: Path = PLAN_PATH,
) -> dict[str, Any]:
    """Validate schema, source digests, evidence files, and lifecycle claims."""

    _validate_schema(record)
    plan, manifest, candidates, regions = load_candidate_pack(
        candidate_pack_dir,
        plan_path=plan_path,
    )
    _validate_pack_bindings(
        record,
        plan=plan,
        manifest=manifest,
        candidates=candidates,
        regions=regions,
    )
    for check in record["phase_8"]["provider_checks"]:
        _validate_evidence_refs(
            check["evidence_refs"],
            evidence_root=evidence_root,
            label=f"{check['provider']} provider check",
        )
    for exchange in record["phase_8"]["identity_exchanges"]:
        _validate_evidence_refs(
            exchange["evidence_refs"],
            evidence_root=evidence_root,
            label=(
                f"{exchange['source_provider']}-to-"
                f"{exchange['destination_provider']} identity exchange"
            ),
        )
    for scenario in record["scenarios"]:
        _validate_evidence_refs(
            scenario["artifacts"],
            evidence_root=evidence_root,
            label=scenario["scenario_id"],
        )
        candidate = candidates[scenario["scenario_id"]]
        provider_scope = set(candidate["assignments"].values())
        for artifact in scenario["artifacts"]:
            if artifact["kind"] != "cleanup":
                continue
            cleanup_relative = _safe_relative_path(
                artifact["path"],
                label=f"{scenario['scenario_id']} cleanup path",
            )
            cleanup_record = _read(
                _resolve_under(
                    evidence_root,
                    cleanup_relative,
                    label=f"{scenario['scenario_id']} cleanup file",
                )
            )
            _validate_cleanup_artifact(
                cleanup_record,
                scenario_id=scenario["scenario_id"],
                provider_scope=provider_scope,
                completed=scenario["status"] == "completed",
            )
        for artifact in scenario["artifacts"]:
            if artifact["kind"] != "evaluation_metrics":
                continue
            relative = _safe_relative_path(
                artifact["path"],
                label=f"{scenario['scenario_id']} metrics path",
            )
            metrics_path = _resolve_under(
                evidence_root,
                relative,
                label=f"{scenario['scenario_id']} metrics file",
            )
            metrics_record = _read(metrics_path)
            try:
                validate_metrics(metrics_record)
            except LiveMetricsError as exc:
                raise LiveEvidenceError(
                    f"{scenario['scenario_id']}: invalid evaluation metrics: {exc}"
                ) from exc
            if (
                metrics_record["scenario_id"] != scenario["scenario_id"]
                or metrics_record["subject_id"] != scenario["scenario_id"]
                or metrics_record["candidate_evidence_digest"]
                != scenario["candidate_evidence_digest"]
            ):
                raise LiveEvidenceError(
                    f"{scenario['scenario_id']}: metrics binding drifted"
                )
            _validate_metrics_candidate_placement(
                metrics_record,
                candidate,
                scenario_id=scenario["scenario_id"],
            )
            _validate_metrics_cost_binding(metrics_record, scenario)
    _validate_state(record, plan=plan)
    return {
        "status": record["status"],
        "provider_check_count": len(record["phase_8"]["provider_checks"]),
        "identity_exchange_count": len(record["phase_8"]["identity_exchanges"]),
        "scenario_count": len(record["scenarios"]),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the digest-bound supervised live-evaluation index."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="Create a not-started index.")
    create.add_argument("--candidate-pack", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate", help="Validate an evidence index.")
    validate.add_argument("--candidate-pack", type=Path, required=True)
    validate.add_argument("--record", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "create":
        if arguments.output.exists():
            raise LiveEvidenceError(
                f"Evidence index already exists: {arguments.output}"
            )
        record = create_template(arguments.candidate_pack)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validate_record(
            record,
            candidate_pack_dir=arguments.candidate_pack,
            evidence_root=arguments.output.parent,
        )
        print(f"live-evaluation-evidence: created {arguments.output}")
        return 0

    record = _read(arguments.record)
    result = validate_record(
        record,
        candidate_pack_dir=arguments.candidate_pack,
        evidence_root=arguments.record.parent,
    )
    print(
        "live-evaluation-evidence: OK "
        f"(status={result['status']}, "
        f"providers={result['provider_check_count']}, "
        f"directions={result['identity_exchange_count']}, "
        f"scenarios={result['scenario_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
