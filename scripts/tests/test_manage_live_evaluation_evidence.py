from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import manage_live_evaluation_evidence as evidence

REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
TERMINAL_ARTIFACTS = (
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
)
TIMESTAMP = "2026-08-28T12:00:00Z"


def _read_plan(*, ready: bool = False) -> dict:
    plan = json.loads(evidence.PLAN_PATH.read_text(encoding="utf-8"))
    if ready:
        plan["status"] = "approved_for_supervised_execution"
        plan["execution_enabled"] = True
        for scenario in plan["scenarios"]:
            scenario["budget_cap_usd"] = 10.0
    return plan


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _candidate_pack(tmp_path: Path, plan: dict) -> tuple[Path, Path]:
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, plan)
    plan_digest = evidence._document_digest(plan)
    pack_dir = tmp_path / "candidate-pack"
    pack_dir.mkdir()
    entries = []
    for index, scenario in enumerate(plan["scenarios"], start=1):
        scenario_id = scenario["scenario_id"]
        providers = sorted(set(scenario["assignments"].values()))
        candidate = {
            "schema_version": "six-layer-evaluation-candidate.v1",
            "evidence_status": "offline_planned_candidate",
            "scenario_id": scenario_id,
            "candidate_id": "|".join(scenario["assignments"].values()),
            "plan_digest": plan_digest,
            "cost_evaluation": {
                "currency": "USD",
                "monthly_total": f"{100 + index}.00",
            },
            "resolved_deployment_specification": {
                "component_selections": [
                    {
                        "provider": provider,
                        "region": REGIONS[provider],
                    }
                    for provider in providers
                ]
            },
        }
        candidate["evidence_digest"] = evidence._document_digest(candidate)
        filename = f"{scenario_id}.candidate.json"
        _write_json(pack_dir / filename, candidate)
        entries.append(
            {
                "scenario_id": scenario_id,
                "candidate_id": candidate["candidate_id"],
                "candidate_file": filename,
                "candidate_evidence_digest": candidate["evidence_digest"],
                "currency": "USD",
                "monthly_total": candidate["cost_evaluation"]["monthly_total"],
            }
        )
    manifest = {
        "schema_version": "six-layer-evaluation-candidate-pack.v1",
        "evidence_status": "offline_planned_candidates",
        "plan_digest": plan_digest,
        "scenario_count": 9,
        "candidates": entries,
    }
    manifest["manifest_digest"] = evidence._document_digest(manifest)
    _write_json(pack_dir / "candidate-pack-manifest.json", manifest)
    return pack_dir, plan_path


def _reference(root: Path, relative: str, value: object) -> dict[str, str]:
    path = root / relative
    _write_json(path, value)
    return {"path": relative, "digest": evidence._file_digest(path)}


def _metrics_record(scenario: dict) -> dict:
    scenario_id = scenario["scenario_id"]
    if scenario_id.startswith("small-local-"):
        providers = [scenario_id.removeprefix("small-local-")]
        run_kind = "provider_local"
    else:
        direction = scenario_id.removeprefix("small-focus-")
        source, destination = direction.split("-to-")
        providers = [source, destination]
        run_kind = "directed_multicloud"
    source = providers[0]
    return {
        "schema_version": "live-evaluation-metrics.v1",
        "evidence_status": "live_observation",
        "run_id": f"run-{scenario_id}",
        "run_kind": run_kind,
        "subject_id": scenario_id,
        "scenario_id": scenario_id,
        "candidate_evidence_digest": scenario["candidate_evidence_digest"],
        "architecture_contract": "six-layer-eventing@1",
        "source_revision": "abcdef1",
        "workload_digest": "sha256:" + "a" * 64,
        "simulator_digest": "sha256:" + "b" * 64,
        "provider_scope": providers,
        "started_at": "2026-08-28T12:00:00Z",
        "completed_at": "2026-08-28T12:30:00Z",
        "clock": {
            "synchronized": True,
            "method": "test-clock",
            "checked_at": "2026-08-28T12:00:00Z",
            "max_observed_skew_ms": 1,
        },
        "protocol": {
            "warmup_messages_per_direction": 0,
            "measured_messages_per_direction": 1,
            "payload_bytes": 256,
            "cadence_ms": 1000,
            "cold_start_observed": False,
            "directions": ["telemetry"],
            "expected_paths": [
                {
                    "direction": "telemetry",
                    "stage_ids": ["simulator_sent", "l1_accepted"],
                }
            ],
            "notes": ["Synthetic unit-test fixture."],
        },
        "lifecycle": [
            {
                "phase": "terraform_apply",
                "provider": source,
                "status": "completed",
                "started_at": "2026-08-28T12:00:00Z",
                "completed_at": "2026-08-28T12:00:01Z",
                "duration_ms": 1000,
            }
        ],
        "message_samples": [
            {
                "trace_id": f"trace-{scenario_id}",
                "sequence": 1,
                "sample_set": "measured",
                "direction": "telemetry",
                "payload_bytes": 256,
                "status": "succeeded",
                "stages": [
                    {
                        "stage_id": "simulator_sent",
                        "provider": None,
                        "layer": "simulator",
                        "observed_at": "2026-08-28T12:00:02Z",
                        "clock_source": "simulator",
                        "event_id": f"event-{scenario_id}",
                    },
                    {
                        "stage_id": "l1_accepted",
                        "provider": source,
                        "layer": "L1",
                        "observed_at": "2026-08-28T12:00:02.100Z",
                        "clock_source": "provider",
                        "event_id": f"event-{scenario_id}",
                    },
                ],
                "retry_count": 0,
                "duplicate_count": 0,
                "ordering_ok": True,
                "dlq_observed": False,
                "failure_code": None,
            }
        ],
        "resources": [],
        "cost": {
            "currency": "USD",
            "budget_cap_usd": scenario["budget_cap_usd"],
            "estimated_monthly_total_usd": scenario["estimated_monthly_total_usd"],
            "observed_incremental_cost_usd": None,
            "observation_started_at": None,
            "observation_completed_at": None,
            "source_artifact_path": None,
        },
        "cleanup": {
            "completed_at": "2026-08-28T12:29:00Z",
            "inventory_clean": True,
            "residual_count": 0,
            "residual_types": [],
        },
        "limitations": ["Synthetic unit-test fixture."],
    }


