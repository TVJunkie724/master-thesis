from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import materialize_live_evaluation_candidate as materializer
from scripts import review_live_evaluation_budget as budget


@pytest.fixture(scope="module")
def candidate_pack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("live-budget") / "candidate-pack"
    materializer.materialize_plan(output)
    return output


def test_budget_proposal_is_digest_bound_and_keeps_execution_disabled(
    candidate_pack: Path,
) -> None:
    proposal = budget.build_proposal(candidate_pack)

    assert proposal["status"] == "offline_complete_pending_operator_approval"
    assert proposal["execution_enabled"] is False
    assert proposal["maximum_runtime_minutes"] == 60
    assert proposal["scenario_count"] == 9
    assert proposal["proposal_digest"] == budget._digest(
        {key: value for key, value in proposal.items() if key != "proposal_digest"}
    )
    assert all(
        item["matrix_budget_cap_usd"] is None
        and item["review_status"] == "pending_operator_approval"
        for item in proposal["scenarios"]
    )


def test_budget_proposals_are_bounded_to_the_checked_small_matrix(
    candidate_pack: Path,
) -> None:
    proposal = budget.build_proposal(candidate_pack)

    assert {
        item["scenario_id"]: item["proposed_budget_cap_usd"]
        for item in proposal["scenarios"]
    } == {
        "small-local-aws": 50,
        "small-local-azure": 105,
        "small-local-gcp": 35,
        "small-focus-aws-to-azure": 105,
        "small-focus-azure-to-aws": 45,
        "small-focus-aws-to-gcp": 45,
        "small-focus-gcp-to-aws": 35,
        "small-focus-azure-to-gcp": 35,
        "small-focus-gcp-to-azure": 35,
    }


def test_budget_policy_runtime_must_match_the_matrix(
    candidate_pack: Path,
    tmp_path: Path,
) -> None:
    policy = budget._read(budget.POLICY_PATH)
    policy["maximum_runtime_minutes"] = 61
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(budget.BudgetReviewError, match="runtime drifted"):
        budget.build_proposal(candidate_pack, policy_path=policy_path)


def test_external_timer_reserves_cleanup_before_the_deadline(
    candidate_pack: Path,
) -> None:
    proposal = budget.build_proposal(candidate_pack)
    timer = proposal["external_timer"]

    assert timer["warning_at_minutes"] == 45
    assert timer["destroy_trigger_at_minutes"] == 50
    assert timer["cleanup_deadline_at_minutes"] == 60
    assert timer["start_before_terraform_plan"] is True


def test_budget_proposal_refuses_to_overwrite_prior_review(
    candidate_pack: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "budget-proposal.json"
    output.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        budget.write_proposal(candidate_pack, output)
