from __future__ import annotations

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
