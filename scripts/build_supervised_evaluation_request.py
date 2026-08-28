#!/usr/bin/env python3
"""Build, but never send, one supervised evaluation-run request.

The utility validates the approved matrix and its digest-bound candidate pack,
then creates the explicit Management request used to materialize that exact
Small candidate. It performs no HTTP or provider call and refuses overwrite.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    from scripts.manage_live_evaluation_evidence import load_candidate_pack
    from scripts.validate_live_evaluation_plan import validate
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from manage_live_evaluation_evidence import load_candidate_pack
    from validate_live_evaluation_plan import validate

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs/research/evaluation/small-scenario-matrix.json"
CONFIRMATION = "MATERIALIZE SUPERVISED EVALUATION CANDIDATE"


class SupervisedEvaluationRequestError(RuntimeError):
    """Raised when the operator handoff is incomplete or inconsistent."""


def build_request(
    candidate_pack_dir: Path,
    scenario_id: str,
    *,
    plan_path: Path = PLAN_PATH,
) -> dict[str, Any]:
    """Return the exact disabled-by-default Management request body."""

    validate(required_state="ready", plan_path=plan_path)
    plan, manifest, candidates, _regions = load_candidate_pack(
        candidate_pack_dir,
        plan_path=plan_path,
    )
    candidate = candidates.get(scenario_id)
    if candidate is None:
        raise SupervisedEvaluationRequestError(
            f"Candidate pack does not contain scenario: {scenario_id}"
        )
    workload_path = ROOT / str(plan["workload_fixture"])
    try:
        workload = json.loads(workload_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupervisedEvaluationRequestError(
            "The immutable Small workload is unavailable"
        ) from exc
    if not isinstance(workload, dict) or workload.get("eventingScenarioId") != (
        "eventing-small-v1"
    ):
        raise SupervisedEvaluationRequestError(
            "Supervised evaluation requires the immutable Small workload"
        )
    return {
        "params": workload,
        "scenario_id": scenario_id,
        "candidate_id": candidate["candidate_id"],
        "candidate_evidence_digest": candidate["evidence_digest"],
        "plan_digest": manifest["plan_digest"],
        "candidate_pack_manifest_digest": manifest["manifest_digest"],
        "confirmation": CONFIRMATION,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build one offline supervised evaluation-run request."
    )
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.output.exists():
        raise SupervisedEvaluationRequestError(
            f"Request output already exists: {arguments.output}"
        )
    request = build_request(arguments.candidate_pack, arguments.scenario_id)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "supervised-evaluation-request: "
        f"{arguments.scenario_id} -> {arguments.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
