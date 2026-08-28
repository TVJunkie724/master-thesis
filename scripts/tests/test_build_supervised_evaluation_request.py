from __future__ import annotations

import json

import pytest

from scripts import build_supervised_evaluation_request as builder


def test_request_binds_approved_candidate_and_small_workload(tmp_path, monkeypatch):
    workload_path = tmp_path / "small.json"
    workload = {
        "schemaVersion": "six-layer-workload.v1",
        "eventingScenarioId": "eventing-small-v1",
    }
    workload_path.write_text(json.dumps(workload), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({"workload_fixture": str(workload_path)}),
        encoding="utf-8",
    )
    candidate = {
        "candidate_id": "aws|azure|azure|azure|azure|azure|azure|azure",
        "evidence_digest": "sha256:" + ("3" * 64),
    }
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "validate", lambda **_kwargs: {})
    monkeypatch.setattr(
        builder,
        "load_candidate_pack",
        lambda *_args, **_kwargs: (
            {"workload_fixture": str(workload_path)},
            {
                "plan_digest": "sha256:" + ("4" * 64),
                "manifest_digest": "sha256:" + ("5" * 64),
            },
            {"small-focus-aws-to-azure": candidate},
            {},
        ),
    )

    request = builder.build_request(
        tmp_path / "pack",
        "small-focus-aws-to-azure",
        plan_path=plan_path,
    )

    assert request == {
        "params": workload,
        "scenario_id": "small-focus-aws-to-azure",
        "candidate_id": candidate["candidate_id"],
        "candidate_evidence_digest": candidate["evidence_digest"],
        "plan_digest": "sha256:" + ("4" * 64),
        "candidate_pack_manifest_digest": "sha256:" + ("5" * 64),
        "confirmation": builder.CONFIRMATION,
    }


def test_request_rejects_unknown_scenario(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "validate", lambda **_kwargs: {})
    monkeypatch.setattr(
        builder,
        "load_candidate_pack",
        lambda *_args, **_kwargs: ({}, {}, {}, {}),
    )

    with pytest.raises(
        builder.SupervisedEvaluationRequestError,
        match="does not contain scenario",
    ):
        builder.build_request(tmp_path / "pack", "small-local-aws")
