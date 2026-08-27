from __future__ import annotations

import json

import pytest

from scripts import materialize_live_evaluation_candidate as materializer


def test_candidate_ids_match_the_checked_evaluation_matrix() -> None:
    plan = materializer._read(materializer.PLAN_PATH)

    actual = {
        item["scenario_id"]: materializer.candidate_id_for(item["assignments"])
        for item in plan["scenarios"]
    }

    assert actual == {
        "small-local-aws": "aws|aws|aws|aws|aws|aws|aws|aws",
        "small-local-azure": ("azure|azure|azure|azure|azure|azure|azure|azure"),
        "small-local-gcp": "gcp|gcp|gcp|gcp|gcp|gcp|gcp|gcp",
        "small-focus-aws-to-azure": ("aws|azure|azure|azure|azure|azure|azure|azure"),
        "small-focus-azure-to-aws": ("azure|aws|aws|aws|aws|aws|aws|azure"),
        "small-focus-aws-to-gcp": "aws|aws|aws|aws|aws|gcp|aws|aws",
        "small-focus-gcp-to-aws": "gcp|gcp|gcp|gcp|gcp|gcp|gcp|aws",
        "small-focus-azure-to-gcp": ("azure|azure|azure|gcp|gcp|azure|azure|azure"),
        "small-focus-gcp-to-azure": ("gcp|gcp|gcp|gcp|azure|gcp|gcp|gcp"),
    }


def test_unknown_scenario_is_rejected_before_costing() -> None:
    plan = materializer._read(materializer.PLAN_PATH)

    with pytest.raises(ValueError, match="Unknown evaluation scenario"):
        materializer._scenario(plan, "missing-scenario")


def test_complete_plan_materializes_as_digest_bound_pack(tmp_path) -> None:
    output_dir = tmp_path / "candidate-pack"

    manifest = materializer.materialize_plan(output_dir)

    assert manifest["scenario_count"] == 9
    assert manifest["manifest_digest"] == materializer._digest(
        {key: value for key, value in manifest.items() if key != "manifest_digest"}
    )
    assert (output_dir / "candidate-pack-manifest.json").is_file()
    assert [item["scenario_id"] for item in manifest["candidates"]] == [
        "small-local-aws",
        "small-local-azure",
        "small-local-gcp",
        "small-focus-aws-to-azure",
        "small-focus-azure-to-aws",
        "small-focus-aws-to-gcp",
        "small-focus-gcp-to-aws",
        "small-focus-azure-to-gcp",
        "small-focus-gcp-to-azure",
    ]
    for item in manifest["candidates"]:
        candidate = json.loads(
            (output_dir / item["candidate_file"]).read_text(encoding="utf-8")
        )
        assert candidate["scenario_id"] == item["scenario_id"]
        assert candidate["candidate_id"] == item["candidate_id"]
        assert candidate["evidence_digest"] == item["candidate_evidence_digest"]
        assert candidate["evidence_digest"] == materializer._digest(
            {key: value for key, value in candidate.items() if key != "evidence_digest"}
        )


def test_complete_plan_refuses_to_overwrite_prior_evidence(tmp_path) -> None:
    output_dir = tmp_path / "candidate-pack"
    output_dir.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        materializer.materialize_plan(output_dir)
