#!/usr/bin/env python3
"""Validate the complete, frozen Phase 8 Eventing decision package offline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import jsonschema
from referencing import Registry, Resource


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing"
SCHEMA_ROOT = EVIDENCE_ROOT / "schemas"
MANIFEST_PATH = EVIDENCE_ROOT / "implementation-component-manifest.json"
DECISION_PATH = EVIDENCE_ROOT / "decision.json"
README_PATH = EVIDENCE_ROOT / "README.md"
PROVIDERS = {"aws", "azure", "gcp"}
SCENARIOS = {"eventing-small-v1", "eventing-medium-v1", "eventing-large-v1"}
PROFILE_TARGETS = {"six-layer-eventing@1"}
EXPECTED_PROFILE_EXTENSION_EVENT_TYPES = [
    "twin.state.upserted",
    "twin.model.upserted",
    "twin.relationship.upserted",
    "twin.relationship.deleted",
]
EXPECTED_BRIDGE_COMPONENTS = {
    "six-layer-eventing@1": {
        "aws": {
            "telemetry": {"deployment.aws.event.kinesis"},
            "control": {
                "deployment.aws.event.sns-fifo",
                "deployment.aws.event.sqs-fifo",
            },
        },
        "azure": {
            "telemetry": {
                "deployment.azure.event.event-hubs-standard",
                "deployment.azure.event.event-hubs-dedicated",
            },
            "control": {"deployment.azure.event.service-bus"},
        },
        "gcp": {
            "telemetry": {"deployment.gcp.event.pubsub"},
            "control": {"deployment.gcp.event.pubsub"},
        },
    },
}
EXPECTED_ARTIFACT_IDS = {
    "bridge-decision",
    "domain-event-flow-contract",
    "formula-and-unit-ledger",
    "mandatory-capabilities",
    "pricing-model-matrix",
    "profile-parity-decision",
    "provider-capability-matrix",
    "scenario-cost-results",
    "scenario-inputs",
    "source-ledger",
}
SECRET_FIELD = re.compile(
    r"(^|_)(password|passwd|secret|client_secret|access_key|private_key|api_key)($|_)",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\."
    r"[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def load_calculator() -> Any:
    path = Path(__file__).with_name("calculate_scenarios.py")
    spec = importlib.util.spec_from_file_location("phase_08_calculator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import calculator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artifact_digest(document: Any) -> str:
    calculator = load_calculator()
    return calculator.normalized_digest(calculator.normalize_for_digest(document))


def iter_references(value: Any, keys: set[str]) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in keys and isinstance(nested, str):
                yield nested
            elif key in keys and isinstance(nested, list):
                yield from (item for item in nested if isinstance(item, str))
            else:
                yield from iter_references(nested, keys)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_references(nested, keys)


def duplicate_values(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def add_duplicates(
    errors: list[str],
    label: str,
    values: Iterable[str],
) -> None:
    for value in duplicate_values(values):
        errors.append(f"duplicate {label}: {value}")


def directed_pairs() -> set[tuple[str, str]]:
    return {
        (source, destination)
        for source in PROVIDERS
        for destination in PROVIDERS
        if source != destination
    }


def provider_permutations() -> set[tuple[str, str, str]]:
    return {
        (ingress, eventing, processing)
        for ingress in PROVIDERS
        for eventing in PROVIDERS
        for processing in PROVIDERS
        if len({ingress, eventing, processing}) == 3
    }


def schema_registry() -> tuple[Registry, dict[str, dict[str, Any]]]:
    registry = Registry()
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        jsonschema.validators.validator_for(schema).check_schema(schema)
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(schema["$id"], resource)
        schemas[path.name] = schema
    return registry, schemas


def validate_schemas(
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    try:
        registry, schemas = schema_registry()
    except Exception as exc:  # pragma: no cover - exercised by command failures
        errors.append(f"invalid schema registry: {exc}")
        return

    for name, document in sorted(artifacts.items()):
        declared = document.get("$schema") if isinstance(document, dict) else None
        if not isinstance(declared, str):
            errors.append(f"{name}: missing $schema")
            continue
        schema_name = Path(declared).name
        schema = schemas.get(schema_name)
        if schema is None:
            errors.append(f"{name}: unresolved schema {declared}")
            continue
        validator_class = jsonschema.validators.validator_for(schema)
        validator = validator_class(
            schema,
            registry=registry,
            format_checker=jsonschema.FormatChecker(),
        )
        for failure in sorted(
            validator.iter_errors(document),
            key=lambda item: list(item.absolute_path),
        ):
            location = "/".join(str(item) for item in failure.absolute_path)
            errors.append(f"{name}:{location or '<root>'}: {failure.message}")


def validate_secrets(
    name: str,
    value: Any,
    errors: list[str],
    path: tuple[str, ...] = (),
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if SECRET_FIELD.search(key):
                errors.append(
                    f"{name}:{'/'.join((*path, key))}: secret-like field name"
                )
            validate_secrets(name, nested, errors, (*path, key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_secrets(name, nested, errors, (*path, str(index)))
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        errors.append(f"{name}:{'/'.join(path)}: value resembles credential material")


def validate_reference_integrity(
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    source_ledger = artifacts["source-ledger.json"]
    sources = source_ledger["sources"]
    source_ids = {item["source_id"] for item in sources}
    fact_ids = {fact["fact_id"] for source in sources for fact in source["facts"]}
    add_duplicates(errors, "source_id", (item["source_id"] for item in sources))
    add_duplicates(
        errors,
        "fact_id",
        (fact["fact_id"] for source in sources for fact in source["facts"]),
    )

    capabilities = artifacts["mandatory-capabilities.json"]
    capability_rows = [
        row
        for section in ("embedded_capabilities", "event_layer_capabilities")
        for row in capabilities[section]
    ]
    capability_ids = {row["capability_id"] for row in capability_rows}
    add_duplicates(
        errors,
        "capability_id",
        (row["capability_id"] for row in capability_rows),
    )

    formulas = artifacts["formula-and-unit-ledger.json"]
    formula_ids = {row["formula_id"] for row in formulas["formulas"]}
    normalization_ids = {
        row["normalization_rule_id"] for row in formulas["normalization_rules"]
    }
    conversion_ids = {row["conversion_id"] for row in formulas["unit_conversions"]}
    add_duplicates(
        errors,
        "formula_id",
        (row["formula_id"] for row in formulas["formulas"]),
    )
    add_duplicates(
        errors,
        "normalization_rule_id",
        (row["normalization_rule_id"] for row in formulas["normalization_rules"]),
    )
    add_duplicates(
        errors,
        "conversion_id",
        (row["conversion_id"] for row in formulas["unit_conversions"]),
    )

    bifromq_formula = next(
        (
            row
            for row in formulas["formulas"]
            if row["formula_id"] == "formula.gcp.bifromq-gke"
        ),
        None,
    )
    expected_bifromq_inputs = {
        "cluster_hours",
        "cluster_hour_price",
        "broker_node_count",
        "integration_node_count",
        "node_hour_price",
        "disk_gib_per_node",
        "disk_gib_hour_price",
        "forwarding_rule_hours",
        "forwarding_rule_hour_price",
        "device_telemetry_data_gib",
        "command_data_gib",
        "lb_processing_gib_price",
    }
    if (
        bifromq_formula is None
        or set(bifromq_formula["inputs"]) != expected_bifromq_inputs
        or any(
            identifier not in bifromq_formula["expression"]
            for identifier in expected_bifromq_inputs
        )
    ):
        errors.append("BifroMQ formula input/expression contract mismatch")

    pricing = artifacts["pricing-model-matrix.json"]
    intent_ids = {row["intent_id"] for row in pricing["price_intents"]}
    add_duplicates(
        errors,
        "intent_id",
        (row["intent_id"] for row in pricing["price_intents"]),
    )

    all_documents = {
        name: document
        for name, document in artifacts.items()
        if name != "source-ledger.json"
    }
    for name, document in all_documents.items():
        for source_ref in iter_references(
            document,
            {"source_id", "source_ids", "source_refs"},
        ):
            if source_ref not in source_ids:
                errors.append(f"{name}: unresolved source reference {source_ref}")
        for fact_ref in iter_references(document, {"fact_id", "fact_ids"}):
            if fact_ref not in fact_ids:
                errors.append(f"{name}: unresolved fact reference {fact_ref}")
        for formula_ref in iter_references(
            document,
            {"formula_id", "formula_ids"},
        ):
            if formula_ref not in formula_ids:
                errors.append(f"{name}: unresolved formula reference {formula_ref}")
        for rule_ref in iter_references(
            document,
            {"normalization_rule_id", "normalization_rule_ids"},
        ):
            if rule_ref not in normalization_ids | conversion_ids:
                errors.append(f"{name}: unresolved normalization reference {rule_ref}")
        for conversion_ref in iter_references(
            document,
            {"conversion_id", "conversion_ids"},
        ):
            if conversion_ref not in conversion_ids:
                errors.append(
                    f"{name}: unresolved conversion reference {conversion_ref}"
                )
        for intent_ref in iter_references(
            document,
            {"intent_id", "intent_ids", "pricing_intent_ids"},
        ):
            if intent_ref not in intent_ids:
                errors.append(f"{name}: unresolved pricing intent {intent_ref}")
        for capability_ref in iter_references(document, {"capability_id"}):
            if capability_ref not in capability_ids:
                errors.append(
                    f"{name}: unresolved capability reference {capability_ref}"
                )


def validate_coverage(
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    scenarios = artifacts["scenario-inputs.json"]["scenarios"]
    actual_scenarios = {row["scenario_id"] for row in scenarios}
    if actual_scenarios != SCENARIOS:
        errors.append(f"scenario coverage mismatch: {sorted(actual_scenarios)}")

    parity = artifacts["profile-parity-decision.json"]
    profile_ids = {row["profile_id"] for row in parity["profiles"]}
    if profile_ids != PROFILE_TARGETS:
        errors.append(f"profile parity mismatch: {sorted(profile_ids)}")
    if set(parity["comparison_rule"]["functional_parity_profiles"]) != PROFILE_TARGETS:
        errors.append("functional validation must target only six-layer@1")
    if parity["legacy_flag_policy"]["new_profile_behavior"] != "reject":
        errors.append("new profiles must reject all legacy event feature flags")

    capability = artifacts["provider-capability-matrix.json"]
    registry = artifacts["mandatory-capabilities.json"]
    expected_capabilities = {
        "embedded": {row["capability_id"] for row in registry["embedded_capabilities"]},
        "event_layer": {
            row["capability_id"] for row in registry["event_layer_capabilities"]
        },
    }
    actual_capabilities: dict[str, set[str]] = defaultdict(set)
    add_duplicates(
        errors,
        "provider capability row",
        (
            f"{row['profile_scope']}:{row['capability_id']}"
            for row in capability["capability_rows"]
        ),
    )
    for row in capability["capability_rows"]:
        actual_capabilities[row["profile_scope"]].add(row["capability_id"])
        cell_providers = {cell["provider"] for cell in row["cells"]}
        if cell_providers != PROVIDERS:
            errors.append(f"{row['capability_id']}: provider cell coverage mismatch")
        for cell in row["cells"]:
            if cell["status"] in {"unsupported", "unverified"}:
                errors.append(
                    f"{row['capability_id']}: {cell['provider']} is {cell['status']}"
                )
    for scope, expected in expected_capabilities.items():
        if actual_capabilities[scope] != expected:
            errors.append(
                f"{scope} capability coverage mismatch: "
                f"{sorted(actual_capabilities[scope])}"
            )

    bundles = capability["bundle_selections"]
    expected_bundles = {
        (provider, scope)
        for provider in PROVIDERS
        for scope in {"embedded", "event_layer"}
    }
    actual_bundles = {
        (row["provider"], row["profile_scope"])
        for row in bundles
        if row["decision"] == "selected"
    }
    if actual_bundles != expected_bundles:
        errors.append(f"selected bundle coverage mismatch: {sorted(actual_bundles)}")

    capacity_cases = {
        (row["provider"], row["scenario_id"])
        for row in capability["capacity_allocations"]
    }
    expected_capacity_cases = {
        (provider, scenario) for provider in PROVIDERS for scenario in SCENARIOS
    }
    if capacity_cases != expected_capacity_cases or len(
        capability["capacity_allocations"]
    ) != len(expected_capacity_cases):
        errors.append(
            f"capacity allocation coverage mismatch: {sorted(capacity_cases)}"
        )

    single = {row["provider"] for row in capability["single_cloud_cases"]}
    if single != PROVIDERS:
        errors.append(f"single-cloud coverage mismatch: {sorted(single)}")
    pairs = {
        (row["source_provider"], row["destination_provider"])
        for row in capability["directed_pair_cases"]
    }
    if pairs != directed_pairs():
        errors.append(f"directed-pair coverage mismatch: {sorted(pairs)}")
    triples = {
        (
            row["ingress_provider"],
            row["eventing_provider"],
            row["processing_provider"],
        )
        for row in capability["three_provider_cases"]
    }
    if triples != provider_permutations():
        errors.append(f"three-provider coverage mismatch: {sorted(triples)}")

    rejected_ids = {
        row["alternative_id"] for row in capability["rejected_alternatives"]
    }
    pricing_rejected_ids = {
        row["alternative_id"]
        for row in artifacts["pricing-model-matrix.json"]["rejected_member_dimensions"]
    }
    add_duplicates(
        errors,
        "rejected capability alternative",
        (row["alternative_id"] for row in capability["rejected_alternatives"]),
    )
    add_duplicates(
        errors,
        "rejected pricing alternative",
        (
            row["alternative_id"]
            for row in artifacts["pricing-model-matrix.json"][
                "rejected_member_dimensions"
            ]
        ),
    )
    if rejected_ids != pricing_rejected_ids:
        errors.append("rejected alternative capability/pricing coverage mismatch")

    bridge = artifacts["bridge-decision.json"]
    identity_pairs = {
        (row["source_provider"], row["destination_provider"])
        for row in bridge["directed_identity_paths"]
    }
    if identity_pairs != directed_pairs():
        errors.append(f"bridge identity coverage mismatch: {sorted(identity_pairs)}")
    aws_to_azure = next(
        (
            row
            for row in bridge["directed_identity_paths"]
            if row["source_provider"] == "aws"
            and row["destination_provider"] == "azure"
        ),
        None,
    )
    if (
        aws_to_azure is None
        or "regional STS" not in aws_to_azure["source_assertion"]
        or (
            "preflight_aws_outbound_federation_enabled_and_regional_sts_endpoint"
            not in bridge["verification_gates"]
        )
    ):
        errors.append("AWS-to-Azure outbound identity preflight is incomplete")

    aws_requirement = next(
        (
            row
            for row in artifacts["implementation-component-manifest.json"][
                "provider_requirements"
            ]
            if row["provider"] == "aws"
        ),
        None,
    )
    required_aws_preflight = {
        "outbound_web_identity_federation_account_enabled",
        "regional_STS_endpoint_for_GetWebIdentityToken",
    }
    if aws_requirement is None or not required_aws_preflight.issubset(
        set(aws_requirement["preflight_gates"])
    ):
        errors.append("AWS provider outbound identity preflight is incomplete")
    runtime_providers = {row["provider"] for row in bridge["provider_source_runtimes"]}
    landing_providers = {row["provider"] for row in bridge["destination_landings"]}
    if runtime_providers != PROVIDERS:
        errors.append(f"bridge source runtime mismatch: {sorted(runtime_providers)}")
    if landing_providers != PROVIDERS:
        errors.append(f"bridge destination mismatch: {sorted(landing_providers)}")

    results = artifacts["scenario-cost-results.json"]["scenarios"]
    result_scenarios = {row["scenario_id"] for row in results}
    if result_scenarios != SCENARIOS:
        errors.append(f"result scenario coverage mismatch: {sorted(result_scenarios)}")
    for result in results:
        if {row["provider"] for row in result["single_cloud_results"]} != PROVIDERS:
            errors.append(f"{result['scenario_id']}: incomplete single-cloud results")
        result_pairs = {
            (row["source_provider"], row["destination_provider"])
            for row in result["directed_pair_bridge_results"]
        }
        if result_pairs != directed_pairs():
            errors.append(f"{result['scenario_id']}: incomplete directed-pair results")
        result_triples = {
            (
                row["ingress_provider"],
                row["eventing_provider"],
                row["processing_provider"],
            )
            for row in result["three_provider_results"]
        }
        if result_triples != provider_permutations():
            errors.append(f"{result['scenario_id']}: incomplete three-provider results")


def validate_manifest(
    artifacts: dict[str, Any],
    errors: list[str],
    *,
    require_new_targets_absent: bool = False,
) -> None:
    manifest = artifacts["implementation-component-manifest.json"]
    capability = artifacts["provider-capability-matrix.json"]
    pricing = artifacts["pricing-model-matrix.json"]
    domain = artifacts["domain-event-flow-contract.json"]

    artifact_refs = manifest["artifact_refs"]
    add_duplicates(
        errors,
        "manifest artifact_id",
        (row["artifact_id"] for row in artifact_refs),
    )
    if {row["artifact_id"] for row in artifact_refs} != EXPECTED_ARTIFACT_IDS:
        errors.append("manifest artifact set is not the exact frozen dependency set")
    for ref in artifact_refs:
        path = REPOSITORY_ROOT / ref["path"]
        if not path.is_file():
            errors.append(f"manifest artifact missing: {ref['path']}")
            continue
        document = load_json(path)
        if document.get("schema_version") != ref["schema_version"]:
            errors.append(f"manifest schema version mismatch: {ref['artifact_id']}")
        expected = artifact_digest(document)
        if ref["digest"] != expected:
            errors.append(
                f"manifest digest mismatch: {ref['artifact_id']}: expected {expected}"
            )

    if {row["profile_id"] for row in manifest["profile_targets"]} != PROFILE_TARGETS:
        errors.append("implementation manifest targets the wrong profiles")
    if {row["provider"] for row in manifest["provider_requirements"]} != PROVIDERS:
        errors.append("implementation manifest provider requirements incomplete")

    bundle_by_id = {row["bundle_id"]: row for row in capability["bundle_selections"]}
    intent_by_id = {row["intent_id"]: row for row in pricing["price_intents"]}
    pricing_by_bundle = {
        row["bundle_id"]: set(row["intent_ids"])
        for row in pricing["selected_bundle_intents"]
    }
    components_by_bundle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    deployment_ids: set[str] = set()
    deployment_metadata: dict[str, tuple[str, str, set[str]]] = {}
    resource_ids: list[str] = []
    component_ids: list[str] = []
    for component in manifest["service_components"]:
        component_ids.append(component["component_manifest_id"])
        bundle_id = component["bundle_id"]
        components_by_bundle[bundle_id].append(component)
        deployment_ids.add(component["deployment_component_id"])
        deployment_metadata[component["deployment_component_id"]] = (
            component["provider"],
            component["profile_scope"],
            set(component["runtime_adapter_ids"]),
        )
        resource_ids.extend(component["terraform"]["resource_ids"])
    add_duplicates(errors, "component_manifest_id", component_ids)
    add_duplicates(errors, "Terraform resource_id", resource_ids)
    add_duplicates(
        errors,
        "deployment_component_id",
        (row["deployment_component_id"] for row in manifest["service_components"]),
    )

    for bundle_id, bundle in bundle_by_id.items():
        components = components_by_bundle.get(bundle_id, [])
        selected_members = Counter(bundle["members"])
        manifested_members = Counter(
            component["selected_member"] for component in components
        )
        if selected_members != manifested_members:
            errors.append(
                f"{bundle_id}: selected members and manifest components differ"
            )
        manifested_intents = {
            intent
            for component in components
            for intent in component["pricing_intent_ids"]
        }
        if manifested_intents != pricing_by_bundle.get(bundle_id, set()):
            errors.append(f"{bundle_id}: pricing-intent ownership differs")
        for component in components:
            required_formulas = {
                intent_by_id[intent_id]["formula_id"]
                for intent_id in component["pricing_intent_ids"]
            }
            if not required_formulas.issubset(set(component["formula_ids"])):
                errors.append(
                    f"{component['component_manifest_id']}: "
                    "pricing formulas are not completely owned"
                )
    unknown_bundles = set(components_by_bundle) - set(bundle_by_id)
    if unknown_bundles:
        errors.append(f"manifest references unknown bundles: {sorted(unknown_bundles)}")

    adapter_ids = {row["adapter_id"] for row in manifest["runtime_adapters"]}
    add_duplicates(
        errors,
        "adapter_id",
        (row["adapter_id"] for row in manifest["runtime_adapters"]),
    )
    for component in manifest["service_components"]:
        for adapter_id in component["runtime_adapter_ids"]:
            if adapter_id not in adapter_ids:
                errors.append(f"unresolved runtime adapter: {adapter_id}")

    contract_ids = {row["contract_id"] for row in manifest["contract_targets"]}
    add_duplicates(
        errors,
        "contract target",
        (row["contract_id"] for row in manifest["contract_targets"]),
    )
    ownership_by_path = {row["path"]: row for row in manifest["file_ownership"]}
    for target in manifest["contract_targets"]:
        owner_path = target["owner_path"]
        repository_path = REPOSITORY_ROOT / owner_path
        if target["status"] == "planned_phase_8_9_contract":
            owner = ownership_by_path.get(owner_path)
            if owner is None or owner["operation"] != "new":
                errors.append(
                    f"{target['contract_id']}: planned contract has no new-file owner"
                )
        elif not repository_path.exists():
            errors.append(
                f"{target['contract_id']}: existing contract target is missing"
            )
    contract_refs: list[str] = []
    for component in manifest["service_components"]:
        contract_refs.extend(component["contract_refs"])
    for adapter in manifest["runtime_adapters"]:
        contract_refs.extend(
            [
                adapter["envelope_ref"],
                adapter["error_contract_ref"],
                adapter["observability_contract_ref"],
                adapter["cleanup_contract_ref"],
            ]
        )
    for edge in manifest["logical_edges"]:
        contract_refs.extend([edge["envelope_ref"], edge["delivery_contract_ref"]])
    contract_refs.extend(
        row["trust_path_ref"] for row in manifest["bridge_route_classes"]
    )
    for contract_ref in contract_refs:
        base_ref = contract_ref.split("#", maxsplit=1)[0]
        if base_ref not in contract_ids:
            errors.append(f"unresolved contract reference: {contract_ref}")

    route_pairs = {
        (row["source_provider"], row["destination_provider"])
        for row in manifest["bridge_route_classes"]
    }
    if route_pairs != directed_pairs():
        errors.append(f"manifest bridge route mismatch: {sorted(route_pairs)}")
    add_duplicates(
        errors,
        "route_class_id",
        (row["route_class_id"] for row in manifest["bridge_route_classes"]),
    )
    for route in manifest["bridge_route_classes"]:
        if route["source_adapter_id"] not in adapter_ids:
            errors.append(f"{route['route_class_id']}: unresolved source adapter")
        source_adapter = next(
            (
                row
                for row in manifest["runtime_adapters"]
                if row["adapter_id"] == route["source_adapter_id"]
            ),
            None,
        )
        if (
            source_adapter is not None
            and source_adapter["provider"] != route["source_provider"]
        ):
            errors.append(f"{route['route_class_id']}: source adapter provider differs")
        bindings = route["profile_bindings"]
        binding_profiles = {row["profile_id"] for row in bindings}
        if binding_profiles != PROFILE_TARGETS or len(bindings) != len(PROFILE_TARGETS):
            errors.append(
                f"{route['route_class_id']}: incomplete profile route bindings"
            )
        for binding in bindings:
            expected_scope = "event_layer"
            for side, provider in (
                ("source", route["source_provider"]),
                ("destination", route["destination_provider"]),
            ):
                expected = EXPECTED_BRIDGE_COMPONENTS[binding["profile_id"]][provider]
                actual_telemetry = set(binding[f"{side}_telemetry_component_ids"])
                actual_control = set(binding[f"{side}_control_component_ids"])
                if (
                    actual_telemetry != expected["telemetry"]
                    or actual_control != expected["control"]
                ):
                    errors.append(
                        f"{route['route_class_id']}: {side} components differ "
                        f"from exact {binding['profile_id']} binding"
                    )
            checks = [
                (
                    component_id,
                    route["source_provider"],
                    "source",
                )
                for component_id in (
                    binding["source_telemetry_component_ids"]
                    + binding["source_control_component_ids"]
                )
            ]
            checks.extend(
                (
                    component_id,
                    route["destination_provider"],
                    "destination",
                )
                for component_id in (
                    binding["destination_telemetry_component_ids"]
                    + binding["destination_control_component_ids"]
                )
            )
            for component_id, expected_provider, side in checks:
                metadata = deployment_metadata.get(component_id)
                if metadata is None:
                    errors.append(
                        f"{route['route_class_id']}: unresolved {side} {component_id}"
                    )
                    continue
                provider, scope, runtime_adapter_ids = metadata
                if provider != expected_provider or scope != expected_scope:
                    errors.append(
                        f"{route['route_class_id']}: {side} {component_id} "
                        "has the wrong provider or profile scope"
                    )
                if (
                    side == "source"
                    and route["source_adapter_id"] not in runtime_adapter_ids
                ):
                    errors.append(
                        f"{route['route_class_id']}: source {component_id} "
                        "does not own the route bridge adapter"
                    )

    domain_channels = {row["channel_id"]: row for row in domain["channels"]}
    manifest_edges = {row["channel_id"]: row for row in manifest["logical_edges"]}
    add_duplicates(
        errors,
        "logical edge channel_id",
        (row["channel_id"] for row in manifest["logical_edges"]),
    )
    if set(domain_channels) != set(manifest_edges):
        errors.append("manifest logical edges do not cover the domain contract exactly")
    for channel_id in set(domain_channels) & set(manifest_edges):
        channel = domain_channels[channel_id]
        edge = manifest_edges[channel_id]
        if edge["producer_component_id"] != channel["producer"]:
            errors.append(f"{channel_id}: producer differs from domain contract")
        if edge["consumer_component_ids"] != channel["consumers"]:
            errors.append(f"{channel_id}: consumers differ from domain contract")
        if set(edge["profiles"]) != PROFILE_TARGETS:
            errors.append(f"{channel_id}: profile edge coverage is incomplete")

    file_paths = [row["path"] for row in manifest["file_ownership"]]
    add_duplicates(errors, "file ownership path", file_paths)
    for row in manifest["file_ownership"]:
        path = REPOSITORY_ROOT / row["path"]
        if row["operation"] == "modify" and not path.exists():
            errors.append(f"modify target does not exist: {row['path']}")
        if require_new_targets_absent and row["operation"] == "new" and path.exists():
            errors.append(f"new target already exists: {row['path']}")
    referenced_implementation_paths = {
        row["architecture_definition_path"] for row in manifest["profile_targets"]
    }
    referenced_implementation_paths.update(
        row["terraform"]["owner_file"] for row in manifest["service_components"]
    )
    referenced_implementation_paths.update(
        row["source_path"] for row in manifest["runtime_adapters"]
    )
    for path in sorted(referenced_implementation_paths - set(file_paths)):
        errors.append(f"implementation path has no file owner: {path}")


def validate_event_type_registry(
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    domain = artifacts["domain-event-flow-contract.json"]
    bridge = artifacts["bridge-decision.json"]
    registry = bridge["envelope_contract"]["event_type_registry"]
    core_event_types = [row["channel_id"] for row in domain["channels"]]

    if registry["core_event_types"] != core_event_types:
        errors.append(
            "bridge core event registry differs from the domain-flow channels"
        )
    if (
        registry["profile_extension_event_types"]
        != EXPECTED_PROFILE_EXTENSION_EVENT_TYPES
    ):
        errors.append("bridge Twin-projection event registry is incomplete")
    combined = [
        *registry["core_event_types"],
        *registry["profile_extension_event_types"],
    ]
    add_duplicates(errors, "canonical event type", combined)


def validate_reproducibility(
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    calculator = load_calculator()
    expected = calculator.build_result()
    committed = calculator.load_json(calculator.RESULT_PATH)
    if expected != committed:
        errors.append("scenario-cost-results.json is not calculator-reproducible")
        return
    result_digest = expected["result_digest"]
    readme = README_PATH.read_text(encoding="utf-8")
    if result_digest not in readme:
        errors.append("README does not contain the current result digest")


def validate_decision(
    artifacts: dict[str, Any],
    errors: list[str],
) -> None:
    decision = artifacts.get("decision.json")
    if decision is None:
        errors.append("missing final decision.json")
        return
    digest_inputs = {
        "bridge_decision": "bridge-decision.json",
        "domain_event_flow_contract": "domain-event-flow-contract.json",
        "formula_and_unit_ledger": "formula-and-unit-ledger.json",
        "implementation_component_manifest": ("implementation-component-manifest.json"),
        "mandatory_capabilities": "mandatory-capabilities.json",
        "pricing_model_matrix": "pricing-model-matrix.json",
        "profile_parity_decision": "profile-parity-decision.json",
        "provider_capability_matrix": "provider-capability-matrix.json",
        "scenario_cost_results": "scenario-cost-results.json",
        "scenario_inputs": "scenario-inputs.json",
        "source_ledger": "source-ledger.json",
    }
    for input_id, artifact_name in digest_inputs.items():
        expected = artifact_digest(artifacts[artifact_name])
        actual = decision["input_digests"][input_id]
        if actual != expected:
            errors.append(f"decision digest mismatch: {input_id}: expected {expected}")
    capability = artifacts["provider-capability-matrix.json"]
    selected: dict[str, set[str]] = defaultdict(set)
    for bundle in capability["bundle_selections"]:
        if bundle["decision"] == "selected":
            selected[bundle["profile_scope"]].add(bundle["bundle_id"])
    if set(decision["selected_embedded_event_bundle_refs"]) != selected["embedded"]:
        errors.append("decision embedded bundle refs differ from capability matrix")
    if set(decision["selected_event_layer_bundle_refs"]) != selected["event_layer"]:
        errors.append("decision Event-Layer bundle refs differ from capability matrix")
    results = artifacts["scenario-cost-results.json"]
    if decision["scenario_result_digest"] != results["result_digest"]:
        errors.append("decision scenario digest differs from committed result")
    if decision["decision_status"] == "approved":
        if decision["mandatory_capability_result"]["status"] != "passed":
            errors.append("approved decision has failed mandatory capabilities")
        if decision["pricing_completeness_result"]["status"] != "passed":
            errors.append("approved decision has incomplete pricing")
        if len(decision["reviewers"]) < 2:
            errors.append("approved decision requires two review records")
        for review in decision["reviewers"]:
            if review["result"] != "zero_findings":
                errors.append(
                    f"approved decision has unresolved review: {review['review_id']}"
                )
    add_duplicates(
        errors,
        "review_id",
        (row["review_id"] for row in decision["reviewers"]),
    )
    add_duplicates(
        errors,
        "risk_id",
        (row["risk_id"] for row in decision["residual_risks"]),
    )


def load_artifacts() -> dict[str, Any]:
    return {path.name: load_json(path) for path in sorted(EVIDENCE_ROOT.glob("*.json"))}


def validate(
    strict: bool = True,
    *,
    require_new_targets_absent: bool = False,
) -> list[str]:
    artifacts = load_artifacts()
    errors: list[str] = []
    validate_schemas(artifacts, errors)
    for name, document in artifacts.items():
        validate_secrets(name, document, errors)
    validate_reference_integrity(artifacts, errors)
    validate_coverage(artifacts, errors)
    validate_manifest(
        artifacts,
        errors,
        require_new_targets_absent=require_new_targets_absent,
    )
    validate_event_type_registry(artifacts, errors)
    validate_reproducibility(artifacts, errors)
    validate_decision(artifacts, errors)
    if strict:
        ledger = artifacts["source-ledger.json"]
        for source in ledger["sources"]:
            if source["review_status"] != "reviewed":
                errors.append(
                    f"strict mode rejects {source['review_status']}: "
                    f"{source['source_id']}"
                )
    return errors


def refresh_artifact_digests() -> None:
    manifest = load_json(MANIFEST_PATH)
    for ref in manifest["artifact_refs"]:
        document = load_json(REPOSITORY_ROOT / ref["path"])
        ref["digest"] = artifact_digest(document)
    write_json(MANIFEST_PATH, manifest)


def refresh_decision_digests() -> None:
    decision = load_json(DECISION_PATH)
    digest_inputs = {
        "bridge_decision": "bridge-decision.json",
        "domain_event_flow_contract": "domain-event-flow-contract.json",
        "formula_and_unit_ledger": "formula-and-unit-ledger.json",
        "implementation_component_manifest": ("implementation-component-manifest.json"),
        "mandatory_capabilities": "mandatory-capabilities.json",
        "pricing_model_matrix": "pricing-model-matrix.json",
        "profile_parity_decision": "profile-parity-decision.json",
        "provider_capability_matrix": "provider-capability-matrix.json",
        "scenario_cost_results": "scenario-cost-results.json",
        "scenario_inputs": "scenario-inputs.json",
        "source_ledger": "source-ledger.json",
    }
    for input_id, artifact_name in digest_inputs.items():
        decision["input_digests"][input_id] = artifact_digest(
            load_json(EVIDENCE_ROOT / artifact_name)
        )
    decision["scenario_result_digest"] = load_json(
        EVIDENCE_ROOT / "scenario-cost-results.json"
    )["result_digest"]
    write_json(DECISION_PATH, decision)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--check-planned-target-absence",
        action="store_true",
        help=(
            "Planning-time collision check. Do not use after implementation "
            "of the immutable manifest has started."
        ),
    )
    parser.add_argument(
        "--refresh-artifact-digests",
        action="store_true",
        help="Explicitly rewrite manifest dependency digests.",
    )
    parser.add_argument(
        "--refresh-decision-digests",
        action="store_true",
        help="Explicitly rewrite final-decision input and result digests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh_artifact_digests:
        refresh_artifact_digests()
    if args.refresh_decision_digests:
        refresh_decision_digests()
    errors = validate(
        strict=args.strict,
        require_new_targets_absent=args.check_planned_target_absence,
    )
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    artifacts = load_artifacts()
    print(
        "validated Phase 8 decision package: "
        f"{len(artifacts)} artifacts, "
        f"{len(artifacts['source-ledger.json']['sources'])} sources, "
        "3 single-cloud cases, 6 directed pairs, 6 three-provider placements, "
        "3 workload sizes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
