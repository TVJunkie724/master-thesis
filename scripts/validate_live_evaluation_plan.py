"""Validate the bounded Six-layer live-evaluation plan without executing it."""

from __future__ import annotations

import argparse
import json
from itertools import permutations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs/research/evaluation/small-scenario-matrix.json"
PROFILE_PATH = (
    ROOT
    / "contracts/architecture-profiles/definitions/profiles"
    / "six-layer-eventing/1/profile.json"
)
PROVIDERS = {"aws", "azure", "gcp"}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def validate(*, required_state: str = "planned") -> dict[str, Any]:
    plan = _read(PLAN_PATH)
    profile = _read(PROFILE_PATH)
    scenarios = plan.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 9:
        raise RuntimeError("Live evaluation must contain exactly nine scenarios")
    if plan.get("architecture_profile") != "six-layer-eventing@1":
        raise RuntimeError("Live evaluation must pin six-layer-eventing@1")
    if required_state not in {"planned", "ready"}:
        raise ValueError(f"Unsupported required state: {required_state}")

    workload_path = ROOT / str(plan.get("workload_fixture", ""))
    workload = _read(workload_path)
    if workload.get("eventingScenarioId") != "eventing-small-v1":
        raise RuntimeError("Live evaluation may use only the Small workload")

    components = {item["component_id"] for item in profile["components"]}
    edges = {item["edge_id"]: item for item in profile["edges"]}
    required_contracts = {item["edge_contract_id"] for item in profile["edges"]}
    scenario_ids: set[str] = set()
    local_providers: set[str] = set()
    directed_pairs: set[tuple[str, str]] = set()
    focused_contracts: set[str] = set()
    covered_contracts: set[str] = set()

    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id in scenario_ids:
            raise RuntimeError("Scenario IDs must be unique strings")
        scenario_ids.add(scenario_id)
        assignments = scenario.get("assignments")
        if not isinstance(assignments, dict) or set(assignments) != components:
            raise RuntimeError(f"{scenario_id}: component coverage is incomplete")
        if set(assignments.values()) - PROVIDERS:
            raise RuntimeError(f"{scenario_id}: unsupported provider assignment")
        if (
            assignments["component.hot-storage"]
            != assignments["component.visualization"]
        ):
            raise RuntimeError(
                f"{scenario_id}: hot storage and visualization must be co-located"
            )
        covered_contracts.update(edge["edge_contract_id"] for edge in edges.values())

        kind = scenario.get("kind")
        focus = scenario.get("focus")
        if not isinstance(focus, dict):
            raise TypeError(f"{scenario_id}: missing focus")
        if kind == "provider_local_baseline":
            provider = focus.get("provider")
            if provider not in PROVIDERS or set(assignments.values()) != {provider}:
                raise RuntimeError(f"{scenario_id}: invalid local baseline")
            local_providers.add(provider)
        elif kind == "directed_multicloud_focus":
            source = focus.get("source_provider")
            destination = focus.get("destination_provider")
            pair = (source, destination)
            if pair not in set(permutations(PROVIDERS, 2)):
                raise RuntimeError(f"{scenario_id}: invalid directed provider pair")
            edge = edges.get(focus.get("edge_id"))
            if edge is None:
                raise RuntimeError(f"{scenario_id}: unknown focus edge")
            if (
                assignments[edge["source_component_id"]] != source
                or assignments[edge["destination_component_id"]] != destination
            ):
                raise RuntimeError(f"{scenario_id}: focus edge direction drifted")
            directed_pairs.add(pair)
            focused_contracts.add(edge["edge_contract_id"])
        else:
            raise RuntimeError(f"{scenario_id}: unsupported scenario kind")

        budget = scenario.get("budget_cap_usd")
        if budget is not None and (not isinstance(budget, (int, float)) or budget <= 0):
            raise RuntimeError(f"{scenario_id}: invalid budget cap")

    if local_providers != PROVIDERS:
        raise RuntimeError("Provider-local baseline coverage is incomplete")
    if directed_pairs != set(permutations(PROVIDERS, 2)):
        raise RuntimeError("Directed provider-pair coverage is incomplete")
    cross_cloud_contracts = required_contracts - {"raw_history_query.v1"}
    if focused_contracts != cross_cloud_contracts:
        raise RuntimeError(
            "Focus cases do not cover every cross-cloud edge-contract class"
        )
    if covered_contracts != required_contracts:
        raise RuntimeError("Scenario set does not exercise every edge-contract class")

    guardrails = plan.get("guardrails")
    required_true = {
        "one_active_scenario",
        "destroy_attempt_required",
        "post_destroy_inventory_required",
        "stop_after_residual_resource",
        "stop_after_unexplained_cost_deviation",
    }
    if not isinstance(guardrails, dict) or any(
        guardrails.get(key) is not True for key in required_true
    ):
        raise RuntimeError("Mandatory cost and cleanup guardrails are incomplete")
    if guardrails.get("maximum_runtime_minutes") != 60:
        raise RuntimeError("Live scenario runtime must remain capped at 60 minutes")

    missing_budgets = [
        item["scenario_id"] for item in scenarios if item.get("budget_cap_usd") is None
    ]
    if required_state == "planned":
        if plan.get("status") != "planned_not_executed":
            raise RuntimeError("Unexecuted plan must retain its explicit status")
        if plan.get("execution_enabled") is not False or not missing_budgets:
            raise RuntimeError(
                "Plan must remain disabled while budget caps are pending"
            )
    else:
        if plan.get("status") != "approved_for_supervised_execution":
            raise RuntimeError(
                "Ready plan must record approved_for_supervised_execution"
            )
        if plan.get("execution_enabled") is not True or missing_budgets:
            raise RuntimeError(
                "Ready plan requires execution_enabled and nine budget caps"
            )
    return {
        "scenario_count": len(scenarios),
        "local_provider_count": len(local_providers),
        "directed_pair_count": len(directed_pairs),
        "edge_contract_count": len(covered_contracts),
        "cross_cloud_edge_contract_count": len(focused_contracts),
        "missing_budget_caps": missing_budgets,
        "required_state": required_state,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the bounded live-evaluation matrix without cloud calls."
    )
    parser.add_argument(
        "--require-state",
        choices=("planned", "ready"),
        default="planned",
        help="Require the checked non-executable or approved supervised state.",
    )
    arguments = parser.parse_args()
    result = validate(required_state=arguments.require_state)
    print(
        "live-evaluation-plan: OK "
        f"({result['scenario_count']} scenarios, "
        f"{result['directed_pair_count']} directed pairs, "
        f"{result['edge_contract_count']} edge contracts "
        f"({result['cross_cloud_edge_contract_count']} cross-cloud); "
        f"state={result['required_state']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
