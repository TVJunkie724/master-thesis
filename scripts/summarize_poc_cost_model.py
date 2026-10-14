"""Offline closeout comparison; no cloud clients, deployment or pricing refresh."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal

import materialize_live_evaluation_candidate as candidates
from backend.architecture_profiles.diagnostics import ArchitectureResolutionError

OUTPUT = candidates.ROOT / "docs/research/evaluation/poc-cost-model-results.json"


def calculate() -> dict:
    plan = candidates._read(candidates.PLAN_PATH)
    base = candidates._read(candidates.ROOT / plan["workload_fixture"])
    variants = {
        size: candidates._read(
            candidates.ROOT / f"contracts/six-layer-workload/v1/fixtures/valid/core-{size}.json"
        ) for size in ("small", "medium", "large")
    }
    rows = []
    pricing = None
    for variant, workload in variants.items():
        for scenario in plan["scenarios"]:
            try:
                evidence = candidates.materialize(
                    scenario["scenario_id"], workload_override=workload
                )
            except ArchitectureResolutionError as exc:
                if exc.code != "ARCH_NO_ADMISSIBLE_CANDIDATE":
                    raise
                rows.append({
                    "variant": variant,
                    "scenario_id": scenario["scenario_id"],
                    "assignments": scenario["assignments"],
                    "workload_digest": candidates._digest(workload),
                    "status": "excluded",
                    "error_code": exc.code,
                    "monthly_total": None,
                })
                continue
            if pricing is None:
                pricing = evidence["pricing_catalogs"]
            assert pricing == evidence["pricing_catalogs"]
            rows.append({
                "variant": variant,
                "status": "costed",
                "changed_inputs": {k: v for k, v in workload.items() if base.get(k) != v},
                "scenario_id": scenario["scenario_id"],
                "assignments": evidence["assignments"],
                "workload_digest": evidence["workload_digest"],
                "candidate_evidence_digest": evidence["evidence_digest"],
                **evidence["cost_evaluation"],
            })
    rankings = {}
    for variant in variants:
        subset = [row for row in rows if row["variant"] == variant and row["status"] == "costed"]
        rankings[variant] = [
            row["scenario_id"] for row in sorted(
                subset, key=lambda row: (Decimal(row["monthly_total"]), row["scenario_id"])
            )
        ]
    result = {
        "schema_version": "poc-cost-model-summary.v1",
        "evidence_status": "offline_modeled_not_billed_or_live",
        "method": "Frozen baseline; eight planned placements across the three immutable Small/Medium/Large workload contracts.",
        "limitations": [
            "Rankings cover these eight candidates, not the unrestricted global optimum.",
            "GCP-local complete profile excluded by L4/L5 scope; never priced as free missing functionality.",
            "Discrete workload-scale sensitivity changes multiple contract inputs together; no single-variable causal attribution.",
            "Medium/Large are offline models only, not live capacity or deployment qualification.",
            "Excluded candidates have no cost or rank; missing functionality is never valued at zero.",
            "Neither actual experiment cost nor causal Event-Layer savings nor paired live FiveLayer comparison.",
        ],
        "plan_digest": candidates._digest(plan),
        "base_workload": base,
        "pricing_catalogs": pricing,
        "rankings": rankings,
        "results": rows,
    }
    result["result_digest"] = candidates._digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(calculate(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != rendered:
            raise SystemExit("Cost summary differs from the frozen calculation")
        print("Verified 24 byte-identical offline candidate/sensitivity results")
    else:
        OUTPUT.write_text(rendered)
        print("Wrote 24 offline candidate/sensitivity results; no cloud calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
