#!/usr/bin/env python3
"""Validate the frozen Phase 8 complete-service decision package offline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_service_bundles"
SCHEMA_PATH = EVIDENCE_ROOT / "schemas/package-artifact.schema.json"
PERMISSION_ROOT = REPOSITORY_ROOT / "3-cloud-deployer/docs/references/permission_sets"
EXPECTED_ARTIFACTS = {
    "decision.json",
    "common-functional-contract.json",
    "complete-provider-bundles.json",
    "boundary-route-matrix.json",
    "workload-scenarios.json",
    "capacity-matrix.json",
    "pricing-ownership-matrix.json",
    "source-ledger.json",
    "implementation-component-manifest.json",
}
PROVIDERS = {"aws", "azure", "gcp"}
CORE_SCENARIOS = {"core-small-v2", "core-medium-v2", "core-large-v2"}
EVENTING_SCENARIOS = {
    "eventing-small-v1",
    "eventing-medium-v1",
    "eventing-large-v1",
}
SECRET_KEYS = {
    "password",
    "passwd",
    "client_secret",
    "private_key",
    "access_key",
    "secret_access_key",
    "api_key",
    "token_value",
}
SECRET_VALUE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
    r"[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def duplicate_values(values: Iterable[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def module(name: str) -> Any:
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def scan_secrets(name: str, value: Any, errors: list[str], path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in SECRET_KEYS:
                errors.append(f"{name}:{'/'.join((*path, key))}: forbidden secret field")
            scan_secrets(name, nested, errors, (*path, key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            scan_secrets(name, nested, errors, (*path, str(index)))
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        errors.append(f"{name}:{'/'.join(path)}: value resembles credential material")


def validate_schema(artifacts: dict[str, Any], errors: list[str]) -> None:
    schema = load_json(SCHEMA_PATH)
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            errors.append(f"{name}: artifact must be an object")
            continue
        for field in required:
            if field not in artifact:
                errors.append(f"{name}: missing required field {field}")
        for field, definition in properties.items():
            if field in artifact and "const" in definition and artifact[field] != definition["const"]:
                errors.append(f"{name}:{field}: value does not match schema const")
        artifact_id = artifact.get("artifact_id")
        if not isinstance(artifact_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", artifact_id):
            errors.append(f"{name}: artifact_id does not match schema pattern")


def validate_generated(artifacts: dict[str, Any], errors: list[str]) -> None:
    calculator = module("calculate_capacity.py")
    expected_capacity = calculator.calculate()
    if artifacts["capacity-matrix.json"] != expected_capacity:
        errors.append("capacity-matrix.json does not match deterministic calculator")

    generator = module("generate_manifests.py")
    bundles = artifacts["complete-provider-bundles.json"]
    routes = artifacts["boundary-route-matrix.json"]
    if artifacts["implementation-component-manifest.json"] != generator.build_manifest(
        bundles, routes
    ):
        errors.append("implementation-component-manifest.json is stale")
    if artifacts["pricing-ownership-matrix.json"] != generator.build_pricing(
        bundles, routes
    ):
        errors.append("pricing-ownership-matrix.json is stale")

    freezer = module("freeze_decision.py")
    if artifacts["decision.json"] != freezer.build():
        errors.append("decision.json or one of its byte digests is stale")


def validate_routes(routes: dict[str, Any], errors: list[str]) -> None:
    cross = {f"{source}->{destination}" for source in PROVIDERS for destination in PROVIDERS if source != destination}
    local = {f"{provider}->{provider}" for provider in PROVIDERS}
    if set(routes["directed_cross_cloud_pairs"]) != cross:
        errors.append("directed_cross_cloud_pairs must contain all six exact pairs")
    if set(routes["same_provider_pairs"]) != local:
        errors.append("same_provider_pairs must contain all three exact pairs")

    placements = routes["online_placements"]
    expected_placements = {(l3_l5, l4) for l3_l5 in PROVIDERS for l4 in PROVIDERS}
    actual_placements = {
        (item["l3_hot_l5_provider"], item["l4_provider"]) for item in placements
    }
    if actual_placements != expected_placements or len(placements) != 9:
        errors.append("online_placements must contain the exact nine L3-hot/L5 plus L4 combinations")
    for item in placements:
        expected_route = f"{item['l3_hot_l5_provider']}->{item['l4_provider']}"
        if item["projection_route"] != expected_route:
            errors.append(f"{item['placement_id']}: projection route does not match placement")

    route_map = {item["route_class"]: item for item in routes["route_classes"]}
    expected_sets = {
        "raw_history_query": local,
        "twin_projection_local": local,
        "twin_projection_cross_cloud": cross,
        "storage_hot_to_cool_local": local,
        "storage_hot_to_cool_cross_cloud": cross,
        "storage_cool_to_archive_local": local,
        "storage_cool_to_archive_cross_cloud": cross,
        "domain_event_cross_cloud": cross,
        "domain_event_local": local,
    }
    if set(route_map) != set(expected_sets):
        errors.append("route classes are incomplete or contain an unknown class")
    for route_class, expected in expected_sets.items():
        if route_class in route_map and set(route_map[route_class]["pairs"]) != expected:
            errors.append(f"{route_class}: pair coverage mismatch")
    if route_map.get("raw_history_query", {}).get("cross_cloud_allowed") is not False:
        errors.append("raw history must be provider-local")
    for route_class in ("twin_projection_cross_cloud", "domain_event_cross_cloud"):
        item = route_map.get(route_class, {})
        if item.get("runtime_owner") != "source_provider":
            errors.append(f"{route_class}: bridge runtime must be source-owned")
        if item.get("destination") != "destination_broker_data_plane":
            errors.append(f"{route_class}: destination must be broker data plane")


def validate_contracts(contract: dict[str, Any], errors: list[str]) -> None:
    definitions = contract.get("contract_definitions", {})
    expected = {
        "raw_history_query.v1",
        "twin_projection.v1",
        "storage_transition.v1",
        "canonical-domain-event.v1",
    }
    if set(definitions) != expected:
        errors.append("common functional contract definitions are incomplete or unknown")

    raw = definitions.get("raw_history_query.v1", {})
    if raw.get("transport", {}).get("provider_placement") != "l3_hot_l5_provider_only":
        errors.append("raw-history transport must remain provider-local")
    if raw.get("request", {}).get("rules", {}).get("limit_max") != 1000:
        errors.append("raw-history query must preserve the 1000-point bound")
    if raw.get("response", {}).get("timeout_seconds") != 10:
        errors.append("raw-history query must preserve the ten-second timeout")
    if raw.get("request", {}).get("additional_fields_allowed") is not False:
        errors.append("raw-history request must be closed")

    projection = definitions.get("twin_projection.v1", {})
    if set(projection.get("variants", {})) != {
        "twin.state.upserted",
        "twin.model.upserted",
        "twin.relationship.upserted",
        "twin.relationship.deleted",
    }:
        errors.append("twin projection variants are incomplete or unknown")
    if projection.get("not_per_telemetry_message") is not True:
        errors.append("twin projection must not become a per-telemetry pipeline")

    storage = definitions.get("storage_transition.v1", {})
    if storage.get("permanent_worker_or_cdc_allowed") is not False:
        errors.append("storage transition must remain a finite scheduled PoC job")
    if storage.get("event_payload_contains_object_bytes") is not False:
        errors.append("storage payload bytes must not traverse the event broker")

    event = definitions.get("canonical-domain-event.v1", {})
    if event.get("anonymous_or_static_shared_bridge_credentials_allowed") is not False:
        errors.append("event bridge must reject anonymous or shared static credentials")


def bundle_component_ids(bundle: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for provider in bundle["providers"]:
        for ids in provider["layers"].values():
            result.update(ids)
        result.update(provider["support_components"])
        result.update(provider["embedded_event_components"])
        result.update(provider["six_layer_event_components"])
    return result


def validate_components(artifacts: dict[str, Any], errors: list[str]) -> None:
    bundle = artifacts["complete-provider-bundles.json"]
    manifest = artifacts["implementation-component-manifest.json"]
    components = manifest["components"]
    ids = [item["component_id"] for item in components]
    for duplicate in duplicate_values(ids):
        errors.append(f"duplicate component: {duplicate}")
    if set(ids) != bundle_component_ids(bundle):
        errors.append("component manifest does not exactly cover selected bundle components")
    for item in components:
        if item["provider"] not in PROVIDERS:
            errors.append(f"{item['component_id']}: invalid provider")
        if not (
            item["terraform_resource_types"] or item["post_terraform_operations"]
        ):
            errors.append(f"{item['component_id']}: missing implementation binding")
        for field in (
            "input_contracts",
            "output_contracts",
            "runtime_package",
            "implementation_file_targets",
            "formula_refs",
            "capacity_dimensions",
        ):
            if not item.get(field):
                errors.append(f"{item['component_id']}: missing {field}")
        if any(port <= 0 or port > 65535 for port in item["network_ports"]):
            errors.append(f"{item['component_id']}: invalid network port")
        if item["runtime_state"] != "decision_frozen_not_implemented":
            errors.append(f"{item['component_id']}: decision package must not claim implementation")

    requirements = manifest.get("terraform_provider_requirements", {})
    expected_requirements = {
        "terraform",
        "aws",
        "awscc",
        "azurerm",
        "google",
        "kubernetes",
    }
    if set(requirements) != expected_requirements:
        errors.append("Terraform provider requirements are incomplete or unknown")
    if requirements.get("google", {}).get("version_constraint") != ">= 7.22.0, < 8.0.0":
        errors.append("Google provider requirement must cover worker pools and direct Cloud Run IAP")
    if requirements.get("google", {}).get("verified_version") != "7.22.0":
        errors.append("Google provider feasibility version must remain reproducible")
    if requirements.get("kubernetes", {}).get("verified_version") != "2.38.0":
        errors.append("Kubernetes provider feasibility version must remain reproducible")
    stages = manifest.get("terraform_apply_stages", [])
    if [item.get("stage") for item in stages] != [1, 2, 3]:
        errors.append("Terraform/Kubernetes/post-Terraform apply stages must be explicit and ordered")
    if stages and stages[1].get("precondition") != (
        "stage_1_cluster_endpoint_and_short_lived_credentials_available"
    ):
        errors.append("Kubernetes apply must wait for the managed cluster and short-lived credentials")
    if "awscc_iot_command" not in next(
        item for item in components if item["component_id"] == "aws.iot-commands"
    )["terraform_resource_types"]:
        errors.append("AWS IoT Commands must use its real AWSCC resource")
    twinmaker = next(
        item for item in components if item["component_id"] == "aws.iot-twinmaker-standard"
    )
    if twinmaker["terraform_resource_types"] != ["awscc_iottwinmaker_workspace"]:
        errors.append("TwinMaker Terraform binding must stop at the supported workspace")
    if not twinmaker["post_terraform_operations"]:
        errors.append("TwinMaker child lifecycle must be an explicit SDK operation")
    gcp_iap = next(
        item
        for item in components
        if item["component_id"] == "gcp.cloud-run-iap-twin-explorer"
    )
    if set(gcp_iap["terraform_resource_types"]) != {
        "google_cloud_run_v2_service",
        "google_cloud_run_v2_service_iam_member",
        "google_iap_web_cloud_run_service_iam_member",
    }:
        errors.append("GCP Twin Explorer must bind both IAP and its Cloud Run service agent")

    pricing = artifacts["pricing-ownership-matrix.json"]
    owners = pricing["component_owners"]
    owner_component_ids = [item["component_id"] for item in owners]
    owner_ids = [item["cost_owner_id"] for item in owners]
    if set(owner_component_ids) != set(ids) or len(owner_component_ids) != len(ids):
        errors.append("pricing ownership does not exactly cover component manifest")
    for duplicate in duplicate_values(owner_ids):
        errors.append(f"duplicate cost owner: {duplicate}")
    if len(pricing["route_owners"]) != 24:
        errors.append("pricing route owners must cover four classes times six directed pairs")
    if pricing["price_value_policy"] != "live_versioned_optimizer_catalog_only_no_static_fallback":
        errors.append("pricing values must come from the live versioned catalog without fallback")


def validate_workloads(artifacts: dict[str, Any], errors: list[str]) -> None:
    workloads = artifacts["workload-scenarios.json"]
    scenarios = workloads["core_scenarios"]
    if {item["scenario_id"] for item in scenarios} != CORE_SCENARIOS:
        errors.append("core workload IDs are incomplete")
    if {item["eventing_scenario_id"] for item in workloads["scenario_pairing"]} != EVENTING_SCENARIOS:
        errors.append("eventing scenario pairing is incomplete")
    for item in scenarios:
        if not (
            1 <= item["hot_boundary_months"]
            < item["cool_boundary_months"]
            < item["archive_boundary_months"]
        ):
            errors.append(f"{item['scenario_id']}: retention boundaries are not cumulative and ordered")

    capacity = {
        item["size"]: item for item in artifacts["capacity-matrix.json"]["scenario_results"]
    }
    exact = {
        "small": (1, 2, 1, 1),
        "medium": (1, 3, 4, 1),
        "large": (16, 42, 30, 19),
    }
    for size, expected in exact.items():
        derived = capacity[size]["derived"]
        actual = (
            derived["firestore_timestamp_shards"],
            derived["reader_max_concurrent_requests"],
            derived["azure_storage_tasks"],
            derived["storage_objects_per_batch_lower_bound"],
        )
        if actual != expected:
            errors.append(f"{size}: capacity tuple {actual!r} != {expected!r}")
        if not derived["cosmos_logical_partition_below_20_gb"]:
            errors.append(f"{size}: Cosmos per-device logical partition proof failed")
        if derived["maximum_aggregate_rollup_points"] != 720:
            errors.append(f"{size}: aggregate rollup bound must be 720")
    if artifacts["capacity-matrix.json"]["global_live_status"] != "live_capacity_pending":
        errors.append("offline capacity evidence must remain live_capacity_pending")


def validate_sources(source_ledger: dict[str, Any], errors: list[str]) -> None:
    sources = source_ledger["sources"]
    source_ids = [item["source_id"] for item in sources]
    for duplicate in duplicate_values(source_ids):
        errors.append(f"duplicate source: {duplicate}")
    available = set(source_ids)
    for fact in source_ledger["facts"]:
        if not fact["source_ids"]:
            errors.append(f"{fact['fact_id']}: source list is empty")
        unknown = set(fact["source_ids"]) - available
        if unknown:
            errors.append(f"{fact['fact_id']}: unknown sources {sorted(unknown)}")
    for source in sources:
        if "url" in source and not source["url"].startswith("https://"):
            errors.append(f"{source['source_id']}: primary source URL must use HTTPS")
        if "path" in source:
            path = REPOSITORY_ROOT / source["path"]
            if not path.is_file():
                errors.append(f"{source['source_id']}: local source is missing")
            elif file_digest(path) != source["byte_digest"]:
                errors.append(f"{source['source_id']}: local source digest changed")


def validate_permissions(decision: dict[str, Any], manifest: dict[str, Any], errors: list[str]) -> None:
    permission_paths = decision["permission_artifact_byte_digests"]
    for path_text, expected in permission_paths.items():
        path = REPOSITORY_ROOT / path_text
        if not path.is_file() or file_digest(path) != expected:
            errors.append(f"permission artifact changed: {path_text}")
    for path_text, expected in decision["immutable_input_byte_digests"].items():
        path = REPOSITORY_ROOT / path_text
        if not path.is_file() or file_digest(path) != expected:
            errors.append(f"immutable input changed: {path_text}")

    for provider in sorted(PROVIDERS):
        path = PERMISSION_ROOT / f"{provider}_thesis_demo_v2.json"
        item = load_json(path)
        if item["provider"] != provider or item["permission_set_version"] != "thesis-demo-v2":
            errors.append(f"{provider}: invalid thesis-demo-v2 manifest identity")
        if item["status"] != "frozen_offline_contract":
            errors.append(f"{provider}: permission manifest overclaims offline status")
        if provider == "gcp" and any("*" in value for value in item["custom_role_inputs"]):
            errors.append("gcp: wildcard custom-role permission is forbidden")
        if provider == "gcp":
            required_iap = {
                "iap.webServices.getIamPolicy",
                "iap.webServices.setIamPolicy",
            }
            if not required_iap.issubset(item["custom_role_inputs"]):
                errors.append("gcp: deployer is missing direct IAP policy permissions")
            if "iap.webServiceVersions.accessViaIAP" in item["custom_role_inputs"]:
                errors.append("gcp: interactive IAP access must not be retained by the deployer")
        scan_secrets(path.name, item, errors)
        review = load_json(PERMISSION_ROOT / item["scope_review_ref"])
        if review["findings"]:
            errors.append(f"{provider}: scope review has unresolved findings")
    expected_refs = {f"{provider}_thesis_demo_v2" for provider in PROVIDERS}
    for component in manifest["components"]:
        if set(component["permission_set_refs"]) != {f"{component['provider']}_thesis_demo_v2"}:
            errors.append(f"{component['component_id']}: wrong permission manifest")
    actual_refs = {ref for item in manifest["components"] for ref in item["permission_set_refs"]}
    if actual_refs != expected_refs:
        errors.append("component permission references do not cover all providers")


def validate_plugins(bundle: dict[str, Any], errors: list[str]) -> None:
    plugins = {item["plugin_id"]: item for item in bundle["plugin_decisions"]}
    json_api = plugins.get("marcusolsson-json-datasource", {})
    if json_api.get("selected_version") != "1.4.0":
        errors.append("JSON API plugin version must be frozen to 1.4.0")
    if json_api.get("hard_end_date") is not None:
        errors.append("JSON API decision must not invent a hard support-end date")
    infinity = plugins.get("yesoreyeram-infinity-datasource", {})
    if infinity.get("selected_version") != "3.10.1":
        errors.append("Infinity plugin version must be frozen to 3.10.1")
    if infinity.get("artifact_digest") != "sha256:39d1cac9bcd2f7f2e46607319cb27afb8592ab0fcbc57968dc9fb86f3ef69a59":
        errors.append("Infinity plugin artifact digest mismatch")


def validate() -> list[str]:
    errors: list[str] = []
    actual_files = {path.name for path in EVIDENCE_ROOT.glob("*.json")}
    if actual_files != EXPECTED_ARTIFACTS:
        errors.append(
            f"artifact set mismatch: expected {sorted(EXPECTED_ARTIFACTS)}, got {sorted(actual_files)}"
        )
    artifacts = {
        name: load_json(EVIDENCE_ROOT / name)
        for name in sorted(EXPECTED_ARTIFACTS)
        if (EVIDENCE_ROOT / name).is_file()
    }
    if set(artifacts) != EXPECTED_ARTIFACTS:
        return errors
    validate_schema(artifacts, errors)
    for name, artifact in artifacts.items():
        scan_secrets(name, artifact, errors)
    artifact_ids = [artifact["artifact_id"] for artifact in artifacts.values()]
    for duplicate in duplicate_values(artifact_ids):
        errors.append(f"duplicate artifact_id: {duplicate}")
    validate_generated(artifacts, errors)
    validate_contracts(artifacts["common-functional-contract.json"], errors)
    validate_routes(artifacts["boundary-route-matrix.json"], errors)
    validate_components(artifacts, errors)
    validate_workloads(artifacts, errors)
    validate_sources(artifacts["source-ledger.json"], errors)
    validate_permissions(
        artifacts["decision.json"],
        artifacts["implementation-component-manifest.json"],
        errors,
    )
    validate_plugins(artifacts["complete-provider-bundles.json"], errors)
    decision = artifacts["decision.json"]
    if decision["decision_status"] != "approved":
        errors.append("decision_status must be approved")
    if len(decision["reviews"]) < 2 or any(
        review["unresolved_findings"] != 0 for review in decision["reviews"]
    ):
        errors.append("two zero-finding reviews are required")
    if not (EVIDENCE_ROOT / "README.md").is_file():
        errors.append("README.md is missing")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate()
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("phase-08-complete-service-bundles@1: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
