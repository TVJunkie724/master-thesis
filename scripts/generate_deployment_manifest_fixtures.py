#!/usr/bin/env python3
"""Generate Manifest v3 fixtures from the real Phase 8.5 optimizer resolver."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER_ROOT = ROOT / "2-twin2clouds"
FIXTURE_ROOT = (
    ROOT / "contracts" / "deployment-manifest" / "v3" / "fixtures" / "valid"
)
CATALOG_PATH = (
    ROOT
    / "contracts"
    / "architecture-profiles"
    / "definitions"
    / "component-catalogs"
    / "baseline"
    / "1"
    / "catalog.json"
)
LOGICAL_TO_PROVIDER_KEY = {
    "component.ingestion": "layer_1_provider",
    "component.processing": "layer_2_provider",
    "component.hot-storage": "layer_3_hot_provider",
    "component.cool-storage": "layer_3_cold_provider",
    "component.archive-storage": "layer_3_archive_provider",
    "component.twin-state": "layer_4_provider",
    "component.visualization": "layer_5_provider",
}
def _scale_price_fields(node: dict, factor: int) -> None:
    for key, value in node.items():
        if isinstance(value, dict):
            _scale_price_fields(value, factor)
        elif (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and "price" in key.lower()
        ):
            node[key] = (value if value > 0 else 1) * factor


def _optimizer_inputs(scenario: str) -> tuple[dict, dict]:
    from tests.unit.calculation_v2.test_engine import TestEngineIntegration

    fixture_owner = TestEngineIntegration()
    params = copy.deepcopy(
        fixture_owner.sample_params.__wrapped__(fixture_owner)
    )
    pricing = copy.deepcopy(
        fixture_owner.sample_pricing.__wrapped__(fixture_owner)
    )
    # TwinMaker's account-plan observation is deliberately freshness-gated.
    # The generated graph does not persist this observation timestamp, so use
    # execution time instead of letting a checked-in date age AWS L4 out.
    params["providerPricingContexts"]["awsTwinMaker"]["observedAt"] = (
        datetime.now(timezone.utc).isoformat()
    )
    _scale_price_fields(pricing["gcp"], 1_000_000)
    if scenario == "all-aws":
        _scale_price_fields(pricing["azure"], 1_000_000)
    elif scenario == "all-azure":
        _scale_price_fields(pricing["aws"], 1_000_000)
    elif scenario == "mixed":
        _scale_price_fields(pricing["azure"]["iotHub"], 1_000_000)
        for service, values in pricing["aws"].items():
            if service not in {"iotCore", "transfer"} and isinstance(values, dict):
                _scale_price_fields(values, 1_000_000)
        pricing["aws"]["iotCore"]["pricePerDeviceAndMonth"] = 0
        pricing["aws"]["iotCore"]["priceRulesTriggered"] = 0
    else:
        raise ValueError(f"unknown deployment-manifest fixture scenario: {scenario}")
    return params, pricing


def _resolved_result(scenario: str) -> dict:
    from backend.calculation_v2.engine import calculate_cheapest_costs
    from backend.architecture_profiles.registry import (
        ArchitectureProfileRegistry,
    )
    from backend.architecture_profiles.strategy import (
        build_resolution_context,
    )
    from tests.unit.pricing.transfer_fixtures import (
        pricing_catalog_context_for,
    )

    params, pricing = _optimizer_inputs(scenario)
    registry = ArchitectureProfileRegistry()
    context = build_resolution_context(
        registry=registry,
        calculation_run_id=params["calculationRunId"],
        architecture_profile={
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        extension_bindings=[
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
    ).with_execution_inputs(
        layer_options={
            layer: (("AWS", 1.0), ("Azure", 1.0))
            for layer in (
                "L1",
                "L2",
                "L3_hot",
                "L3_cool",
                "L3_archive",
                "L4",
                "L5",
            )
        },
        provider_regions={
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1",
        },
    )
    return calculate_cheapest_costs(
        params,
        pricing,
        pricing_catalog_context=pricing_catalog_context_for(pricing),
        architecture_context=context,
    )


def _manifest(scenario: str, filename: str) -> dict:
    existing = json.loads((FIXTURE_ROOT / filename).read_text("utf-8"))
    result = _resolved_result(scenario)
    architecture = result["resolvedTwinArchitecture"]
    specification = result["resolvedDeploymentSpecification"]
    providers = {
        LOGICAL_TO_PROVIDER_KEY[item["logical_component_id"]]: (
            "google" if item["provider"] == "gcp" else item["provider"]
        )
        for item in architecture["component_assignments"]
    }
    credential_providers = sorted(
        {
            item["provider"]
            for item in architecture["component_assignments"]
        }
    )
    catalog = json.loads(CATALOG_PATH.read_text("utf-8"))
    existing.update(
        {
            "calculation_run_id": architecture["calculation_run_id"],
            "providers": providers,
            "resolved_twin_architecture": architecture,
            "resolved_twin_architecture_digest": architecture[
                "content_digest"
            ],
            "resolved_deployment_specification": specification,
            "resolved_deployment_specification_digest": specification[
                "digest"
            ],
            "credentials": {
                "providers": credential_providers,
                "sources": {
                    provider: "cloud_connection"
                    for provider in credential_providers
                },
                "contains_secret_payloads": False,
            },
            "compatibility": {
                "component_catalog_ref": {
                    "id": catalog["catalog_id"],
                    "version": catalog["catalog_version"],
                    "digest": catalog["content_digest"],
                },
                "graph_resolver_version": "resolved-deployment-graph.v1",
                "package_builder_version": "graph-package-builder.v1",
                "terraform_input_contract_version": (
                    "graph-terraform-inputs.v1"
                ),
            },
        }
    )
    return existing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed fixtures differ from resolver output.",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(OPTIMIZER_ROOT))
    local_tests = ModuleType("tests")
    local_tests.__path__ = [str(OPTIMIZER_ROOT / "tests")]
    sys.modules["tests"] = local_tests
    try:
        fixtures = {
            "all-aws.json": _manifest("all-aws", "all-aws.json"),
            "all-azure.json": _manifest(
                "all-azure",
                "all-azure.json",
            ),
            "mixed-providers.json": _manifest(
                "mixed",
                "mixed-providers.json",
            ),
        }
    finally:
        sys.path.remove(str(OPTIMIZER_ROOT))
    for filename, manifest in fixtures.items():
        rendered = (
            json.dumps(
                manifest,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        path = FIXTURE_ROOT / filename
        if args.check:
            if path.read_text(encoding="utf-8") != rendered:
                raise RuntimeError(
                    f"DeploymentManifest fixture drift: {filename}"
                )
            continue
        path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
