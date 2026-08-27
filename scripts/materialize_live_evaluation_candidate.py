"""Materialize one planned Six-layer candidate without calling a cloud API.

This research utility uses the repository-pinned pricing baseline and the
Optimizer's internal evaluation selector. It does not expose provider
overrides through the application and it never invokes the Deployer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER_ROOT = ROOT / "2-twin2clouds"
if str(OPTIMIZER_ROOT) not in sys.path:
    sys.path.insert(0, str(OPTIMIZER_ROOT))

from backend.architecture_profiles.candidate_factory import (
    SIX_LAYER_COMPONENTS,
)
from backend.architecture_profiles.registry import (
    ArchitectureProfileRegistry,
)
from backend.architecture_profiles.six_layer_optimizer import (
    optimize_six_layer_eventing_v1,
)
from backend.pricing_catalog_models import PricingCatalogContext
from backend.pricing_catalog_repository import (
    get_pricing_catalog_repository,
)
from backend.pricing_catalog_resolver import PricingCatalogResolver

PLAN_PATH = ROOT / "docs/research/evaluation/small-scenario-matrix.json"
ARTIFACT_PATH = (
    ROOT / "contracts/user-function-extension/v1/examples/valid-artifact.json"
)
PROVIDER_ORDER = ("aws", "azure", "gcp")


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


def candidate_id_for(assignments: Mapping[str, str]) -> str:
    """Return the Optimizer's canonical provider-only candidate identity."""

    return "|".join(
        assignments[logical_component_id]
        for _, _, logical_component_id in SIX_LAYER_COMPONENTS
    )


def _extension_binding() -> dict[str, str]:
    artifact = _read(ARTIFACT_PATH)
    return {
        "slotId": str(artifact["slot_id"]),
        "slotVersion": str(artifact["slot_version"]),
        "artifactId": str(artifact["artifact_id"]),
        "artifactDigest": str(artifact["artifact_digest"]),
        "configurationDigest": _digest(artifact["configuration"]),
    }


def _scenario(plan: Mapping[str, Any], scenario_id: str) -> Mapping[str, Any]:
    scenario = next(
        (
            item
            for item in plan.get("scenarios", [])
            if item.get("scenario_id") == scenario_id
        ),
        None,
    )
    if scenario is None:
        raise ValueError(f"Unknown evaluation scenario: {scenario_id}")
    return scenario