def _completed_record(
    tmp_path: Path,
) -> tuple[dict, Path, Path, Path]:
    plan = _read_plan(ready=True)
    pack_dir, plan_path = _candidate_pack(tmp_path, plan)
    record = evidence.create_template(pack_dir, plan_path=plan_path)
    record.update(
        {
            "status": "completed",
            "operator_label": "supervised-operator",
            "cleanup_timer_owner_label": "cleanup-owner",
            "started_at": TIMESTAMP,
            "completed_at": "2026-08-28T15:00:00Z",
        }
    )
    evidence_root = tmp_path / "evidence"
    for check in record["phase_8"]["provider_checks"]:
        provider = check["provider"]
        check.update(
            {
                "account_scope_label": f"thesis-{provider}-scope",
                "principal_label": f"thesis-{provider}-principal",
                "status": "ready",
                "evidence_refs": [
                    _reference(
                        evidence_root,
                        f"phase-8/{provider}-preflight.json",
                        {"provider": provider, "status": "ready"},
                    )
                ],
            }
        )
    for exchange in record["phase_8"]["identity_exchanges"]:
        source = exchange["source_provider"]
        destination = exchange["destination_provider"]
        exchange.update(
            {
                "status": "succeeded",
                "cleanup_status": "clean",
                "evidence_refs": [
                    _reference(
                        evidence_root,
                        f"phase-8/{source}-to-{destination}.json",
                        {
                            "source": source,
                            "destination": destination,
                            "status": "succeeded_and_clean",
                        },
                    )
                ],
            }
        )
    for scenario in record["scenarios"]:
        scenario_id = scenario["scenario_id"]
        artifacts = []
        for kind in TERMINAL_ARTIFACTS:
            value = (
                _metrics_record(scenario)
                if kind == "evaluation_metrics"
                else {
                    "scenario_id": scenario_id,
                    "kind": kind,
                    "status": "observed",
                }
            )
            artifacts.append(
                {
                    "kind": kind,
                    **_reference(
                        evidence_root,
                        f"{scenario_id}/{kind}.json",
                        value,
                    ),
                }
            )
        scenario.update(
            {
                "budget_reviewed": True,
                "status": "completed",
                "started_at": TIMESTAMP,
                "completed_at": "2026-08-28T12:30:00Z",
                "artifacts": artifacts,
            }
        )
    return record, pack_dir, plan_path, evidence_root


def test_planned_template_binds_exact_matrix_and_pack(tmp_path: Path) -> None:
    pack_dir, plan_path = _candidate_pack(tmp_path, _read_plan())
    record = evidence.create_template(pack_dir, plan_path=plan_path)

    result = evidence.validate_record(
        record,
        candidate_pack_dir=pack_dir,
        evidence_root=tmp_path,
        plan_path=plan_path,
    )

    assert result == {
        "status": "planned_not_executed",
        "provider_check_count": 3,
        "identity_exchange_count": 6,
        "scenario_count": 9,
    }


