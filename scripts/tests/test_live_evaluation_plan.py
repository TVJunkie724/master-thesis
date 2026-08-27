from __future__ import annotations

import copy

import pytest

from scripts import validate_live_evaluation_plan as evaluation


def test_live_evaluation_plan_covers_the_bounded_matrix() -> None:
    result = evaluation.validate()

    assert result["scenario_count"] == 9
    assert result["local_provider_count"] == 3
    assert result["directed_pair_count"] == 6
    assert result["edge_contract_count"] == 4
    assert result["cross_cloud_edge_contract_count"] == 3
    assert len(result["missing_budget_caps"]) == 9


def test_live_evaluation_cannot_be_enabled_without_reviewed_budgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = evaluation._read(evaluation.PLAN_PATH)
    plan["execution_enabled"] = True
    original_read = evaluation._read

    def read_with_enabled_plan(path):
        if path == evaluation.PLAN_PATH:
            return copy.deepcopy(plan)
        return original_read(path)

    monkeypatch.setattr(evaluation, "_read", read_with_enabled_plan)
    with pytest.raises(RuntimeError, match="remain disabled"):
        evaluation.validate()


def test_live_evaluation_rejects_non_materializable_visualization_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = evaluation._read(evaluation.PLAN_PATH)
    plan["scenarios"][3]["assignments"]["component.visualization"] = "gcp"
    original_read = evaluation._read

    def read_with_invalid_plan(path):
        if path == evaluation.PLAN_PATH:
            return copy.deepcopy(plan)
        return original_read(path)

    monkeypatch.setattr(evaluation, "_read", read_with_invalid_plan)
    with pytest.raises(RuntimeError, match="must be co-located"):
        evaluation.validate()
