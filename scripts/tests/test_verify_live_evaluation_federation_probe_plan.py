"""Contract tests for the bounded directed federation-probe plan."""

from __future__ import annotations

import copy

import pytest

from scripts import verify_live_evaluation_federation_probe_plan as verifier


def _write_with_digest(tmp_path, value):
    value["record_digest"] = verifier._digest(
        {key: item for key, item in value.items() if key != "record_digest"}
    )
    path = tmp_path / "probe-plan.json"
    path.write_text(verifier._canonical_json(value), encoding="utf-8")
    return path


def test_tracked_federation_probe_plan_is_valid_and_disabled() -> None:
    plan = verifier.verify(verifier.DEFAULT_PLAN, verifier.DEFAULT_SCHEMA)

    assert plan["execution_enabled"] is False
    assert plan["cloud_mutation_performed"] is False
    assert plan["summary"]["directed_routes_planned"] == 6
    assert plan["summary"]["probes_approved"] == 0
    assert plan["summary"]["probes_executed"] == 0


def test_plan_covers_each_matrix_direction_and_runtime_contract_once() -> None:
    plan = verifier.verify(verifier.DEFAULT_PLAN, verifier.DEFAULT_SCHEMA)
    actual = {
        (probe["source_provider"], probe["destination_provider"]): probe[
            "exchange_contract"
        ]
        for probe in plan["probes"]
    }

    assert actual == verifier.IDENTITY_EXCHANGE_BY_PAIR


def test_plan_is_bound_to_current_candidate_pack() -> None:
    plan = verifier._load(verifier.DEFAULT_PLAN)
    image_readiness = verifier._load(verifier.IMAGE_READINESS_PATH)

    assert (
        plan["candidate_pack_manifest_digest"]
        == image_readiness["candidate_pack_manifest_digest"]
    )


def test_record_digest_mutation_fails_closed(tmp_path) -> None:
    plan = verifier._load(verifier.DEFAULT_PLAN)
    plan["probes"][0]["maximum_elapsed_minutes"] = 9
    path = tmp_path / "mutated.json"
    path.write_text(verifier._canonical_json(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="plan digest mismatch"):
        verifier.verify(path, verifier.DEFAULT_SCHEMA)


def test_non_identity_resource_fails_closed(tmp_path) -> None:
    plan = copy.deepcopy(verifier._load(verifier.DEFAULT_PLAN))
    plan["probes"][0]["resources"].append(
        {
            "provider": "aws",
            "type": "aws.kinesis_stream",
            "count": 1,
            "purpose": "Must not enter a standalone identity probe",
            "direct_charge": True,
        }
    )
    path = _write_with_digest(tmp_path, plan)

    with pytest.raises(ValueError, match="non-identity probe resource"):
        verifier.verify(path, verifier.DEFAULT_SCHEMA)


def test_aggregate_cost_cap_drift_fails_closed(tmp_path) -> None:
    plan = copy.deepcopy(verifier._load(verifier.DEFAULT_PLAN))
    plan["probes"][2]["direct_cost_cap_usd"] = "0.020000"
    path = _write_with_digest(tmp_path, plan)

    with pytest.raises(ValueError, match="Azure source cap changed"):
        verifier.verify(path, verifier.DEFAULT_SCHEMA)
