#!/usr/bin/env python3
"""Build a bounded offline budget proposal for the nine Small scenarios.

The utility reads only the checked matrix, a digest-verified candidate pack,
the repository-pinned pricing snapshots, and the explicit PoC budget policy.
It imports no cloud SDK, invokes neither Terraform nor the Deployer, and never
enables live execution. Proposed caps remain pending operator approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.manage_live_evaluation_evidence import (
    PLAN_PATH,
    load_candidate_pack,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "docs/research/evaluation/small-scenario-budget-policy.json"
SCHEMA_PATH = (
    ROOT
    / "docs/research/evaluation/schemas"
    / "live-evaluation-budget-proposal.schema.json"
)
PRICING_ROOT = ROOT / "2-twin2clouds/json/pricing_catalog_baselines"
PROVIDERS = ("aws", "azure", "gcp")


class BudgetReviewError(RuntimeError):
    """Raised when the offline budget proposal is incomplete or inconsistent."""


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _decimal(value: object, *, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - Decimal exception types vary
        raise BudgetReviewError(f"{label} must be decimal") from exc
    if not result.is_finite() or result < 0:
        raise BudgetReviewError(f"{label} must be a finite non-negative decimal")
    return result


def _positive_integer(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BudgetReviewError(f"{label} must be a positive integer")
    return value


def _positive_decimal(value: object, *, label: str) -> Decimal:
    result = _decimal(value, label=label)
    if result <= 0:
        raise BudgetReviewError(f"{label} must be positive")
    return result


def _decimal_text(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.000001"))
    return format(rounded, "f")


def _validate_policy(policy: dict[str, Any], plan: dict[str, Any]) -> None:
    if policy.get("schema_version") != "six-layer-live-budget-policy.v1":
        raise BudgetReviewError("Unsupported budget policy version")
    if policy.get("status") != "offline_review_policy":
        raise BudgetReviewError("Budget policy must remain explicitly offline")
    if policy.get("architecture_profile") != plan.get("architecture_profile"):
        raise BudgetReviewError("Budget policy architecture profile drifted")
    if policy.get("currency") != "USD":
        raise BudgetReviewError("Budget policy must use USD")

    monthly_hours = _positive_integer(
        policy.get("monthly_hours"), label="monthly_hours"
    )
    if monthly_hours != 730:
        raise BudgetReviewError("Budget policy must retain 730 monthly hours")
    runtime = _positive_integer(
        policy.get("maximum_runtime_minutes"),
        label="maximum_runtime_minutes",
    )
    guardrails = plan.get("guardrails")
    if not isinstance(guardrails, dict) or runtime != guardrails.get(
        "maximum_runtime_minutes"
    ):
        raise BudgetReviewError("Budget policy runtime drifted from the matrix")

    _positive_integer(
        policy.get("variable_cost_headroom_multiplier"),
        label="variable_cost_headroom_multiplier",
    )
    _positive_decimal(policy.get("fixed_run_buffer_usd"), label="fixed_run_buffer_usd")
    _positive_decimal(
        policy.get("cap_rounding_increment_usd"),
        label="cap_rounding_increment_usd",
    )
    _positive_decimal(
        policy.get("maximum_individual_scenario_cap_usd"),
        label="maximum_individual_scenario_cap_usd",
    )
    _positive_decimal(
        policy.get("maximum_scenario_cap_portfolio_usd"),
        label="maximum_scenario_cap_portfolio_usd",
    )
    review_units = policy.get("billing_semantics_review_meter_units")
    if (
        not isinstance(review_units, list)
        or not review_units
        or any(not isinstance(item, str) or not item for item in review_units)
        or len(set(review_units)) != len(review_units)
    ):
        raise BudgetReviewError("Budget policy billing-review meter units are invalid")
    if policy.get("unverified_billing_semantics_action") != (
        "block_scenario_not_raise_cap"
    ):
        raise BudgetReviewError("Unverified billing semantics must block the scenario")

    timer = policy.get("external_timer")
    if not isinstance(timer, dict):
        raise BudgetReviewError("Budget policy requires an external timer")
    warning = _positive_integer(
        timer.get("warning_at_minutes"), label="warning_at_minutes"
    )
    destroy = _positive_integer(
        timer.get("destroy_trigger_at_minutes"),
        label="destroy_trigger_at_minutes",
    )
    deadline = _positive_integer(
        timer.get("cleanup_deadline_at_minutes"),
        label="cleanup_deadline_at_minutes",
    )
    if not warning < destroy < deadline == runtime:
        raise BudgetReviewError("External timer boundaries are inconsistent")
    if (
        timer.get("timer_owner") != "named_supervised_operator"
        or timer.get("timer_location") != "outside_the_deployment"
        or timer.get("start_before_terraform_plan") is not True
    ):
        raise BudgetReviewError("External timer ownership or start boundary drifted")

    scope = policy.get("scope")
    if (
        not isinstance(scope, dict)
        or scope.get("scenario_size") != "Small"
        or scope.get("scenario_count") != 9
        or scope.get("product_capability") is not False
        or scope.get("cloud_execution_authorized") is not False
    ):
        raise BudgetReviewError("Budget policy exceeds the bounded thesis PoC scope")


def _load_rate_cards(
    candidates: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    references: dict[str, dict[str, Any]] | None = None
    for scenario_id, candidate in candidates.items():
        pricing = candidate.get("pricing_catalogs")
        catalogs = pricing.get("catalogs") if isinstance(pricing, dict) else None
        if not isinstance(catalogs, dict):
            raise BudgetReviewError(f"{scenario_id}: pricing catalogs are missing")
        if references is None:
            references = catalogs
        elif catalogs != references:
            raise BudgetReviewError("Candidate pack mixes pricing catalog references")
    if references is None or set(references) != set(PROVIDERS):
        raise BudgetReviewError("Candidate pack must bind all three pricing catalogs")

    rate_cards: dict[str, dict[str, Any]] = {}
    for provider in PROVIDERS:
        reference = references[provider]
        snapshot_id = reference.get("snapshotId")
        content_digest = reference.get("contentDigest")
        if not isinstance(snapshot_id, str) or not isinstance(content_digest, str):
            raise BudgetReviewError(f"{provider}: invalid pricing reference")
        matches = list(PRICING_ROOT.glob(f"{provider}/*/snapshots/{snapshot_id}.json"))
        if len(matches) != 1:
            raise BudgetReviewError(
                f"{provider}: expected one pinned pricing snapshot, found {len(matches)}"
            )
        snapshot = _read(matches[0])
        snapshot_reference = snapshot.get("reference")
        if (
            not isinstance(snapshot_reference, dict)
            or snapshot_reference.get("snapshot_id") != snapshot_id
            or snapshot_reference.get("content_digest") != content_digest
        ):
            raise BudgetReviewError(f"{provider}: pricing snapshot binding drifted")
        pricing = snapshot.get("pricing")
        six_layer = pricing.get("sixLayer") if isinstance(pricing, dict) else None
        component_rates = (
            six_layer.get("componentRates") if isinstance(six_layer, dict) else None
        )
        if not isinstance(component_rates, dict):
            raise BudgetReviewError(f"{provider}: Six-layer rate card is missing")
        rate_cards[provider] = component_rates
    return rate_cards


def _meter_units(rate: dict[str, Any], *, component_id: str) -> set[str]:
    variants = rate.get("variants")
    if not isinstance(variants, list) or not variants:
        raise BudgetReviewError(f"{component_id}: pricing variants are missing")
    units: set[str] = set()
    for variant in variants:
        meters = variant.get("meters") if isinstance(variant, dict) else None
        if not isinstance(meters, list):
            raise BudgetReviewError(f"{component_id}: pricing meters are invalid")
        for meter in meters:
            unit = meter.get("unit") if isinstance(meter, dict) else None
            if not isinstance(unit, str) or not unit:
                raise BudgetReviewError(
                    f"{component_id}: pricing meter unit is invalid"
                )
            units.add(unit)
    return units


def _scenario_budget(
    *,
    scenario_id: str,
    candidate: dict[str, Any],
    plan_scenario: dict[str, Any],
    rate_cards: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    specification = candidate.get("resolved_deployment_specification")
    selections = (
        specification.get("component_selections")
        if isinstance(specification, dict)
        else None
    )
    if not isinstance(selections, list):
        raise BudgetReviewError(f"{scenario_id}: component selections are missing")
    providers_by_component: dict[str, str] = {}
    for selection in selections:
        if not isinstance(selection, dict):
            raise BudgetReviewError(f"{scenario_id}: component selection is invalid")
        component_id = selection.get("implementation_component_id")
        provider = selection.get("provider")
        if not isinstance(component_id, str) or provider not in PROVIDERS:
            raise BudgetReviewError(f"{scenario_id}: component provider is invalid")
        if component_id in providers_by_component:
            raise BudgetReviewError(f"{scenario_id}: duplicate component selection")
        providers_by_component[component_id] = provider

    ledger = candidate.get("cost_ledger")
    component_costs = (
        ledger.get("component_costs") if isinstance(ledger, dict) else None
    )
    route_costs = ledger.get("route_costs") if isinstance(ledger, dict) else None
    if not isinstance(component_costs, list) or not isinstance(route_costs, list):
        raise BudgetReviewError(f"{scenario_id}: cost ledger is incomplete")

    review_units = set(policy["billing_semantics_review_meter_units"])
    review_components: list[str] = []
    component_total = Decimal(0)
    for cost in component_costs:
        if not isinstance(cost, dict):
            raise BudgetReviewError(f"{scenario_id}: component cost is invalid")
        component_id = cost.get("component_id")
        if not isinstance(component_id, str):
            raise BudgetReviewError(f"{scenario_id}: component cost lacks an ID")
        provider = providers_by_component.get(component_id)
        if provider is None:
            raise BudgetReviewError(
                f"{scenario_id}: cost component is absent from the RDS"
            )
        rate = rate_cards[provider].get(component_id)
        if not isinstance(rate, dict):
            raise BudgetReviewError(
                f"{scenario_id}: {component_id} is absent from the pinned rate card"
            )
        amount = _decimal(
            cost.get("monthly_amount"),
            label=f"{scenario_id}:{component_id}:monthly_amount",
        )
        component_total += amount
        if amount > 0 and _meter_units(rate, component_id=component_id) & review_units:
            review_components.append(component_id)

    route_total = Decimal(0)
    for cost in route_costs:
        if not isinstance(cost, dict):
            raise BudgetReviewError(f"{scenario_id}: route cost is invalid")
        route_total += _decimal(
            cost.get("monthly_amount"),
            label=f"{scenario_id}:route:monthly_amount",
        )

    monthly_total = _decimal(
        candidate["cost_evaluation"].get("monthly_total"),
        label=f"{scenario_id}:monthly_total",
    )
    if component_total + route_total != monthly_total:
        raise BudgetReviewError(f"{scenario_id}: cost ledger total drifted")
    runtime_minutes = Decimal(policy["maximum_runtime_minutes"])
    monthly_minutes = Decimal(policy["monthly_hours"]) * Decimal(60)
    run_equivalent = monthly_total * runtime_minutes / monthly_minutes
    risk_adjusted = run_equivalent * Decimal(
        policy["variable_cost_headroom_multiplier"]
    )
    fixed_buffer = _decimal(
        policy["fixed_run_buffer_usd"], label="fixed_run_buffer_usd"
    )
    increment = _decimal(
        policy["cap_rounding_increment_usd"],
        label="cap_rounding_increment_usd",
    )
    unrounded_cap = risk_adjusted + fixed_buffer
    proposed_cap = (unrounded_cap / increment).to_integral_value(
        rounding=ROUND_CEILING
    ) * increment
    maximum_cap = _decimal(
        policy["maximum_individual_scenario_cap_usd"],
        label="maximum_individual_scenario_cap_usd",
    )
    if proposed_cap > maximum_cap:
        raise BudgetReviewError(
            f"{scenario_id}: calculated cap exceeds the PoC scenario maximum"
        )
    proposed_number: int | float = (
        int(proposed_cap)
        if proposed_cap == proposed_cap.to_integral_value()
        else float(proposed_cap)
    )

    return {
        "scenario_id": scenario_id,
        "candidate_evidence_digest": candidate["evidence_digest"],
        "estimated_monthly_total_usd": str(monthly_total),
        "estimated_60_minute_equivalent_usd": _decimal_text(run_equivalent),
        "risk_adjusted_60_minute_amount_usd": _decimal_text(risk_adjusted),
        "fixed_run_buffer_usd": _decimal_text(fixed_buffer),
        "proposed_budget_cap_usd": proposed_number,
        "matrix_budget_cap_usd": plan_scenario.get("budget_cap_usd"),
        "review_status": "pending_operator_approval",
        "billing_semantics_review_required": bool(review_components),
        "billing_semantics_review_components": sorted(review_components),
        "unverified_billing_semantics_action": "block_scenario_not_raise_cap",
    }


def _validate_schema(proposal: dict[str, Any]) -> None:
    schema = _read(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(proposal),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.absolute_path) or "$"
        raise BudgetReviewError(
            f"Budget proposal schema error at {location}: {first.message}"
        )


def build_proposal(
    candidate_pack_dir: Path,
    *,
    plan_path: Path = PLAN_PATH,
    policy_path: Path = POLICY_PATH,
) -> dict[str, Any]:
    """Return one schema- and digest-bound offline budget proposal."""

    plan, manifest, candidates, _ = load_candidate_pack(
        candidate_pack_dir,
        plan_path=plan_path,
    )
    if (
        plan.get("status") != "planned_not_executed"
        or plan.get("execution_enabled") is not False
        or any(item.get("budget_cap_usd") is not None for item in plan["scenarios"])
    ):
        raise BudgetReviewError(
            "Budget proposals require the disabled plan with nine pending caps"
        )
    policy = _read(policy_path)
    _validate_policy(policy, plan)
    rate_cards = _load_rate_cards(candidates)
    scenarios_by_id = {item["scenario_id"]: item for item in plan["scenarios"]}
    scenario_proposals = [
        _scenario_budget(
            scenario_id=scenario_id,
            candidate=candidates[scenario_id],
            plan_scenario=scenarios_by_id[scenario_id],
            rate_cards=rate_cards,
            policy=policy,
        )
        for scenario_id in scenarios_by_id
    ]
    scenario_cap_total = sum(
        (Decimal(str(item["proposed_budget_cap_usd"])) for item in scenario_proposals),
        start=Decimal(0),
    )
    portfolio_maximum = _decimal(
        policy["maximum_scenario_cap_portfolio_usd"],
        label="maximum_scenario_cap_portfolio_usd",
    )
    if scenario_cap_total > portfolio_maximum:
        raise BudgetReviewError("Scenario cap portfolio exceeds the PoC maximum")
    proposal = {
        "schema_version": "six-layer-live-budget-proposal.v1",
        "status": "offline_complete_pending_operator_approval",
        "architecture_profile": plan["architecture_profile"],
        "currency": policy["currency"],
        "plan_digest": manifest["plan_digest"],
        "candidate_pack_manifest_digest": manifest["manifest_digest"],
        "budget_policy_digest": _digest(policy),
        "execution_enabled": False,
        "maximum_runtime_minutes": policy["maximum_runtime_minutes"],
        "external_timer": dict(policy["external_timer"]),
        "maximum_individual_scenario_cap_usd": policy[
            "maximum_individual_scenario_cap_usd"
        ],
        "maximum_scenario_cap_portfolio_usd": policy[
            "maximum_scenario_cap_portfolio_usd"
        ],
        "proposed_scenario_cap_total_usd": _decimal_text(scenario_cap_total),
        "scenario_count": len(candidates),
        "scenarios": scenario_proposals,
    }
    proposal["proposal_digest"] = _digest(proposal)
    _validate_schema(proposal)
    return proposal


def write_proposal(
    candidate_pack_dir: Path,
    output: Path,
    *,
    plan_path: Path = PLAN_PATH,
    policy_path: Path = POLICY_PATH,
) -> dict[str, Any]:
    """Write one non-overwriting budget proposal and return it."""

    if output.exists():
        raise FileExistsError(f"Budget proposal already exists: {output}")
    proposal = build_proposal(
        candidate_pack_dir,
        plan_path=plan_path,
        policy_path=policy_path,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(proposal, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return proposal


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a non-executable budget proposal from an offline candidate pack."
        )
    )
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    arguments = parser.parse_args()
    proposal = write_proposal(
        arguments.candidate_pack,
        arguments.output,
        policy_path=arguments.policy,
    )
    print(
        "live-evaluation-budget-proposal: "
        f"{proposal['scenario_count']} scenarios -> {arguments.output} "
        f"({proposal['proposal_digest']}); execution remains disabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
