#!/usr/bin/env python3
"""Generate and verify the additive Six-layer Eventing contract bundle."""

from __future__ import annotations

import argparse
import copy
from decimal import Decimal
import hashlib
import importlib.util
from itertools import product
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCH_ROOT = ROOT / "contracts" / "architecture-profiles"
ARCH_V2 = ARCH_ROOT / "v2"
DEFINITIONS = ARCH_ROOT / "definitions"
FIVE_SCRIPT = ROOT / "scripts" / "sync_five_layer_v2_contracts.py"
EVENT_EVIDENCE = ROOT / "docs" / "research" / "evidence" / "phase_08_eventing"
EVENT_MANIFEST = EVENT_EVIDENCE / "implementation-component-manifest.json"
EVENT_DECISION = EVENT_EVIDENCE / "decision.json"
EVENT_SCENARIOS = EVENT_EVIDENCE / "scenario-inputs.json"
EVENT_PRICING = EVENT_EVIDENCE / "pricing-model-matrix.json"
EVENT_COST_RESULTS = EVENT_EVIDENCE / "scenario-cost-results.json"
EVENT_CALCULATOR = ROOT / "scripts" / "phase_08_eventing" / "calculate_scenarios.py"
SERVICE_DECISION = (
    ROOT
    / "docs"
    / "research"
    / "evidence"
    / "phase_08_service_bundles"
    / "decision.json"
)
RDS_CAPACITY_REGISTRY = (
    ROOT
    / "contracts"
    / "resolved-deployment-specification"
    / "v2"
    / "component-capacity-registry.json"
)
RDS_V2 = ROOT / "contracts" / "resolved-deployment-specification" / "v2"
DEPLOYMENT_MANIFEST_V4 = ROOT / "contracts" / "deployment-manifest" / "v4"
PROFILE_PATH = (
    DEFINITIONS / "profiles" / "six-layer-eventing" / "1" / "profile.json"
)
CATALOG_PATH = (
    DEFINITIONS
    / "component-catalogs"
    / "six-layer-eventing"
    / "1"
    / "catalog.json"
)
MANIFEST_PATH = DEFINITIONS / "six-layer-eventing-v1-manifest.json"
COST_REGISTRY_PATH = DEFINITIONS / "six-layer-eventing-v1-cost-registry.json"
PROVIDERS = ("aws", "azure", "gcp")
REGIONS = {"aws": "eu-central-1", "azure": "westeurope", "gcp": "europe-west1"}
EVENT_CAPABILITIES = (
    "capability.event.envelope",
    "capability.event.routing",
    "capability.event.durable-buffer",
    "capability.event.independent-fanout",
    "capability.event.at-least-once",
    "capability.event.retry",
    "capability.event.dead-letter",
    "capability.event.replay",
    "capability.event.trace-correlation",
    "capability.event.idempotency",
    "capability.event.per-device-ordering",
    "capability.event.schema-rejection",
    "capability.event.observability",
    "capability.event.cross-cloud-transport",
    "capability.event.cost-ownership",
)
REMOVED_DIRECT_EDGES = {
    "edge.ingestion-to-processing",
    "edge.processing-to-ingestion",
    "edge.ingestion-to-hot-storage",
}
EVENT_EDGES: dict[str, tuple[str, str, str, str, str]] = {
    "edge.ingestion-to-eventing": (
        "component.ingestion",
        "port.ingestion.telemetry-event-out",
        "component.eventing",
        "port.eventing.telemetry-in",
        "cost.ingestion-to-eventing",
    ),
    "edge.eventing-to-processing": (
        "component.eventing",
        "port.eventing.telemetry-out",
        "component.processing",
        "port.processing.telemetry-event-in",
        "cost.eventing-to-processing",
    ),
    "edge.processing-to-eventing": (
        "component.processing",
        "port.processing.device-command-out",
        "component.eventing",
        "port.eventing.control-in",
        "cost.processing-to-eventing",
    ),
    "edge.eventing-to-ingestion": (
        "component.eventing",
        "port.eventing.control-out",
        "component.ingestion",
        "port.ingestion.device-command-in",
        "cost.eventing-to-ingestion",
    ),
}
CATALOG_PORTS = {
    "edge.ingestion-to-eventing": ("ingestion.telemetry-event-out", "eventing.telemetry-in"),
    "edge.eventing-to-processing": ("eventing.telemetry-out", "processing.telemetry-event-in"),
    "edge.processing-to-eventing": ("processing.device-command-out", "eventing.control-in"),
    "edge.eventing-to-ingestion": ("eventing.control-out", "ingestion.device-command-in"),
}
INHERITED_IMPLEMENTATION_COMMIT = "c5c6232478d29a9cc3c7d280bdc9ca0e79c47226"
INHERITED_AUDIT_COMMIT = "d4c080f6"
DEPLOYMENT_FIXTURE_ID = "six-layer-aws-azure-eventing-small"
DEPLOYMENT_FIXTURE_RUN_ID = "89287aa5-89b4-55dc-88cb-680f2823da48"


