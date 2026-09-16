"""Offline Small Core research inputs; no credentials, cloud calls or execution.

This intentionally does not emit a deployment_manifest.json or change full-profile
readiness. Inputs still need reviewed runtime artifacts, real account bindings,
an exact resource/cost/time/cleanup plan and explicit live authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "2-twin2clouds"))
sys.path.insert(0, str(ROOT / "3-cloud-deployer"))

from backend.architecture_profiles.six_layer_workload import resolve_six_layer_workload  # noqa: E402
from backend.deployment_specification.six_layer_builder import (  # noqa: E402
    small_core_evaluation_dimensions,
)
from src.providers.terraform.cross_cloud_routes import core_evaluation_routes  # noqa: E402

PROVIDERS = ("aws", "azure", "gcp")
SCENARIOS = {
    (
        f"core-small-local-{source}"
        if source == target
        else f"core-small-{source}-to-{target}"
    ): (source, target)
    for source in PROVIDERS
    for target in PROVIDERS
}
WORKLOAD_PATH = ROOT / "contracts/six-layer-workload/v1/fixtures/valid/core-small.json"


def materialize(scenario_id: str) -> dict:
    source, target = SCENARIOS[scenario_id]
    assignment = {
        f"component.{logical}": source if logical == "ingestion" else target
        for logical in (
            "ingestion",
            "eventing",
            "processing",
            "hot-storage",
            "cool-storage",
            "archive-storage",
        )
    }
    workload = resolve_six_layer_workload(json.loads(WORKLOAD_PATH.read_text()))
    dimensions = small_core_evaluation_dimensions(assignment, workload)

    def tf_provider(value: str) -> str:
        return "google" if value == "gcp" else value

    values = {
        "digital_twin_name": scenario_id,
        "architecture_profile_id": "six-layer-eventing",
        "architecture_profile_version": "1",
        "evaluation_scope": "core",
        "layer_1_provider": tf_provider(source),
        "layer_2_provider": tf_provider(target),
        "layer_3_hot_provider": tf_provider(target),
        "layer_3_cold_provider": tf_provider(target),
        "layer_3_archive_provider": tf_provider(target),
        "event_layer_provider": tf_provider(target),
        "layer_4_provider": "",
        "layer_5_provider": "",
        "aws_region": "eu-central-1",
        "azure_region": "westeurope",
        "gcp_region": "europe-west1",
        "layer_3_hot_to_cold_interval_days": 30,
        "layer_3_cold_to_archive_interval_days": 90,
        "layer_3_archive_expiry_interval_days": 365,
        "resolved_component_dimensions": dimensions,
        "resolved_cross_cloud_routes": core_evaluation_routes(source, target),
    }
    if target == "aws":
        values["aws_event_kinesis_shards"] = int(
            dimensions["dimension.aws.aws.kinesis-data-streams.shards_per_stream"]
        )
    # Each directed scenario also returns commands. Both identity directions
    # must be reviewed, even though the scenario is named by telemetry direction.
    identity_pairs = sorted(
        {
            (route["source_provider"], route["destination_provider"])
            for route in values["resolved_cross_cloud_routes"]
        }
    )
    payload = {
        "schema_version": "core-evaluation-inputs.v1",
        "scenario_id": scenario_id,
        "status": "offline_inputs_not_authorized",
        "execution_enabled": False,
        "full_architecture_evidence": False,
        "excluded_layers": ["L4", "L5"],
        "source_refs": {
            "workload_sha256": hashlib.sha256(WORKLOAD_PATH.read_bytes()).hexdigest(),
            "capacity_registry_digest": json.loads(
                (
                    ROOT
                    / "contracts/resolved-deployment-specification/v2/component-capacity-registry.json"
                ).read_text()
            )["content_digest"],
            "component_catalog_digest": json.loads(
                (
                    ROOT
                    / "contracts/architecture-profiles/definitions/component-catalogs/six-layer-eventing/1/catalog.json"
                ).read_text()
            )["content_digest"],
        },
        "assignments": assignment,
        "identity_pairs": [list(pair) for pair in identity_pairs],
        "budget_cap_usd": None,
        "maximum_runtime_minutes": None,
        "remaining_gates": [
            "review-runtime-packages-and-real-image-digests",
            "review-account-scope-and-read-only-prerequisites",
            "review-exact-plan-cost-cap-time-limit-and-cleanup",
            "explicit-live-approval",
        ],
        "tfvars": values,
    }
    payload["content_digest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payloads = [
        materialize(name) for name in ([args.scenario] if args.scenario else SCENARIOS)
    ]
    # Refuse reuse rather than overwrite previous evidence or mix scenarios.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for payload in payloads:
        name = payload["scenario_id"]
        (args.output_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2) + "\n"
        )
        (args.output_dir / f"{name}.tfvars.json").write_text(
            json.dumps(payload["tfvars"], indent=2) + "\n"
        )
    print(
        f"Prepared {len(payloads)} Core scenarios offline; execution remains disabled."
    )


if __name__ == "__main__":
    main()