def materialize(scenario_id: str) -> dict[str, Any]:
    """Cost and materialize one exact, admissible planned candidate offline."""

    plan = _read(PLAN_PATH)
    scenario = _scenario(plan, scenario_id)
    assignments = scenario["assignments"]
    if not isinstance(assignments, dict):
        raise TypeError(f"{scenario_id}: assignments must be an object")
    candidate_id = candidate_id_for(assignments)
    providers = tuple(
        provider for provider in PROVIDER_ORDER if provider in assignments.values()
    )

    workload_path = ROOT / str(plan["workload_fixture"])
    workload = _read(workload_path)
    registry = ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    repository = get_pricing_catalog_repository()
    context = PricingCatalogContext(
        catalogs={
            provider: repository.resolve_baseline(
                provider,
                require_fresh=False,
            ).reference
            for provider in PROVIDER_ORDER
        }
    )
    resolved_catalogs = PricingCatalogResolver(repository).resolve_context(
        context,
        require_fresh=False,
    )
    references = {
        provider: {
            "id": reference.snapshot_id,
            "version": "1",
            "digest": reference.content_digest,
            "provider": provider,
            "currency": str(workload.get("currency", "USD")),
        }
        for provider, reference in resolved_catalogs.context.catalogs.items()
    }
    result = optimize_six_layer_eventing_v1(
        calculation_run_id=str(
            uuid5(NAMESPACE_URL, f"twin2multicloud-evaluation:{scenario_id}")
        ),
        architecture_profile={
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        extension_bindings=[_extension_binding()],
        workload=workload,
        pricing_evidence_refs=references,
        pricing_by_provider=resolved_catalogs.detached_pricing(),
        providers=providers,
        registry=registry,
        evaluation_candidate_id=candidate_id,
    )
    if result.selection_kind != "evaluation_candidate":
        raise RuntimeError("Optimizer did not retain the evaluation boundary")

    evidence = {
        "schema_version": "six-layer-evaluation-candidate.v1",
        "evidence_status": "offline_planned_candidate",
        "scenario_id": scenario_id,
        "candidate_id": result.selected_candidate_id,
        "assignments": dict(assignments),
        "plan_digest": _digest(plan),
        "workload_digest": _digest(workload),
        "pricing_catalogs": resolved_catalogs.context.to_http_dict(),
        "cost_evaluation": {
            "currency": result.cost_evaluation.currency,
            "monthly_total": str(result.cost_evaluation.monthly_total),
            "component_totals": {
                key: str(value)
                for key, value in result.cost_evaluation.component_totals.items()
            },
            "edge_totals": {
                key: str(value)
                for key, value in result.cost_evaluation.edge_totals.items()
            },
            "component_owner_totals": {
                key: str(value)
                for key, value in result.cost_evaluation.component_owner_totals.items()
            },
            "route_owner_totals": {
                key: str(value)
                for key, value in result.cost_evaluation.route_owner_totals.items()
            },
        },
        "cost_ledger": dict(result.cost_ledger),
        "resolved_twin_architecture": dict(result.resolved_architecture),
        "resolved_deployment_specification": dict(result.deployment_specification),
        "optimizer_diagnostics": {
            "enumerated_candidate_count": result.enumerated_candidate_count,
            "admissible_candidate_count": result.costed_candidate_count,
            "rejected_by_error_code": dict(result.rejected_by_error_code),
        },
    }
    evidence["evidence_digest"] = _digest(evidence)
    return evidence


def materialize_plan(output_dir: Path) -> dict[str, Any]:
    """Materialize the complete checked matrix into one immutable handoff pack."""

    if output_dir.exists():
        raise FileExistsError(
            f"Evaluation output directory already exists: {output_dir}"
        )
    output_dir.mkdir(parents=True)
    plan = _read(PLAN_PATH)
    candidates: list[dict[str, str]] = []
    for scenario in plan["scenarios"]:
        scenario_id = str(scenario["scenario_id"])
        evidence = materialize(scenario_id)
        filename = f"{scenario_id}.candidate.json"
        (output_dir / filename).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        candidates.append(
            {
                "scenario_id": scenario_id,
                "candidate_id": str(evidence["candidate_id"]),
                "candidate_file": filename,
                "candidate_evidence_digest": str(evidence["evidence_digest"]),
                "currency": str(evidence["cost_evaluation"]["currency"]),
                "monthly_total": str(evidence["cost_evaluation"]["monthly_total"]),
            }
        )
    manifest = {
        "schema_version": "six-layer-evaluation-candidate-pack.v1",
        "evidence_status": "offline_planned_candidates",
        "plan_digest": _digest(plan),
        "scenario_count": len(candidates),
        "candidates": candidates,
    }
    manifest["manifest_digest"] = _digest(manifest)
    (output_dir / "candidate-pack-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize exact planned evaluation candidates offline."
    )
    parser.add_argument("scenario_id", nargs="?")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_scenarios",
        help="Materialize all nine checked scenarios into a new directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Single-scenario JSON output path; stdout is used when omitted.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Required new output directory for --all.",
    )
    arguments = parser.parse_args()
    if arguments.all_scenarios:
        if arguments.scenario_id is not None or arguments.output is not None:
            parser.error("--all cannot be combined with scenario_id or --output")
        if arguments.output_dir is None:
            parser.error("--all requires --output-dir")
        manifest = materialize_plan(arguments.output_dir)
        print(
            "evaluation-candidate-pack: "
            f"{manifest['scenario_count']} scenarios -> {arguments.output_dir} "
            f"({manifest['manifest_digest']})"
        )
        return 0
    if arguments.scenario_id is None:
        parser.error("scenario_id is required unless --all is used")
    if arguments.output_dir is not None:
        parser.error("--output-dir is valid only with --all")
    evidence = materialize(arguments.scenario_id)
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
        print(
            f"evaluation-candidate: {evidence['scenario_id']} -> "
            f"{arguments.output} ({evidence['evidence_digest']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