def _load_five() -> ModuleType:
    spec = importlib.util.spec_from_file_location("six_layer_five_contract", FIVE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Five-layer contract generator: {FIVE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FIVE = _load_five()


def _load_event_calculator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "six_layer_eventing_cost_calculator",
        EVENT_CALCULATOR,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Eventing cost calculator: {EVENT_CALCULATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVENT_COST = _load_event_calculator()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def write_json(path: Path, value: object) -> None:
    FIVE.write_json(path, value)


def redigest(document: dict[str, Any], runtime: ModuleType) -> dict[str, Any]:
    document["content_digest"] = runtime.calculate_digest(document)
    return document


def provider_profile_path(provider: str) -> Path:
    return (
        DEFINITIONS
        / "provider-implementations"
        / "six-layer-eventing"
        / "1"
        / provider
        / "1.json"
    )


def five_profile() -> dict[str, Any]:
    return read_json(
        DEFINITIONS / "profiles" / "five-layer-baseline" / "2" / "profile.json"
    )


def five_catalog() -> dict[str, Any]:
    return read_json(
        DEFINITIONS
        / "component-catalogs"
        / "complete-service"
        / "1"
        / "catalog.json"
    )


def five_provider_profile(provider: str) -> dict[str, Any]:
    return read_json(
        DEFINITIONS
        / "provider-implementations"
        / "five-layer-baseline"
        / "2"
        / provider
        / "1.json"
    )


def event_services(provider: str) -> list[dict[str, Any]]:
    manifest = read_json(EVENT_MANIFEST)
    return [
        item
        for item in manifest["service_components"]
        if item["provider"] == provider and item["profile_scope"] == "event_layer"
    ]


def event_rds_component_ids(provider: str) -> list[str]:
    registry = read_json(RDS_CAPACITY_REGISTRY)
    bundle = next(
        item for item in registry["provider_bundles"] if item["provider"] == provider
    )
    source_owned_adapter = {
        "aws": "aws.lambda-event-adapter",
        "azure": "azure.functions-flex-event-adapter",
        "gcp": "gcp.cloud-run-event-adapter",
    }[provider]
    return [*bundle["six_layer_event_components"], source_owned_adapter]


FULL_EVENT_COMPONENTS = {
    "aws": {
        "telemetry": "aws.kinesis-data-streams",
        "control": "aws.sns-fifo",
        "failure": "aws.s3-event-failure-store",
        "runtime": "aws.lambda-event-worker",
        "observability": "aws.cloudwatch",
    },
    "azure": {
        "telemetry_standard": "azure.event-hubs-standard-small-medium",
        "telemetry_large": "azure.event-hubs-dedicated-large",
        "control": "azure.service-bus-standard",
        "runtime": "azure.functions-flex-event-worker",
        "observability": "azure.log-analytics-shared-workspace",
    },
    "gcp": {
        "telemetry": "gcp.pubsub-separated-event-layer-topics",
        "runtime_service": "gcp.cloud-run-event-service-small-medium",
        "runtime_worker": "gcp.cloud-run-worker-pool-fixed-large",
        "observability": "gcp.cloud-logging",
    },
}
EMBEDDED_EVENT_COMPONENTS = {
    "aws": {
        "telemetry": "aws.kinesis-only-for-reviewed-remote-telemetry-edge",
        "control": "aws.sns-fifo-only-for-reviewed-remote-control-edge",
        "runtime": "aws.lambda-event-adapter",
    },
    "azure": {
        "telemetry": "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
        "control": "azure.service-bus-standard",
        "runtime": "azure.functions-flex-event-adapter",
    },
    "gcp": {
        "telemetry": "gcp.pubsub-separated-embedded-topics",
        "control": "gcp.pubsub-separated-embedded-topics",
        "runtime": "gcp.cloud-run-event-adapter",
    },
}
OBSERVABILITY_COMPONENTS = {
    "aws": "aws.cloudwatch",
    "azure": "azure.log-analytics-shared-workspace",
    "gcp": "gcp.cloud-logging",
}
EDGE_ID_BY_ROLE = {
    "ingress-to-eventing": "edge.ingestion-to-eventing",
    "processing-to-eventing": "edge.processing-to-eventing",
    "eventing-to-processing": "edge.eventing-to-processing",
    "eventing-to-ingress": "edge.eventing-to-ingestion",
}


def _provider_from_member(member: str) -> str:
    normalized = member.lower()
    if normalized.startswith(("amazon", "aws")):
        return "aws"
    if normalized.startswith("azure"):
        return "azure"
    if normalized.startswith(("google", "gcp")):
        return "gcp"
    raise RuntimeError(f"Unknown Eventing contribution provider: {member}")


def _full_event_component(
    provider: str,
    size: str,
    contribution_id: str,
) -> str:
    components = FULL_EVENT_COMPONENTS[provider]
    if contribution_id.endswith(".telemetry-log"):
        return components[
            "telemetry_large"
            if provider == "azure" and size == "large"
            else "telemetry_standard"
            if provider == "azure"
            else "telemetry"
        ]
    if contribution_id.endswith(".control-fanout"):
        return components["control"]
    if contribution_id.endswith(".telemetry-dlq"):
        return components["failure"]
    if contribution_id.endswith(".control-delivery-adapter.cloud-run"):
        return components["runtime_service"]
    if ".delivery-adapter" in contribution_id:
        if provider == "gcp":
            return components[
                "runtime_worker" if size == "large" else "runtime_service"
            ]
        return components["runtime"]
    if contribution_id.endswith(".broker"):
        return components["telemetry"]
    if contribution_id.endswith(".observability"):
        return components["observability"]
    raise RuntimeError(f"Unknown Event-Layer contribution: {contribution_id}")


def _bridge_component(
    contribution_id: str,
    *,
    source_provider: str,
    destination_provider: str,
) -> str:
    if ".source-outbox.telemetry-landing" in contribution_id:
        return EMBEDDED_EVENT_COMPONENTS[source_provider]["telemetry"]
    if ".source-outbox.control-landing" in contribution_id:
        return EMBEDDED_EVENT_COMPONENTS[source_provider]["control"]
    if ".destination.telemetry-landing" in contribution_id:
        return EMBEDDED_EVENT_COMPONENTS[destination_provider]["telemetry"]
    if ".destination.control-landing" in contribution_id:
        return EMBEDDED_EVENT_COMPONENTS[destination_provider]["control"]
    if ".forwarder." in contribution_id:
        if source_provider == "gcp" and ".worker-pool" in contribution_id:
            return "gcp.cloud-run-worker-pool-fixed-large"
        return EMBEDDED_EVENT_COMPONENTS[source_provider]["runtime"]
    raise RuntimeError(f"Unknown bridge component contribution: {contribution_id}")


def build_cost_registry() -> dict[str, Any]:
    scenario_document = read_json(EVENT_SCENARIOS)
    pricing_document = read_json(EVENT_PRICING)
    intents = EVENT_COST.intent_map(pricing_document)
    shared = scenario_document["shared_assumptions"]
    scenarios: list[dict[str, Any]] = []
    for scenario in scenario_document["scenarios"]:
        size = str(scenario["scenario_id"]).removeprefix("eventing-").removesuffix(
            "-v1"
        )
        channels = EVENT_COST.derive_channels(scenario, shared)
        placements: list[dict[str, Any]] = []
        for ingestion, eventing, processing in product(PROVIDERS, repeat=3):
            calculated = EVENT_COST.three_provider_result(
                {
                    "ingress_provider": ingestion,
                    "eventing_provider": eventing,
                    "processing_provider": processing,
                    "status": "capability_admissible_live_pending",
                },
                scenario,
                shared,
                channels,
                intents,
                include_event_layer_contributions=True,
            )
            component_amounts: dict[str, Decimal] = {}
            component_contributions: dict[str, list[str]] = {}
            route_amounts: dict[str, Decimal] = {}
            route_contributions: dict[str, list[str]] = {}

            def add_component(component_id: str, contribution: dict[str, Any]) -> None:
                component_amounts[component_id] = component_amounts.get(
                    component_id, Decimal(0)
                ) + Decimal(str(contribution["amount_usd"]))
                component_contributions.setdefault(component_id, []).append(
                    str(contribution["contribution_id"])
                )

            for contribution in calculated["event_layer_cost_contributions"]:
                add_component(
                    _full_event_component(
                        eventing,
                        size,
                        str(contribution["contribution_id"]),
                    ),
                    contribution,
                )

            summaries = {
                str(item["route_role"]): item
                for item in calculated["bridge_route_summaries"]
            }
            for contribution in calculated["bridge_cost_contributions"]:
                contribution_id = str(contribution["contribution_id"])
                if ".bridge-shared.observability" in contribution_id:
                    add_component(
                        OBSERVABILITY_COMPONENTS[
                            _provider_from_member(str(contribution["member"]))
                        ],
                        contribution,
                    )
                    continue
                role = next(
                    (
                        candidate
                        for candidate in EDGE_ID_BY_ROLE
                        if f".{candidate}." in contribution_id
                    ),
                    None,
                )
                if role is None:
                    raise RuntimeError(
                        f"Bridge contribution has no route role: {contribution_id}"
                    )
                edge_id = EDGE_ID_BY_ROLE[role]
                summary = summaries[role]
                if contribution_id.endswith(".egress"):
                    route_amounts[edge_id] = route_amounts.get(
                        edge_id, Decimal(0)
                    ) + Decimal(str(contribution["amount_usd"]))
                    route_contributions.setdefault(edge_id, []).append(
                        contribution_id
                    )
                else:
                    add_component(
                        _bridge_component(
                            contribution_id,
                            source_provider=str(summary["source_provider"]),
                            destination_provider=str(summary["destination_provider"]),
                        ),
                        contribution,
                    )

            component_costs = [
                {
                    "implementation_component_id": component_id,
                    "monthly_amount_usd": EVENT_COST.money(amount),
                    "contribution_ids": sorted(
                        component_contributions[component_id]
                    ),
                }
                for component_id, amount in sorted(component_amounts.items())
            ]
            route_costs = [
                {
                    "edge_id": edge_id,
                    "monthly_transfer_amount_usd": EVENT_COST.money(amount),
                    "contribution_ids": sorted(route_contributions[edge_id]),
                }
                for edge_id, amount in sorted(route_amounts.items())
            ]
            allocated_total = sum(component_amounts.values(), Decimal(0)) + sum(
                route_amounts.values(), Decimal(0)
            )
            expected_total = Decimal(str(calculated["event_scope_total_usd"]))
            if allocated_total != expected_total:
                raise RuntimeError(
                    "Eventing topology allocation does not reconcile for "
                    f"{ingestion}/{eventing}/{processing}/{size}: "
                    f"{allocated_total} != {expected_total}"
                )
            placements.append(
                {
                    "placement_id": calculated["placement_id"],
                    "ingestion_provider": ingestion,
                    "eventing_provider": eventing,
                    "processing_provider": processing,
                    "topology": calculated["topology"],
                    "event_layer_bundle_ref": calculated["event_layer_bundle_ref"],
                    "event_layer_bundle_total_usd": calculated[
                        "event_layer_bundle_total_usd"
                    ],
                    "bridge_addition_total_usd": calculated[
                        "bridge_addition_total_usd"
                    ],
                    "event_scope_total_usd": calculated["event_scope_total_usd"],
                    "component_costs": component_costs,
                    "route_transfer_costs": route_costs,
                }
            )
        scenarios.append(
            {
                "scenario_id": scenario["scenario_id"],
                "placements": placements,
            }
        )
    registry = {
        "schema_version": "six-layer-eventing-topology-cost-registry.v1",
        "currency": "USD",
        "scenario_source_ref": {
            "id": "phase-08-eventing-scenarios",
            "version": "1",
            "digest": file_digest(EVENT_SCENARIOS),
        },
        "pricing_source_ref": {
            "id": "phase-08-eventing-pricing-model",
            "version": "1",
            "digest": file_digest(EVENT_PRICING),
        },
        "reviewed_result_ref": {
            "id": "phase-08-eventing-cost-results",
            "version": "1",
            "digest": file_digest(EVENT_COST_RESULTS),
        },
        "scenarios": scenarios,
    }
    registry["content_digest"] = FIVE.digest(registry)
    return registry


def build_profile(runtime: ModuleType) -> dict[str, Any]:
    profile = copy.deepcopy(five_profile())
    profile.update(
        {
            "profile_id": "six-layer-eventing",
            "profile_version": "1",
            "display_name": "Six-layer Eventing",
            "description": (
                "Five-layer v2 responsibilities with one independent Eventing and "
                "Messaging responsibility for durable routing, fan-out, retry, "
                "dead-letter, replay, observability, and cross-cloud transport."
            ),
            "lifecycle_status": "active",
        }
    )
    for responsibility in profile["responsibilities"]:
        order = responsibility["evaluation_order"]
        if order >= 3:
            responsibility["evaluation_order"] = order + 1
    profile["responsibilities"].append(
        {
            "responsibility_id": "responsibility.eventing",
            "display_name": "Eventing and Messaging",
            "required": True,
            "capability_requirements": list(EVENT_CAPABILITIES),
            "workload_field_refs": ["workload.eventing-scenario"],
            "cost_category_ids": ["cost.eventing"],
            "logical_component_ids": ["component.eventing"],
            "evaluation_order": 3,
        }
    )
    profile["components"].append(
        {
            "component_id": "component.eventing",
            "responsibility_id": "responsibility.eventing",
            "component_kind": "eventing",
            "required": True,
            "required_capability_ids": list(EVENT_CAPABILITIES),
            "input_port_ids": [
                "port.eventing.telemetry-in",
                "port.eventing.control-in",
            ],
            "output_port_ids": [
                "port.eventing.telemetry-out",
                "port.eventing.control-out",
            ],
            "extension_slot_ids": [],
            "cost_owner_ids": ["cost.eventing"],
            "observability_contract_id": "observability.eventing",
        }
    )
    edge_template = next(
        item
        for item in profile["edges"]
        if item["edge_id"] == "edge.ingestion-to-processing"
    )
    profile["edges"] = [
        item
        for item in profile["edges"]
        if item["edge_id"] not in REMOVED_DIRECT_EDGES
    ]
    for edge_id, (source, source_port, destination, destination_port, cost) in EVENT_EDGES.items():
        edge = copy.deepcopy(edge_template)
        edge.update(
            {
                "edge_id": edge_id,
                "source_component_id": source,
                "source_port_id": source_port,
                "destination_component_id": destination,
                "destination_port_id": destination_port,
                "edge_contract_id": "canonical-domain-event.v1",
                "edge_contract_version": "1",
                "cost_owner_ids": [cost],
            }
        )
        profile["edges"].append(edge)
    profile["optimization_slot_ids"].append("eventing")
    profile["graph_policy"]["allowed_cycle_ids"] = [
        "cycle.eventing.ingestion.processing"
    ]
    profile["functional_completeness_rules"] = [
        item
        for item in profile["functional_completeness_rules"]
        if item["capability_id"]
        not in {
            "capability.embedded-domain-event-flow",
            "capability.five-scientific-responsibilities",
            "capability.seven-costed-optimization-slots",
            "capability.six-baseline-flows",
        }
    ]
    profile["functional_completeness_rules"].extend(
        [
            {
                "capability_id": "capability.six-scientific-responsibilities",
                "evidence": "Six-layer responsibility registry",
                "required": True,
            },
            {
                "capability_id": "capability.eight-costed-optimization-slots",
                "evidence": "Seven inherited slots plus Eventing",
                "required": True,
            },
            {
                "capability_id": "capability.independent-eventing-responsibility",
                "evidence": "phase-08-eventing-decision@1",
                "required": True,
            },
            *[
                {
                    "capability_id": capability,
                    "evidence": "phase-08-eventing-decision@1 mandatory capability",
                    "required": True,
                }
                for capability in EVENT_CAPABILITIES
            ],
        ]
    )
    return redigest(profile, runtime)


def six_compatibility(provider: str) -> dict[str, Any]:
    return {
        "architecture_profile_versions": [
            {"id": "six-layer-eventing", "version": "1"}
        ],
        "provider_profile_versions": [
            {
                "id": f"provider-profile.{provider}.six-layer-eventing-v1",
                "version": "1",
            }
        ],
        "deployment_specification_versions": [
            "resolved-deployment-specification.v2"
        ],
    }


def _event_package(provider: str) -> dict[str, Any]:
    source = {
        "aws": "3-cloud-deployer/src/providers/aws/lambda_functions/five-layer-v2",
        "azure": "3-cloud-deployer/src/providers/azure/azure_functions/five-layer-v2",
        "gcp": "3-cloud-deployer/src/providers/gcp/containers/five-layer-v2",
    }[provider]
    included = [
        path.relative_to(ROOT / source).as_posix()
        for path in sorted((ROOT / source).rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    return {
        "artifact_id": f"artifact.platform.{provider}.six-layer-eventing",
        "artifact_version": "1",
        "decision_implementation_ids": [
            item["service_id"] for item in event_services(provider)
        ],
        "repository_source_path": source,
        "platform_handler": f"handler.{provider}.five-layer-v2",
        "digest_policy": "sha256.canonical-source.v1",
        "source_digest": FIVE.package_source_digest(source),
        "included_paths": included,
        "excluded_paths": [],
        "dependency_artifact_refs": [
            {"id": "artifact.shared.phase8-bridge-runtime", "version": "1"}
        ],
        "builder_adapter_id": f"builder.{provider}.five-layer-v2",
        "supported_runtimes": [
            f"runtime.{provider}.five-layer-v2",
            f"runtime.{provider}.six-layer-eventing",
        ],
        "user_source_policy": "platform_only",
        "compatibility": {"component_versions": ["1"], "builder_versions": ["2"]},
    }


def _terraform_output_name(output_id: str) -> str:
    return output_id.removeprefix("output.").replace(".", "_").replace("-", "_")


def _event_component(provider: str) -> dict[str, Any]:
    services = event_services(provider)
    service_ids = sorted({item["service_id"] for item in services})
    resource_addresses = sorted(
        {
            address
            for item in services
            for address in item["terraform"]["resource_ids"]
        }
    )
    input_ids = sorted(
        {
            input_id
            for item in services
            for input_id in item["terraform"]["input_ids"]
        }
    )
    output_ids = sorted(
        {
            output_id
            for item in services
            for output_id in item["terraform"]["output_ids"]
        }
    )
    pricing_refs = sorted(
        {item_id for item in services for item_id in item["pricing_intent_ids"]}
    )
    formula_refs = sorted(
        {item_id for item in services for item_id in item["formula_ids"]}
    )
    def port(port_id: str) -> dict[str, Any]:
        return {
            "port_id": f"catalog.{provider}.port.{port_id}",
            "schema_ref": {"id": "canonical-domain-event.v1", "version": "1"},
            "envelope_ref": {"id": "contract-envelope", "version": "1"},
            "value_type": "json_document",
            "sensitivity": "internal",
            "cardinality": "many",
            "producer_consumer_phase": "runtime",
            "resolution_stage": "catalog",
            "compatibility_version": "1",
        }
    return {
        "deployment_component_id": f"deployment.{provider}.eventing.v1",
        "component_version": "1",
        "provider": provider,
        "logical_component_ids": ["component.eventing"],
        "decision_implementation_ids": [
            item["service_id"] for item in services
        ],
        "service_id": f"{provider}.eventing.v1",
        "service_ids": service_ids,
        "component_kind": "managed_service",
        "package_artifact_ref": {
            "id": f"artifact.platform.{provider}.six-layer-eventing",
            "version": "1",
        },
        "terraform_binding": {
            "resource_addresses": resource_addresses,
            "module_addresses": [],
            "allowed_input_variable_ids": input_ids,
            "input_bindings": [],
            "outputs": [
                {
                    "output_id": output_id,
                    "terraform_output": _terraform_output_name(output_id),
                    "sensitive": False,
                }
                for output_id in output_ids
            ],
            "dependency_keys": [],
        },
        "runtime_contract": {
            "provider_runtime_id": f"runtime.{provider}.six-layer-eventing",
            "platform_handler_adapter_id": f"adapter.{provider}.event-delivery.v1",
            "timeout_seconds_min": 1,
            "timeout_seconds_max": 900,
            "memory_mb_min": 128,
            "memory_mb_max": 32768,
            "trigger_adapter_id": f"trigger.{provider}.six-layer-eventing",
            "package_layout_id": f"package-layout.{provider}.six-layer-eventing",
            "user_override_allowed": False,
        },
        "configuration_schema_ref": {
            "id": f"configuration.{provider}.eventing.v1",
            "version": "1",
        },
        "input_ports": [port("eventing.telemetry-in"), port("eventing.control-in")],
        "output_ports": [port("eventing.telemetry-out"), port("eventing.control-out")],
        "required_permission_capabilities": [f"{provider}_thesis_demo_v2"],
        "pricing_model_refs": pricing_refs,
        "formula_refs": formula_refs,
        "deployment_specification_bindings": [
            {
                "specification_schema_version": "resolved-deployment-specification.v2",
                "component_id": service_id,
                "slot_id": "eventing",
            }
            for service_id in event_rds_component_ids(provider)
        ],
        "extension_slot_refs": [],
        "error_contract_ref": {"id": "architecture-runtime-errors", "version": "1"},
        "observability_contract_ref": {"id": "observability.eventing", "version": "1"},
        "cleanup_contract_ref": {"id": "cleanup.eventing", "version": "1"},
        "compatibility": six_compatibility(provider),
    }


def _catalog_component_id(provider: str, logical: str) -> str:
    if logical == "component.eventing":
        return f"deployment.{provider}.eventing.v1"
    return FIVE.deployment_component_id(provider, logical)


def _catalog_port(provider: str, suffix: str) -> str:
    return f"catalog.{provider}.port.{suffix}"


def _event_edge_implementation(
    source_provider: str,
    destination_provider: str,
    edge_id: str,
) -> dict[str, Any]:
    source_logical, _, destination_logical, _, _ = EVENT_EDGES[edge_id]
    source_suffix, destination_suffix = CATALOG_PORTS[edge_id]
    local = source_provider == destination_provider
    source_component = _catalog_component_id(source_provider, source_logical)
    destination_component = _catalog_component_id(
        destination_provider, destination_logical
    )
    provider_refs = [
        {
            "id": f"provider-profile.{provider}.six-layer-eventing-v1",
            "version": "1",
        }
        for provider in sorted({source_provider, destination_provider})
    ]
    return {
        "edge_implementation_id": (
            f"edge-implementation.{source_provider}-to-{destination_provider}."
            f"{edge_id.removeprefix('edge.')}.eventing-v1"
        ),
        "edge_implementation_version": "1",
        "provider": source_provider,
        "decision_edge_ids": [
            f"decision.event-route.{source_provider}-to-{destination_provider}."
            f"{edge_id.removeprefix('edge.')}"
        ],
        "logical_edge_ids": [edge_id],
        "mechanism": "provider_native_trigger" if local else "cross_provider_adapter",
        "source_component_ids": [source_component],
        "destination_component_ids": [destination_component],
        "source_output_port_id": _catalog_port(source_provider, source_suffix),
        "destination_input_port_id": _catalog_port(
            destination_provider, destination_suffix
        ),
        "terraform_binding": {
            "source_output_id": f"output.{source_provider}.eventing-edge-source",
            "destination_input_id": _catalog_port(
                destination_provider, destination_suffix
            ),
            "dependency_keys": [],
        },
        "transfer_route_class": (
            "same_provider_same_region" if local else "cross_provider"
        ),
        "payload_contract_ref": {
            "id": "canonical-domain-event.v1",
            "version": "1",
        },
        "delivery_requirements": {
            "dead_letter_policy": "provider_managed",
            "idempotency": "consumer_deduplicated",
            "mode": "asynchronous",
            "ordering": "per_entity",
            "replay": "bounded",
            "retry_policy": "provider_managed_bounded",
            "timeout_policy": "not_applicable",
        },
        "trust_contract_ref": {
            "id": "trust.workload-identity-federation",
            "version": "1",
        },
        "pricing_model_refs": [
            f"pricing.eventing.transfer.{source_provider}-to-{destination_provider}.v1"
        ],
        "formula_refs": ["formula.phase-08-eventing"],
        "required_permission_capabilities": [
            f"{source_provider}_thesis_demo_v2"
        ],
        "glue_component_ids": [] if local else [source_component],
        "error_contract_ref": {
            "id": "architecture-runtime-errors",
            "version": "1",
        },
        "observability_contract_ref": {
            "id": "observability.eventing",
            "version": "1",
        },
        "compatibility": {
            "architecture_profile_versions": [
                {"id": "six-layer-eventing", "version": "1"}
            ],
            "provider_profile_versions": provider_refs,
            "deployment_specification_versions": [
                "resolved-deployment-specification.v2"
            ],
        },
    }


def build_catalog(
    runtime: ModuleType,
    profile: dict[str, Any],
) -> dict[str, Any]:
    catalog = copy.deepcopy(five_catalog())
    catalog.update(
        {
            "catalog_id": "six-layer-eventing-component-catalog",
            "catalog_version": "1",
            "lifecycle_status": "active",
        }
    )
    for component in catalog["components"]:
        component["compatibility"] = six_compatibility(component["provider"])
    valid_edge_ids = {item["edge_id"] for item in profile["edges"]}
    catalog["edge_implementations"] = [
        item
        for item in catalog["edge_implementations"]
        if set(item["logical_edge_ids"]).issubset(valid_edge_ids)
    ]
    for edge in catalog["edge_implementations"]:
        providers = sorted(
            {
                component_id.split(".")[1]
                for component_id in (
                    *edge["source_component_ids"],
                    *edge["destination_component_ids"],
                )
            }
        )
        edge["compatibility"] = {
            "architecture_profile_versions": [
                {"id": "six-layer-eventing", "version": "1"}
            ],
            "provider_profile_versions": [
                {
                    "id": f"provider-profile.{provider}.six-layer-eventing-v1",
                    "version": "1",
                }
                for provider in providers
            ],
            "deployment_specification_versions": [
                "resolved-deployment-specification.v2"
            ],
        }
    catalog["package_artifacts"].extend(
        _event_package(provider) for provider in PROVIDERS
    )
    catalog["components"].extend(_event_component(provider) for provider in PROVIDERS)
    catalog["edge_implementations"].extend(
        _event_edge_implementation(source, destination, edge_id)
        for source in PROVIDERS
        for destination in PROVIDERS
        for edge_id in EVENT_EDGES
    )
    referenced_inputs: dict[str, set[str]] = {}
    referenced_outputs: dict[str, set[str]] = {}
    for edge in catalog["edge_implementations"]:
        for component_id in edge["source_component_ids"]:
            referenced_outputs.setdefault(component_id, set()).add(
                edge["source_output_port_id"]
            )
        for component_id in edge["destination_component_ids"]:
            referenced_inputs.setdefault(component_id, set()).add(
                edge["destination_input_port_id"]
            )
    for component in catalog["components"]:
        component_id = component["deployment_component_id"]
        component["input_ports"] = [
            port
            for port in component["input_ports"]
            if port["port_id"] in referenced_inputs.get(component_id, set())
        ]
        component["output_ports"] = [
            port
            for port in component["output_ports"]
            if port["port_id"] in referenced_outputs.get(component_id, set())
        ]
    return redigest(catalog, runtime)


def _local_event_edge_mapping(provider: str, edge_id: str) -> dict[str, Any]:
    source_logical, _, destination_logical, _, cost_owner = EVENT_EDGES[edge_id]
    source_suffix, destination_suffix = CATALOG_PORTS[edge_id]
    return {
        "edge_id": edge_id,
        "edge_implementation_id": (
            f"edge-implementation.{provider}-to-{provider}."
            f"{edge_id.removeprefix('edge.')}.eventing-v1"
        ),
        "source_deployment_component_ids": [
            _catalog_component_id(provider, source_logical)
        ],
        "destination_deployment_component_ids": [
            _catalog_component_id(provider, destination_logical)
        ],
        "mechanism": "provider_native_trigger",
        "catalog_input_port_id": _catalog_port(provider, destination_suffix),
        "catalog_output_port_id": _catalog_port(provider, source_suffix),
        "transfer_route_class": "same_provider_same_region",
        "cost_owner_ids": [cost_owner],
    }


def build_provider_profile(
    provider: str,
    profile: dict[str, Any],
    catalog: dict[str, Any],
    runtime: ModuleType,
) -> dict[str, Any]:
    document = copy.deepcopy(five_provider_profile(provider))
    document.update(
        {
            "implementation_profile_id": (
                f"provider-profile.{provider}.six-layer-eventing-v1"
            ),
            "implementation_profile_version": "1",
            "architecture_profile_ref": {
                "id": "six-layer-eventing",
                "version": "1",
                "digest": profile["content_digest"],
            },
            "lifecycle_status": "active",
            "supported": True,
            "unsupported_reasons": [],
        }
    )
    for mapping in document["component_mappings"]:
        logical = mapping["component_id"]
        required = next(
            item["required_capability_ids"]
            for item in profile["components"]
            if item["component_id"] == logical
        )
        mapping["required_capability_ids"] = required
        mapping["provided_capability_ids"] = sorted(
            set(mapping["provided_capability_ids"]) | set(required)
        )
    event_component = next(
        item
        for item in catalog["components"]
        if item["deployment_component_id"] == f"deployment.{provider}.eventing.v1"
    )
    document["component_mappings"].append(
        {
            "component_id": "component.eventing",
            "deployment_component_candidates": [
                f"deployment.{provider}.eventing.v1"
            ],
            "required_capability_ids": list(EVENT_CAPABILITIES),
            "provided_capability_ids": list(EVENT_CAPABILITIES),
            "service_model_refs": [
                f"service-model.{provider}.{service_id}"
                for service_id in event_component["service_ids"]
            ],
            "formula_refs": event_component["formula_refs"],
            "supported_region_ids": [f"region.{provider}.{REGIONS[provider]}"],
            "deployment_specification_component_ids": [
                binding["component_id"]
                for binding in event_component["deployment_specification_bindings"]
            ],
            "deployment_specification_slot_ids": ["eventing"],
        }
    )
    valid_edge_ids = {item["edge_id"] for item in profile["edges"]}
    document["edge_mappings"] = [
        item for item in document["edge_mappings"] if item["edge_id"] in valid_edge_ids
    ]
    document["edge_mappings"].extend(
        _local_event_edge_mapping(provider, edge_id) for edge_id in EVENT_EDGES
    )
    document["capability_claims"]["provided_capability_ids"] = sorted(
        set(document["capability_claims"]["provided_capability_ids"])
        | set(EVENT_CAPABILITIES)
        | {
            "capability.six-scientific-responsibilities",
            "capability.eight-costed-optimization-slots",
            "capability.independent-eventing-responsibility",
        }
    )
    document["capability_claims"]["missing_capability_ids"] = []
    document["compatibility"]["compatible_catalog_versions"] = [
        {"id": catalog["catalog_id"], "version": catalog["catalog_version"]}
    ]
    return redigest(document, runtime)


def build_manifest(
    profile: dict[str, Any],
    catalog: dict[str, Any],
    providers: dict[str, dict[str, Any]],
    cost_registry: dict[str, Any],
) -> dict[str, Any]:
    five_manifest = read_json(DEFINITIONS / "five-layer-v2-manifest.json")
    service = read_json(SERVICE_DECISION)
    manifest = {
        "manifest_version": "six-layer-eventing-architecture-definitions.v1",
        "activation_status": "active",
        "inherited_implementation_commit": INHERITED_IMPLEMENTATION_COMMIT,
        "inherited_audit_commit": INHERITED_AUDIT_COMMIT,
        "inherited_profile_ref": five_manifest["profile_ref"],
        "inherited_catalog_ref": five_manifest["catalog_ref"],
        "profile_ref": {
            "id": profile["profile_id"],
            "version": profile["profile_version"],
            "digest": profile["content_digest"],
        },
        "provider_profile_refs": [
            {
                "provider": provider,
                "id": document["implementation_profile_id"],
                "version": document["implementation_profile_version"],
                "digest": document["content_digest"],
            }
            for provider, document in providers.items()
        ],
        "catalog_ref": {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
        },
        "eventing_decision_ref": {
            "id": "phase-08-eventing-decision",
            "version": "1",
            "digest": file_digest(EVENT_DECISION),
        },
        "eventing_implementation_manifest_ref": {
            "id": "phase-08-eventing-implementation",
            "version": "1",
            "digest": file_digest(EVENT_MANIFEST),
        },
        "service_decision_ref": {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": service["package_digest"],
        },
        "topology_cost_registry_ref": {
            "id": "six-layer-eventing-topology-cost-registry",
            "version": "1",
            "digest": cost_registry["content_digest"],
        },
        "workload_ref": five_manifest["workload_ref"],
        "supported_eventing_placements": [
            f"{provider}-eventing" for provider in PROVIDERS
        ],
        "supported_directed_provider_pairs": [
            f"{source}-to-{destination}"
            for source in PROVIDERS
            for destination in PROVIDERS
            if source != destination
        ],
    }
    manifest["content_digest"] = FIVE.digest(manifest)
    return manifest


def _deployment_fixture(
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build one real deterministic Six-layer RTA/RDS/Manifest-v4 fixture."""

    optimizer_root = ROOT / "2-twin2clouds"
    sys.path.insert(0, str(optimizer_root))
    try:
        from backend.architecture_profiles.five_layer_v2_pricing import (
            FiveLayerV2CatalogCostLedgerResolver,
        )
        from backend.architecture_profiles.registry import (
            ArchitectureProfileRegistry,
        )
        from backend.architecture_profiles.six_layer_optimizer import (
            optimize_six_layer_eventing_v1,
        )

        pricing_root = optimizer_root / "json" / "pricing_catalog_baselines"
        pricing_manifest = read_json(pricing_root / "baseline.json")
        pricing: dict[str, dict[str, Any]] = {}
        evidence: dict[str, dict[str, str]] = {}
        for provider, reference in pricing_manifest["catalogs"].items():
            snapshot = read_json(
                pricing_root
                / provider
                / reference["pricing_region"]
                / "snapshots"
                / f"{reference['snapshot_id']}.json"
            )
            pricing[provider] = snapshot["pricing"]
            evidence[provider] = {
                "id": reference["snapshot_id"],
                "version": "1",
                "digest": reference["content_digest"],
                "provider": provider,
                "currency": "USD",
            }
        resolver = FiveLayerV2CatalogCostLedgerResolver(pricing)
        target = {
            "component.ingestion": "aws",
            "component.processing": "aws",
            "component.eventing": "azure",
        }

        def force_target(specification, assignment, workload):
            ledger = copy.deepcopy(
                resolver.resolve(specification, assignment, workload)
            )
            if any(assignment[logical] != provider for logical, provider in target.items()):
                component_quote = ledger["component_costs"][0]
                component_quote["monthly_amount"] = str(
                    Decimal(component_quote["monthly_amount"])
                    + Decimal("1000000000")
                )
            return ledger

        optimizer_registry = ArchitectureProfileRegistry(
            profile_id="six-layer-eventing",
            profile_version="1",
        )
        workload = read_json(
            ROOT
            / "contracts"
            / "five-layer-workload"
            / "v2"
            / "fixtures"
            / "valid"
            / "core-small.json"
        )
        configuration_digest = "sha256:" + hashlib.sha256(b"{}").hexdigest()
        optimized = optimize_six_layer_eventing_v1(
            calculation_run_id=DEPLOYMENT_FIXTURE_RUN_ID,
            architecture_profile={
                "profileId": profile["profile_id"],
                "profileVersion": profile["profile_version"],
                "contentDigest": profile["content_digest"],
            },
            extension_bindings=[
                {
                    "slotId": "processor.telemetry",
                    "slotVersion": "1",
                    "artifactId": "artifact.user.processor.example",
                    "artifactDigest": "sha256:" + ("1" * 64),
                    "configurationDigest": configuration_digest,
                }
            ],
            workload=workload,
            pricing_evidence_refs=evidence,
            cost_ledger_resolver=force_target,
            providers=PROVIDERS,
            registry=optimizer_registry,
        )
    finally:
        sys.path.remove(str(optimizer_root))

    architecture = json.loads(json.dumps(optimized.resolved_architecture))
    specification = json.loads(json.dumps(optimized.deployment_specification))
    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in architecture["component_assignments"]
    }
    provider_keys = {
        "component.ingestion": "layer_1_provider",
        "component.processing": "layer_2_provider",
        "component.hot-storage": "layer_3_hot_provider",
        "component.cool-storage": "layer_3_cold_provider",
        "component.archive-storage": "layer_3_archive_provider",
        "component.twin-state": "layer_4_provider",
        "component.visualization": "layer_5_provider",
    }
    providers = {
        provider_key: assignment[logical]
        for logical, provider_key in provider_keys.items()
    }
    used_providers = sorted(set(assignment.values()))
    manifest = {
        "manifest_version": "4.0",
        "generated_at": "2026-08-11T00:00:00Z",
        "producer": "twin2multicloud_backend",
        "package": {
            "format": "deployer-project-zip",
            "files": [
                "config.json",
                "config_credentials.json",
                "config_events.json",
                "config_iot_devices.json",
                "config_providers.json",
            ],
            "required_files": [
                "config.json",
                "config_iot_devices.json",
                "config_events.json",
                "config_credentials.json",
                "config_providers.json",
            ],
            "secret_bearing_files": ["config_credentials.json"],
        },
        "twin": {
            "id": None,
            "name": "Six-layer AWS Azure Eventing Small",
            "resource_name": "six-layer-aws-azure-eventing-small",
        },
        "providers": providers,
        "calculation_run_id": specification["calculation_run_id"],
        "resolved_twin_architecture_digest": architecture["content_digest"],
        "resolved_twin_architecture": architecture,
        "resolved_deployment_specification_digest": specification["digest"],
        "resolved_deployment_specification": specification,
        "credentials": {
            "providers": used_providers,
            "sources": {
                provider: "cloud_connection" for provider in used_providers
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
            "terraform_input_contract_version": "graph-terraform-inputs.v1",
        },
        "extensions": {"binding_index": None, "bindings": []},
    }
    return architecture, specification, manifest


def generate_deployment_fixture(
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> None:
    architecture, specification, manifest = _deployment_fixture(profile, catalog)
    write_json(
        ARCH_V2 / "fixtures" / "valid" / f"{DEPLOYMENT_FIXTURE_ID}-resolved.json",
        architecture,
    )
    write_json(
        RDS_V2 / "fixtures" / "valid" / f"{DEPLOYMENT_FIXTURE_ID}.json",
        specification,
    )
    write_json(
        DEPLOYMENT_MANIFEST_V4
        / "fixtures"
        / "valid"
        / f"{DEPLOYMENT_FIXTURE_ID}.json",
        manifest,
    )


def generate() -> None:
    FIVE.generate_v2_schemas()
    base_profile = five_profile()
    registry = FIVE.build_semantic_registry(base_profile)
    write_json(ARCH_V2 / "semantic-registry.json", registry)
    runtime = FIVE.load_v2_runtime()
    profile = build_profile(runtime)
    catalog = build_catalog(runtime, profile)
    providers = {
        provider: build_provider_profile(provider, profile, catalog, runtime)
        for provider in PROVIDERS
    }
    cost_registry = build_cost_registry()
    write_json(PROFILE_PATH, profile)
    write_json(CATALOG_PATH, catalog)
    for provider, document in providers.items():
        write_json(provider_profile_path(provider), document)
    write_json(COST_REGISTRY_PATH, cost_registry)
    write_json(
        MANIFEST_PATH,
        build_manifest(profile, catalog, providers, cost_registry),
    )
    generate_deployment_fixture(profile, catalog)
    (ARCH_V2 / "README.md").write_text(
        "# Architecture Profile Contracts v2\n\n"
        "Additive Five-layer v2 and Six-layer Eventing schemas with strict "
        "closed-world definitions. Historical v1 bytes remain unchanged. Both "
        "new profiles are active for offline evaluation; explicit supervised "
        "live gates still block deployment. Generated by the Five-layer and "
        "Six-layer synchronizers; do not edit generated definitions by hand.\n",
        encoding="utf-8",
    )


def load_bundle() -> tuple[
    ModuleType,
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    runtime = FIVE.load_v2_runtime()
    profile = read_json(PROFILE_PATH)
    catalog = read_json(CATALOG_PATH)
    providers = {provider: read_json(provider_profile_path(provider)) for provider in PROVIDERS}
    registry = read_json(ARCH_V2 / "semantic-registry.json")
    return runtime, profile, catalog, providers, registry


def validate_source() -> None:
    runtime, profile, catalog, providers, registry = load_bundle()
    linked = [registry, five_profile(), profile, *providers.values(), catalog]
    try:
        runtime.validate_bundle(linked, bundle_root=ARCH_V2)
    except runtime.ContractError as exc:
        raise RuntimeError(f"{exc.code} at {exc.path}: {exc}") from exc
    if len(profile["responsibilities"]) != 6:
        raise RuntimeError("Six-layer profile must expose exactly six responsibilities")
    if {item["component_id"] for item in profile["components"]} - {
        item["component_id"] for item in five_profile()["components"]
    } != {"component.eventing"}:
        raise RuntimeError("Six-layer profile delta is not exactly component.eventing")
    if {item["edge_id"] for item in profile["edges"] if "eventing" in item["edge_id"]} != set(EVENT_EDGES):
        raise RuntimeError("Six-layer Eventing edge set drifted")
    event_components = [
        item for item in catalog["components"] if item["logical_component_ids"] == ["component.eventing"]
    ]
    if {item["provider"] for item in event_components} != set(PROVIDERS):
        raise RuntimeError("Eventing catalog does not contain all provider bundles")
    event_edges = [
        item
        for item in catalog["edge_implementations"]
        if item["logical_edge_ids"][0] in EVENT_EDGES
    ]
    if len(event_edges) != len(PROVIDERS) * len(PROVIDERS) * len(EVENT_EDGES):
        raise RuntimeError("Eventing catalog directed edge matrix is incomplete")
    for item in event_edges:
        local = item["transfer_route_class"] == "same_provider_same_region"
        if local != (not item["glue_component_ids"]):
            raise RuntimeError("Local/cross-cloud Eventing bridge ownership drifted")
    manifest = read_json(MANIFEST_PATH)
    supplied = manifest.pop("content_digest")
    if supplied != FIVE.digest(manifest):
        raise RuntimeError("Six-layer definition manifest digest drifted")
    if manifest["eventing_decision_ref"]["digest"] != file_digest(EVENT_DECISION):
        raise RuntimeError("Eventing decision digest drifted")
    if manifest["eventing_implementation_manifest_ref"]["digest"] != file_digest(EVENT_MANIFEST):
        raise RuntimeError("Eventing implementation manifest digest drifted")
    cost_registry = read_json(COST_REGISTRY_PATH)
    supplied_registry_digest = cost_registry.pop("content_digest")
    if supplied_registry_digest != FIVE.digest(cost_registry):
        raise RuntimeError("Six-layer topology cost registry digest drifted")
    if manifest["topology_cost_registry_ref"]["digest"] != supplied_registry_digest:
        raise RuntimeError("Six-layer topology cost registry manifest binding drifted")
    if (
        cost_registry["schema_version"]
        != "six-layer-eventing-topology-cost-registry.v1"
        or cost_registry["currency"] != "USD"
        or len(cost_registry["scenarios"]) != 3
        or any(len(item["placements"]) != 27 for item in cost_registry["scenarios"])
    ):
        raise RuntimeError("Six-layer topology cost registry coverage drifted")
    if cost_registry["reviewed_result_ref"]["digest"] != file_digest(EVENT_COST_RESULTS):
        raise RuntimeError("Reviewed Eventing result binding drifted")

    architecture = read_json(
        ARCH_V2
        / "fixtures"
        / "valid"
        / f"{DEPLOYMENT_FIXTURE_ID}-resolved.json"
    )
    specification = read_json(
        RDS_V2 / "fixtures" / "valid" / f"{DEPLOYMENT_FIXTURE_ID}.json"
    )
    deployment_manifest = read_json(
        DEPLOYMENT_MANIFEST_V4
        / "fixtures"
        / "valid"
        / f"{DEPLOYMENT_FIXTURE_ID}.json"
    )
    runtime.validate_document(
        architecture,
        bundle_root=ARCH_V2,
        linked_documents=linked,
    )
    specification_errors = list(
        FIVE.Draft202012Validator(
            read_json(RDS_V2 / "schema.json"),
            format_checker=FIVE.FormatChecker(),
        ).iter_errors(specification)
    )
    manifest_errors = list(
        FIVE.Draft202012Validator(
            read_json(DEPLOYMENT_MANIFEST_V4 / "schema.json"),
            format_checker=FIVE.FormatChecker(),
        ).iter_errors(deployment_manifest)
    )
    if specification_errors or specification["digest"] != FIVE.rds_digest(specification):
        raise RuntimeError("Six-layer deployment specification fixture drifted")
    if manifest_errors:
        raise RuntimeError("Six-layer deployment manifest fixture drifted")
    expected_profile_ref = {
        "id": profile["profile_id"],
        "version": profile["profile_version"],
        "digest": profile["content_digest"],
    }
    expected_catalog_ref = {
        "id": catalog["catalog_id"],
        "version": catalog["catalog_version"],
        "digest": catalog["content_digest"],
    }
    if (
        architecture["architecture_profile_ref"] != expected_profile_ref
        or specification["architecture_profile_ref"] != expected_profile_ref
        or deployment_manifest["compatibility"]["component_catalog_ref"]
        != expected_catalog_ref
        or len(architecture["component_assignments"]) != 8
        or len(architecture["resolved_edges"]) != 9
        or not any(
            item["logical_component_id"] == "component.eventing"
            for item in architecture["component_assignments"]
        )
    ):
        raise RuntimeError("Six-layer deployment fixture identity drifted")


def synchronize() -> None:
    FIVE.synchronize()


def check() -> None:
    FIVE.validate_source()
    validate_source()
    FIVE.check_tree(ARCH_ROOT, FIVE.ARCH_TARGETS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.generate or args.sync or args.check):
        parser.error("at least one action is required")
    try:
        if args.generate:
            generate()
        validate_source()
        if args.sync:
            synchronize()
        if args.check:
            check()
    except (RuntimeError, FIVE.ContractError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    profile = read_json(PROFILE_PATH)
    catalog = read_json(CATALOG_PATH)
    print(
        "six-layer-eventing-contracts: OK "
        f"(profile={profile['content_digest']}, catalog={catalog['content_digest']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
