from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_live_evaluation_plan as validator


def _plan() -> dict:
    return json.loads(validator.PLAN_PATH.read_text(encoding="utf-8"))


def _use_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, plan: dict) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(validator, "PLAN_PATH", path)


def test_checked_matrix_is_valid_only_as_planned() -> None:
    result = validator.validate(required_state="planned")

    assert result["scenario_count"] == 9
    assert result["directed_pair_count"] == 6
    assert result["required_state"] == "planned"
    assert len(result["missing_budget_caps"]) == 9

    with pytest.raises(RuntimeError, match="approved_for_supervised_execution"):
        validator.validate(required_state="ready")


def test_reviewed_budget_caps_enable_only_the_ready_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan = _plan()
    plan["status"] = "approved_for_supervised_execution"
    plan["execution_enabled"] = True
    for scenario in plan["scenarios"]:
        scenario["budget_cap_usd"] = 10.0
    _use_plan(monkeypatch, tmp_path, plan)

    result = validator.validate(required_state="ready")

    assert result["required_state"] == "ready"
    assert result["missing_budget_caps"] == []
    with pytest.raises(RuntimeError, match="explicit status"):
        validator.validate(required_state="planned")


@pytest.mark.parametrize("budget", [None, 0, -1, True, float("inf"), float("nan")])
def test_ready_gate_rejects_missing_or_invalid_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    budget: float | None,
) -> None:
    plan = _plan()
    plan["status"] = "approved_for_supervised_execution"
    plan["execution_enabled"] = True
    for scenario in plan["scenarios"]:
        scenario["budget_cap_usd"] = 10.0
    plan["scenarios"][0]["budget_cap_usd"] = budget
    _use_plan(monkeypatch, tmp_path, plan)

    message = "invalid budget cap" if budget is not None else "nine budget caps"
    with pytest.raises(RuntimeError, match=message):
        validator.validate(required_state="ready")
