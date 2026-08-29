#!/usr/bin/env python3
"""Verify the bounded, non-executable Phase 8 federation-probe plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
DEPLOYER_ROOT = ROOT / "3-cloud-deployer"
if str(DEPLOYER_ROOT) not in sys.path:
    sys.path.insert(0, str(DEPLOYER_ROOT))

from src.architecture_profiles.requirements import IDENTITY_EXCHANGE_BY_PAIR  # noqa: E402


DEFAULT_PLAN = (
    ROOT / "docs/research/evaluation/directed-federation-probe-plan.json"
)
DEFAULT_SCHEMA = (
    ROOT
    / "docs/research/evaluation/schemas/"
    "live-evaluation-federation-probe-plan.schema.json"
)
MATRIX_PATH = ROOT / "docs/research/evaluation/small-scenario-matrix.json"
IMAGE_READINESS_PATH = (
    ROOT / "docs/research/evaluation/small-runtime-image-readiness.json"
)
AZURE_RUNNER_IMAGE = (
    "mcr.microsoft.com/azure-cli@"
    "sha256:b23e5168ce9654b1385c565a2c6cf60695f7b0d03056f7a0fafdc7c59a084512"
)
ALLOWED_PROBE_RESOURCE_TYPES = {
    "aws.iam_inline_policy",
    "aws.iam_oidc_provider",
    "aws.iam_role",
    "azure.container_instance_group",
    "azure.entra_app_role_assignment",
    "azure.entra_application",
    "azure.entra_application_role",
    "azure.entra_identifier_uri",
    "azure.entra_service_principal",
    "azure.federated_identity_credential",
    "azure.resource_group",
    "azure.role_assignment",
    "azure.user_assigned_managed_identity",
    "gcp.service_account",
    "gcp.service_account_iam_binding",
    "gcp.workload_identity_pool",
    "gcp.workload_identity_pool_provider",
}
GCP_SOFT_DELETE_TYPES = {
    "gcp.service_account",
    "gcp.workload_identity_pool",
    "gcp.workload_identity_pool_provider",
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _directed_matrix_routes() -> dict[tuple[str, str], str]:
    matrix = _load(MATRIX_PATH)
    routes: dict[tuple[str, str], str] = {}
    for scenario in matrix["scenarios"]:
        focus = scenario.get("focus", {})
        source = focus.get("source_provider")
        destination = focus.get("destination_provider")
        if not source or not destination:
            continue
        pair = (str(source), str(destination))
        if pair in routes:
            raise ValueError(f"duplicate directed matrix route: {pair}")
        routes[pair] = str(scenario["scenario_id"])
    return routes


def _verify_runner_and_cost(probe: dict[str, Any]) -> None:
    source = probe["source_provider"]
    runner = probe["runner"]
    direct_charge_resources = [
        resource for resource in probe["resources"] if resource["direct_charge"]
    ]
    expected = Decimal(probe["expected_direct_cost_usd"])
    cap = Decimal(probe["direct_cost_cap_usd"])
    if expected > cap:
        raise ValueError(f"expected cost exceeds cap for {probe['probe_id']}")

    if source == "azure":
        if runner != {
            "location": "azure_container_instance",
            "image_reference": AZURE_RUNNER_IMAGE,
            "vcpu": 1,
            "memory_gib": 1,
            "maximum_billable_runtime_seconds": 300,
            "network_ingress_exposed": False,
        }:
            raise ValueError(f"Azure source runner is not exactly bounded: {probe['probe_id']}")
        if [item["type"] for item in direct_charge_resources] != [
            "azure.container_instance_group"
        ]:
            raise ValueError(f"Azure source must bill only its bounded runner: {probe['probe_id']}")
        if cap != Decimal("0.010000"):
            raise ValueError(f"Azure source cap changed: {probe['probe_id']}")
    else:
        if runner != {
            "location": "local_supervised_process",
            "image_reference": None,
            "vcpu": None,
            "memory_gib": None,
            "maximum_billable_runtime_seconds": 0,
            "network_ingress_exposed": False,
        }:
            raise ValueError(f"non-Azure source must remain local: {probe['probe_id']}")
        if direct_charge_resources or expected != 0 or cap != 0:
            raise ValueError(f"local probe must have zero direct charge: {probe['probe_id']}")


def verify(plan_path: Path, schema_path: Path) -> dict[str, Any]:
    plan = _load(plan_path)
    schema = _load(schema_path)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(plan)

    payload = {key: value for key, value in plan.items() if key != "record_digest"}
    expected_digest = _digest(payload)
    if plan["record_digest"] != expected_digest:
        raise ValueError(
            "federation-probe plan digest mismatch: "
            f"expected {expected_digest}, got {plan['record_digest']}"
        )

    for relative_path in plan["planning_basis"]:
        if not (ROOT / relative_path).is_file():
            raise ValueError(f"planning basis does not exist: {relative_path}")

    image_readiness = _load(IMAGE_READINESS_PATH)
    if (
        plan["candidate_pack_manifest_digest"]
        != image_readiness["candidate_pack_manifest_digest"]
    ):
        raise ValueError("probe plan is not bound to the current candidate pack")

    expected_routes = _directed_matrix_routes()
    actual_routes: dict[tuple[str, str], str] = {}
    for probe in plan["probes"]:
        pair = (probe["source_provider"], probe["destination_provider"])
        if pair in actual_routes:
            raise ValueError(f"duplicate federation probe route: {pair}")
        actual_routes[pair] = probe["scenario_id"]
        if pair[0] == pair[1]:
            raise ValueError(f"federation probe route is not directed: {pair}")
        if probe["probe_id"] != f"federation-{pair[0]}-to-{pair[1]}":
            raise ValueError(f"probe ID does not match route: {probe['probe_id']}")
        if probe["name_prefix"] != f"t2mc-p8-{pair[0]}-{pair[1]}-":
            raise ValueError(f"name prefix does not match route: {probe['probe_id']}")
        if probe["exchange_contract"] != IDENTITY_EXCHANGE_BY_PAIR[pair]:
            raise ValueError(f"exchange contract drift: {probe['probe_id']}")
        resource_types = [resource["type"] for resource in probe["resources"]]
        if len(resource_types) != len(set(resource_types)):
            raise ValueError(f"duplicate resource type: {probe['probe_id']}")
        unexpected = set(resource_types) - ALLOWED_PROBE_RESOURCE_TYPES
        if unexpected:
            raise ValueError(
                f"non-identity probe resource added to {probe['probe_id']}: {sorted(unexpected)}"
            )
        if {resource["provider"] for resource in probe["resources"]} != set(pair):
            raise ValueError(f"probe resources escape the directed pair: {probe['probe_id']}")
        expected_tombstones = sorted(set(resource_types) & GCP_SOFT_DELETE_TYPES)
        if sorted(probe["expected_soft_delete_tombstones"]) != expected_tombstones:
            raise ValueError(f"GCP soft-delete ledger drift: {probe['probe_id']}")
        _verify_runner_and_cost(probe)

    if actual_routes != expected_routes:
        raise ValueError(
            f"directed route coverage drift: expected {expected_routes}, got {actual_routes}"
        )

    aggregate = sum(
        (Decimal(probe["direct_cost_cap_usd"]) for probe in plan["probes"]),
        Decimal(0),
    )
    declared = Decimal(plan["common_guardrails"]["aggregate_direct_cost_cap_usd"])
    summary = Decimal(plan["summary"]["aggregate_direct_cost_cap_usd"])
    if aggregate != declared or aggregate != summary or aggregate != Decimal("0.020000"):
        raise ValueError("aggregate direct-cost cap drift")

    cost_basis = plan["cost_basis"]
    calculated = (
        Decimal(cost_basis["azure_container_instance_vcpu_hour_usd"])
        + Decimal(cost_basis["azure_container_instance_gib_hour_usd"])
    ) * Decimal(300) / Decimal(3600)
    calculated = calculated.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    if calculated != Decimal(
        cost_basis["azure_source_runner_cost_for_maximum_runtime_usd"]
    ):
        raise ValueError("Azure source-runner cost calculation drift")

    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    plan = verify(args.plan.resolve(), args.schema.resolve())
    print(
        "Directed federation-probe plan verified "
        f"({plan['record_digest']}); execution remains disabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
