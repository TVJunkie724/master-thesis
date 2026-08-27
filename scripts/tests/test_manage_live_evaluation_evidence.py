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
        scenario.update(
            {
                "budget_reviewed": True,
                "status": "completed",
                "started_at": TIMESTAMP,
                "completed_at": "2026-08-28T12:30:00Z",
                "artifacts": [
                    {
                        "kind": kind,
                        **_reference(
                            evidence_root,
                            f"{scenario_id}/{kind}.json",
                            {
                                "scenario_id": scenario_id,
                                "kind": kind,
                                "status": "observed",
                            },
                        ),
                    }
                    for kind in TERMINAL_ARTIFACTS
                ],
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