def test_candidate_pack_digest_drift_is_rejected(tmp_path: Path) -> None:
    pack_dir, plan_path = _candidate_pack(tmp_path, _read_plan())
    record = evidence.create_template(pack_dir, plan_path=plan_path)
    candidate_path = next(pack_dir.glob("small-local-aws.candidate.json"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["candidate_id"] = "drifted"
    _write_json(candidate_path, candidate)

    with pytest.raises(evidence.LiveEvidenceError, match="candidate digest"):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=tmp_path,
            plan_path=plan_path,
        )


def test_completed_record_requires_all_digest_verified_artifacts(
    tmp_path: Path,
) -> None:
    record, pack_dir, plan_path, evidence_root = _completed_record(tmp_path)

    result = evidence.validate_record(
        record,
        candidate_pack_dir=pack_dir,
        evidence_root=evidence_root,
        plan_path=plan_path,
    )

    assert result["status"] == "completed"
    record["scenarios"][0]["artifacts"] = [
        artifact
        for artifact in record["scenarios"][0]["artifacts"]
        if artifact["kind"] != "cleanup"
    ]
    with pytest.raises(evidence.LiveEvidenceError, match="completed evidence misses"):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=evidence_root,
            plan_path=plan_path,
        )


def test_referenced_evidence_digest_drift_is_rejected(tmp_path: Path) -> None:
    record, pack_dir, plan_path, evidence_root = _completed_record(tmp_path)
    reference = record["scenarios"][0]["artifacts"][0]
    _write_json(evidence_root / reference["path"], {"status": "tampered"})

    with pytest.raises(evidence.LiveEvidenceError, match="evidence digest"):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=evidence_root,
            plan_path=plan_path,
        )


def test_metrics_must_bind_to_exact_scenario_candidate(tmp_path: Path) -> None:
    record, pack_dir, plan_path, evidence_root = _completed_record(tmp_path)
    scenario = record["scenarios"][0]
    artifact = next(
        item for item in scenario["artifacts"] if item["kind"] == "evaluation_metrics"
    )
    path = evidence_root / artifact["path"]
    value = json.loads(path.read_text(encoding="utf-8"))
    value["candidate_evidence_digest"] = "sha256:" + "f" * 64
    _write_json(path, value)
    artifact["digest"] = evidence._file_digest(path)

    with pytest.raises(evidence.LiveEvidenceError, match="metrics binding drifted"):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=evidence_root,
            plan_path=plan_path,
        )


def test_completed_scenario_requires_exactly_one_metrics_artifact(
    tmp_path: Path,
) -> None:
    record, pack_dir, plan_path, evidence_root = _completed_record(tmp_path)
    scenario = record["scenarios"][0]
    metrics_artifact = next(
        item for item in scenario["artifacts"] if item["kind"] == "evaluation_metrics"
    )
    metrics_value = json.loads(
        (evidence_root / metrics_artifact["path"]).read_text(encoding="utf-8")
    )
    scenario["artifacts"].append(
        {
            "kind": "evaluation_metrics",
            **_reference(
                evidence_root,
                f"{scenario['scenario_id']}/evaluation-metrics-copy.json",
                metrics_value,
            ),
        }
    )

    with pytest.raises(evidence.LiveEvidenceError, match="exactly one"):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=evidence_root,
            plan_path=plan_path,
        )


def test_final_status_must_disclose_recorded_blocker(tmp_path: Path) -> None:
    record, pack_dir, plan_path, evidence_root = _completed_record(tmp_path)
    record["scenarios"][0]["status"] = "blocked"
    record["scenarios"][0]["blocker_code"] = "provider-runtime-blocker"

    with pytest.raises(evidence.LiveEvidenceError, match="Final status"):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=evidence_root,
            plan_path=plan_path,
        )

    record["status"] = "completed_with_blockers"
    result = evidence.validate_record(
        record,
        candidate_pack_dir=pack_dir,
        evidence_root=evidence_root,
        plan_path=plan_path,
    )
    assert result["status"] == "completed_with_blockers"


def test_evidence_reference_cannot_escape_directory(tmp_path: Path) -> None:
    record, pack_dir, plan_path, evidence_root = _completed_record(tmp_path)
    record["scenarios"][0]["artifacts"][0]["path"] = "../outside.json"

    with pytest.raises(evidence.LiveEvidenceError):
        evidence.validate_record(
            record,
            candidate_pack_dir=pack_dir,
            evidence_root=evidence_root,
            plan_path=plan_path,
        )
