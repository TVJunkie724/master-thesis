#!/usr/bin/env python3
"""Generate, validate, synchronize, and drift-check architecture-profile v1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_NAME = "architecture-profiles"
SOURCE_ROOT = ROOT / "contracts" / CONTRACT_NAME
SOURCE_V1 = SOURCE_ROOT / "v1"
VALID_ROOT = SOURCE_V1 / "fixtures" / "valid"
INVALID_ROOT = SOURCE_V1 / "fixtures" / "invalid"
GENERATED_TARGETS = (
    ROOT / "2-twin2clouds" / "backend" / "contracts" / "generated" / CONTRACT_NAME,
    ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / CONTRACT_NAME,
    ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated" / CONTRACT_NAME,
)
SCHEMA_FILES = (
    "architecture-profile.schema.json",
    "provider-implementation-profile.schema.json",
    "deployment-component-catalog.schema.json",
    "resolved-twin-architecture.schema.json",
    "semantic-registry.schema.json",
)
MANDATORY_VALID_FIXTURES = frozenset(
    {
        "five-layer-baseline-profile.json",
        "aws-baseline-provider-profile.json",
        "baseline-component-catalog.json",
        "mixed-baseline-resolved-architecture.json",
    }
)
MANDATORY_INVALID_FIXTURES = {
    "unknown-version.json": "ARCH_VERSION_UNSUPPORTED",
    "duplicate-id.json": "ARCH_DUPLICATE_ID",
    "unresolved-reference.json": "ARCH_REFERENCE_UNRESOLVED",
    "illegal-cycle.json": "ARCH_GRAPH_CYCLE_FORBIDDEN",
    "capability-mismatch.json": "ARCH_CAPABILITY_INCOMPLETE",
    "secret-like-field.json": "ARCH_SECRET_FIELD_FORBIDDEN",
    "digest-tamper.json": "ARCH_DIGEST_MISMATCH",
}
ERROR_CODES = (
    "ARCH_BUNDLE_INCOMPATIBLE",
    "ARCH_CAPABILITY_INCOMPLETE",
    "ARCH_COMPONENT_UNAVAILABLE",
    "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
    "ARCH_DIGEST_MISMATCH",
    "ARCH_DUPLICATE_ID",
    "ARCH_EDGE_UNAVAILABLE",
    "ARCH_EXTENSION_BINDING_INVALID",
    "ARCH_GRAPH_CYCLE_FORBIDDEN",
    "ARCH_REFERENCE_UNRESOLVED",
    "ARCH_SCHEMA_INVALID",
    "ARCH_SECRET_FIELD_FORBIDDEN",
    "ARCH_VERSION_UNSUPPORTED",
)
LOGICAL_COMPONENTS = (
    ("component.ingestion", "responsibility.ingestion", "ingress", "l1_ingestion"),
    ("component.processing", "responsibility.processing", "processor", "l2_processing"),
    ("component.hot-storage", "responsibility.storage", "storage", "l3_hot_storage"),
    ("component.cool-storage", "responsibility.storage", "storage", "l3_cool_storage"),
    (
        "component.archive-storage",
        "responsibility.storage",
        "storage",
        "l3_archive_storage",
    ),
    (
        "component.twin-state",
        "responsibility.twin-state",
        "twin_state",
        "l4_twin_state",
    ),
    (
        "component.visualization",
        "responsibility.visualization",
        "visualization",
        "l5_visualization",
    ),
)
LOGICAL_EDGES = (
    (
        "edge.ingestion-to-processing",
        "component.ingestion",
        "port.ingestion.telemetry-out",
        "component.processing",
        "port.processing.telemetry-in",
        "provider_native_trigger",
        "asynchronous",
    ),
    (
        "edge.processing-to-hot-storage",
        "component.processing",
        "port.processing.telemetry-out",
        "component.hot-storage",
        "port.hot-storage.write-in",
        "provider_native_trigger",
        "asynchronous",
    ),
    (
        "edge.hot-to-cool-storage",
        "component.hot-storage",
        "port.hot-storage.transition-out",
        "component.cool-storage",
        "port.cool-storage.write-in",
        "source_owned_transition_runtime",
        "asynchronous",
    ),
    (
        "edge.cool-to-archive-storage",
        "component.cool-storage",
        "port.cool-storage.transition-out",
        "component.archive-storage",
        "port.archive-storage.write-in",
        "source_owned_transition_runtime",
        "asynchronous",
    ),
    (
        "edge.hot-storage-to-twin-state",
        "component.hot-storage",
        "port.hot-storage.twin-update-out",
        "component.twin-state",
        "port.twin-state.update-in",
        "provider_native_trigger",
        "asynchronous",
    ),
    (
        "edge.twin-state-to-visualization",
        "component.twin-state",
        "port.twin-state.query-out",
        "component.visualization",
        "port.visualization.query-in",
        "typed_synchronous_api",
        "synchronous",
    ),
)
PORTS_BY_COMPONENT = {
    "component.ingestion": (
        (),
        ("port.ingestion.telemetry-out",),
    ),
    "component.processing": (
        ("port.processing.telemetry-in",),
        ("port.processing.telemetry-out",),
    ),
    "component.hot-storage": (
        ("port.hot-storage.write-in",),
        (
            "port.hot-storage.transition-out",
            "port.hot-storage.twin-update-out",
        ),
    ),
    "component.cool-storage": (
        ("port.cool-storage.write-in",),
        ("port.cool-storage.transition-out",),
    ),
    "component.archive-storage": (
        ("port.archive-storage.write-in",),
        (),
    ),
    "component.twin-state": (
        ("port.twin-state.update-in",),
        ("port.twin-state.query-out",),
    ),
    "component.visualization": (
        ("port.visualization.query-in",),
        (),
    ),
}
RESPONSIBILITIES = (
    (
        "responsibility.ingestion",
        "Ingestion",
        ("component.ingestion",),
        1,
    ),
    (
        "responsibility.processing",
        "Processing",
        ("component.processing",),
        2,
    ),
    (
        "responsibility.storage",
        "Storage",
        (
            "component.hot-storage",
            "component.cool-storage",
            "component.archive-storage",
        ),
        3,
    ),
    (
        "responsibility.twin-state",
        "Twin state",
        ("component.twin-state",),
        4,
    ),
    (
        "responsibility.visualization",
        "Visualization",
        ("component.visualization",),
        5,
    ),
)
PROVIDER_CONFIG = {
    "aws": {
        "profile_id": "provider-profile.aws.baseline",
        "region": "eu-central-1",
        "region_id": "region.aws.eu-central-1",
        "service_prefix": "aws",
        "deployment_components": {
            "component.ingestion": ("l1.aws.iot_core", "l1.aws.dispatcher_lambda"),
            "component.processing": (
                "l2.aws.eventbridge",
                "l2.aws.processing_lambdas",
                "l2.aws.step_functions",
            ),
            "component.hot-storage": (
                "l3_hot.aws.dynamodb",
                "l3_hot.aws.reader_lambdas",
            ),
            "component.cool-storage": ("l3_cool.aws.s3",),
            "component.archive-storage": ("l3_archive.aws.s3",),
            "component.twin-state": (
                "l4.aws.connector_lambda",
                "l4.aws.twinmaker",
            ),
            "component.visualization": ("l5.aws.managed_grafana",),
        },
    },
    "azure": {
        "profile_id": "provider-profile.azure.baseline",
        "region": "westeurope",
        "region_id": "region.azure.westeurope",
        "service_prefix": "azure",
        "deployment_components": {
            "component.ingestion": (
                "l1.azure.event_grid",
                "l1.azure.function_plan",
                "l1.azure.iot_hub",
            ),
            "component.processing": (
                "l2.azure.event_grid",
                "l2.azure.function_plan",
                "l2.azure.logic_apps",
            ),
            "component.hot-storage": (
                "l3_hot.azure.cosmos_db",
                "l3_hot.azure.function_plan",
            ),
            "component.cool-storage": ("l3_cool.azure.blob_storage",),
            "component.archive-storage": ("l3_archive.azure.blob_storage",),
            "component.twin-state": (
                "l4.azure.digital_twins",
                "l4.azure.pusher_function",
            ),
            "component.visualization": ("l5.azure.managed_grafana",),
        },
    },
}


def _load_runtime() -> ModuleType:
    path = SOURCE_V1 / "runtime.py"
    spec = importlib.util.spec_from_file_location(
        "_architecture_profile_contract_runtime_source",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load contract runtime from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime = _load_runtime()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain an object")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = runtime.canonicalize(payload)
    path.write_text(
        json.dumps(normalized, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(value: object) -> str:
    encoded = runtime.canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _redigest(document: dict[str, Any]) -> dict[str, Any]:
    document["content_digest"] = runtime.calculate_digest(document)
    return document


def _optimization_bundle() -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "optimization_strategy_id": "cost-minimization",
        "optimization_strategy_version": "1",
        "calculation_strategy_id": "cost-calculation",
        "calculation_strategy_version": "2",
        "formula_set_id": "cost-formula-set",
        "formula_set_version": "1",
        "scoring_strategy_id": "monthly-cost",
        "scoring_strategy_version": "1",
        "pricing_registry_id": "provider-catalog",
        "pricing_registry_versions": ["1"],
        "workload_contract_id": "digital-twin-workload",
        "workload_contract_version": "1",
        "deployment_specification_versions": ["resolved-deployment-specification.v1"],
    }
    bundle["compatibility_digest"] = _sha256(bundle)
    return bundle


def _semantic_registry() -> dict[str, Any]:
    port_contracts = [
        {
            "port_id": port_id,
            "schema_ref": (
                "twin-query-result" if "query" in port_id else "normalized-telemetry"
            ),
            "envelope_ref": "contract-envelope",
            "semantics": (
                "Typed query request or correlated response."
                if "query" in port_id
                else "Normalized telemetry or storage transition payload."
            ),
            "compatibility_version": "1",
        }
        for port_id in sorted(
            {
                port_id
                for input_ports, output_ports in PORTS_BY_COMPONENT.values()
                for port_id in (*input_ports, *output_ports)
            }
        )
    ]
    registry = {
        "schema_version": "semantic-registry.v1",
        "registry_id": "architecture-profile-semantics",
        "registry_version": "1",
        "supported_schema_versions": sorted(runtime.SCHEMA_FILES),
        "supported_providers": ["aws", "azure", "gcp"],
        "known_error_codes": list(ERROR_CODES),
        "field_ownership": [
            {
                "contract_kind": "architecture-profile.v1",
                "field_path": "/",
                "author": "repository_developer",
                "mutability": "versioned_definition",
            },
            {
                "contract_kind": "provider-implementation-profile.v1",
                "field_path": "/",
                "author": "repository_developer",
                "mutability": "versioned_definition",
            },
            {
                "contract_kind": "deployment-component-catalog.v1",
                "field_path": "/",
                "author": "repository_developer",
                "mutability": "versioned_definition",
            },
            {
                "contract_kind": "resolved-twin-architecture.v1",
                "field_path": "/calculation_run_id",
                "author": "management_api_input",
                "mutability": "immutable_input",
            },
            *[
                {
                    "contract_kind": "resolved-twin-architecture.v1",
                    "field_path": f"/{field}",
                    "author": "optimizer_derived",
                    "mutability": "immutable_derived",
                }
                for field in (
                    "architecture_profile_ref",
                    "component_assignments",
                    "content_digest",
                    "cost_summary",
                    "deployment_specification_ref",
                    "extension_bindings",
                    "functional_completeness",
                    "optimization_bundle_ref",
                    "pricing_evidence_refs",
                    "provider_profile_refs",
                    "resolution_id",
                    "resolved_edges",
                    "schema_version",
                    "workload_contract_ref",
                )
            ],
        ],
        "cycle_contracts": [
            {
                "cycle_id": "cycle.hot-storage.twin-state",
                "workflow_semantics": (
                    "Bounded, explicitly correlated reconciliation between hot "
                    "storage and Twin state; not enabled by the baseline profile."
                ),
                "compatibility_version": "1",
            }
        ],
        "compatible_optimization_bundles": [_optimization_bundle()],
        "port_contracts": port_contracts,
        "deployment_specification_compatibility": [
            {
                "schema_version": "resolved-deployment-specification.v1",
                "architecture_profile_ids": ["five-layer-baseline"],
                "architecture_profile_versions": ["1"],
            }
        ],
        "limits": {
            "max_document_bytes": runtime.MAX_DOCUMENT_BYTES,
            "max_depth": runtime.MAX_DEPTH,
            "max_array_items": runtime.MAX_ARRAY_ITEMS,
            "max_errors": runtime.MAX_ERRORS,
        },
        "content_digest": "",
    }
    return _redigest(registry)


def _delivery_requirements(mode: str) -> dict[str, str]:
    if mode == "synchronous":
        return {
            "mode": mode,
            "timeout_policy": "bounded",
            "retry_policy": "bounded_backoff",
            "dead_letter_policy": "not_applicable",
            "idempotency": "required",
            "ordering": "not_required",
            "replay": "not_supported",
        }
    return {
        "mode": mode,
        "timeout_policy": "not_applicable",
        "retry_policy": "provider_managed_bounded",
        "dead_letter_policy": "provider_managed",
        "idempotency": "consumer_deduplicated",
        "ordering": "per_entity",
        "replay": "bounded",
    }


def _architecture_profile() -> dict[str, Any]:
    workload_path = (
        ROOT / "2-twin2clouds" / "pricing_registry" / "workload_contracts.yaml"
    )
    responsibilities = [
        {
            "responsibility_id": responsibility_id,
            "display_name": display_name,
            "required": True,
            "capability_requirements": [
                f"capability.{responsibility_id.removeprefix('responsibility.')}"
            ],
            "workload_field_refs": [
                (
                    "workload.logical-query-count"
                    if responsibility_id == "responsibility.visualization"
                    else "workload.telemetry-update-count"
                )
            ],
            "cost_category_ids": [
                f"cost.{responsibility_id.removeprefix('responsibility.')}"
            ],
            "logical_component_ids": list(component_ids),
            "evaluation_order": evaluation_order,
        }
        for (
            responsibility_id,
            display_name,
            component_ids,
            evaluation_order,
        ) in RESPONSIBILITIES
    ]
    components = []
    for component_id, responsibility_id, component_kind, _ in LOGICAL_COMPONENTS:
        input_ports, output_ports = PORTS_BY_COMPONENT[component_id]
        capability_suffix = component_id.removeprefix("component.")
        components.append(
            {
                "component_id": component_id,
                "responsibility_id": responsibility_id,
                "component_kind": component_kind,
                "required": True,
                "required_capability_ids": [f"capability.{capability_suffix}"],
                "input_port_ids": list(input_ports),
                "output_port_ids": list(output_ports),
                "extension_slot_ids": [],
                "cost_owner_ids": [f"cost.{capability_suffix}"],
                "observability_contract_id": "observability.baseline",
            }
        )
    edges = []
    for (
        edge_id,
        source_component_id,
        source_port_id,
        destination_component_id,
        destination_port_id,
        _mechanism,
        mode,
    ) in LOGICAL_EDGES:
        edges.append(
            {
                "edge_id": edge_id,
                "source_component_id": source_component_id,
                "source_port_id": source_port_id,
                "destination_component_id": destination_component_id,
                "destination_port_id": destination_port_id,
                "edge_contract_id": (
                    "twin-query-result"
                    if mode == "synchronous"
                    else "normalized-telemetry"
                ),
                "edge_contract_version": "1",
                "required": True,
                "delivery_requirements": _delivery_requirements(mode),
                "trust_requirements": {
                    "authentication": "workload_identity",
                    "authorization": "least_privilege_capability_set",
                    "transport": "tls",
                },
                "observability_requirements": {
                    "correlation": "required",
                    "metrics": "required",
                    "bounded_error_contract": "required",
                },
                "transfer_workload_ref": {
                    "id": (
                        "logical-query-count"
                        if mode == "synchronous"
                        else "telemetry-update-count"
                    ),
                    "version": "1",
                },
                "cost_owner_ids": [f"cost.{edge_id.removeprefix('edge.')}"],
            }
        )
    profile = {
        "schema_version": "architecture-profile.v1",
        "profile_id": "five-layer-baseline",
        "profile_version": "1",
        "lifecycle_status": "active",
        "display_name": "Five-layer baseline",
        "description": (
            "Paper-compatible ingestion, processing, storage, Twin-state, and "
            "visualization responsibilities with provider implementation hidden "
            "behind reviewed mappings."
        ),
        "workload_contract_ref": {
            "id": "digital-twin-workload",
            "version": "1",
            "digest": _file_digest(workload_path),
        },
        "optimization_bundle": _optimization_bundle(),
        "responsibilities": responsibilities,
        "components": components,
        "edges": edges,
        "extension_slots": [],
        "graph_policy": {
            "cycle_policy": "acyclic",
            "allowed_cycle_ids": [],
            "optional_components": [],
            "user_topology_editable": False,
        },
        "compatibility": {
            "supported_contract_versions": [
                "digital-twin-workload.v1",
                "resolved-deployment-specification.v1",
            ],
            "provider_implementation_schema_versions": [
                "provider-implementation-profile.v1"
            ],
            "catalog_schema_versions": ["deployment-component-catalog.v1"],
            "resolved_architecture_schema_versions": ["resolved-twin-architecture.v1"],
        },
        "content_digest": "",
    }
    return _redigest(profile)


def _deployment_id(provider: str, component_id: str) -> str:
    return f"deployment.{provider}.{component_id.removeprefix('component.')}"


def _edge_implementation_id(provider: str, edge_id: str) -> str:
    return f"edge-implementation.{provider}.{edge_id.removeprefix('edge.')}"


def _provider_profile(
    provider: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    config = PROVIDER_CONFIG[provider]
    component_mappings = []
    all_capabilities: set[str] = set()
    for component in profile["components"]:
        component_id = component["component_id"]
        capabilities = component["required_capability_ids"]
        all_capabilities.update(capabilities)
        component_mappings.append(
            {
                "component_id": component_id,
                "deployment_component_candidates": [
                    _deployment_id(provider, component_id)
                ],
                "required_capability_ids": capabilities,
                "provided_capability_ids": capabilities,
                "service_model_refs": [
                    f"service-model.{provider}.{component_id.removeprefix('component.')}"
                ],
                "formula_refs": [f"formula.{component_id.removeprefix('component.')}"],
                "supported_region_ids": [config["region_id"]],
                "deployment_specification_component_ids": list(
                    config["deployment_components"][component_id]
                ),
                "deployment_specification_slot_ids": [
                    next(
                        slot_id
                        for logical_id, _, _, slot_id in LOGICAL_COMPONENTS
                        if logical_id == component_id
                    )
                ],
            }
        )
    edge_mappings = []
    for edge in profile["edges"]:
        edge_tuple = next(item for item in LOGICAL_EDGES if item[0] == edge["edge_id"])
        source_component_id = edge_tuple[1]
        destination_component_id = edge_tuple[3]
        mechanism = edge_tuple[5]
        edge_mappings.append(
            {
                "edge_id": edge["edge_id"],
                "edge_implementation_id": _edge_implementation_id(
                    provider,
                    edge["edge_id"],
                ),
                "source_deployment_component_ids": [
                    _deployment_id(provider, source_component_id)
                ],
                "destination_deployment_component_ids": [
                    _deployment_id(provider, destination_component_id)
                ],
                "mechanism": mechanism,
                "catalog_input_port_id": (
                    f"catalog.{provider}.{edge['destination_port_id']}"
                ),
                "catalog_output_port_id": (
                    f"catalog.{provider}.{edge['source_port_id']}"
                ),
                "transfer_route_class": "same_provider_same_region",
                "cost_owner_ids": edge["cost_owner_ids"],
            }
        )
    provider_profile = {
        "schema_version": "provider-implementation-profile.v1",
        "implementation_profile_id": config["profile_id"],
        "implementation_profile_version": "1",
        "architecture_profile_ref": {
            "id": profile["profile_id"],
            "version": profile["profile_version"],
            "digest": profile["content_digest"],
        },
        "provider": provider,
        "lifecycle_status": "active",
        "region_policy_ref": {
            "id": f"region-policy.{provider}.baseline",
            "version": "1",
        },
        "permission_set_ref": {
            "id": f"permission-set.{provider}.baseline",
            "version": "1",
        },
        "supported": True,
        "component_mappings": component_mappings,
        "edge_mappings": edge_mappings,
        "capability_claims": {
            "required_capability_ids": sorted(all_capabilities),
            "provided_capability_ids": sorted(all_capabilities),
            "extra_capability_ids": [],
            "missing_capability_ids": [],
            "evidence_refs": [f"evidence.{provider}.baseline-capability-matrix"],
        },
        "unsupported_reasons": [],
        "compatibility": {
            "compatible_catalog_versions": [
                {"id": "baseline-component-catalog", "version": "1"}
            ],
            "compatible_resolver_versions": ["1"],
            "compatible_runtime_versions": ["1"],
            "compatible_deployment_specification_versions": [
                "resolved-deployment-specification.v1"
            ],
        },
        "content_digest": "",
    }
    return _redigest(provider_profile)


def _catalog_port(provider: str, port_id: str, phase: str) -> dict[str, Any]:
    return {
        "port_id": f"catalog.{provider}.{port_id}",
        "schema_ref": {
            "id": "twin-query-result" if "query" in port_id else "normalized-telemetry",
            "version": "1",
        },
        "envelope_ref": {"id": "contract-envelope", "version": "1"},
        "value_type": "json_document",
        "sensitivity": "internal",
        "cardinality": "many",
        "producer_consumer_phase": "runtime",
        "resolution_stage": phase,
        "compatibility_version": "1",
    }


def _catalog(
    profile: dict[str, Any],
    provider_profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    artifacts = []
    components = []
    edge_implementations = []
    for provider, config in PROVIDER_CONFIG.items():
        artifact_id = f"artifact.platform.{provider}.baseline"
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_version": "1",
                "repository_source_path": "3-cloud-deployer/src",
                "platform_handler": f"handler.{provider}.platform",
                "digest_policy": "sha256.canonical-source.v1",
                "included_paths": ["**/*.py"],
                "excluded_paths": ["**/__pycache__/**"],
                "builder_adapter_id": f"builder.{provider}.baseline",
                "supported_runtimes": [f"runtime.{provider}.managed"],
                "user_source_policy": "platform_only",
                "compatibility": {
                    "component_versions": ["1"],
                    "builder_versions": ["1"],
                },
            }
        )
        provider_profile_ref = {
            "id": provider_profiles[provider]["implementation_profile_id"],
            "version": "1",
        }
        for component_id, _, component_kind, slot_id in LOGICAL_COMPONENTS:
            input_ports, output_ports = PORTS_BY_COMPONENT[component_id]
            component_suffix = component_id.removeprefix("component.")
            terraform_prefix = "azurerm" if provider == "azure" else provider
            resource_kind = component_suffix.replace("-", "_")
            components.append(
                {
                    "deployment_component_id": _deployment_id(provider, component_id),
                    "component_version": "1",
                    "provider": provider,
                    "logical_component_ids": [component_id],
                    "service_id": f"{provider}.{component_suffix}",
                    "component_kind": (
                        "storage_service"
                        if component_kind == "storage"
                        else (
                            "twin_service"
                            if component_kind == "twin_state"
                            else (
                                "visualization_service"
                                if component_kind == "visualization"
                                else "managed_service"
                            )
                        )
                    ),
                    "package_artifact_ref": {"id": artifact_id, "version": "1"},
                    "terraform_binding": {
                        "resource_addresses": [
                            f"{terraform_prefix}_{resource_kind}.component"
                        ],
                        "module_addresses": [],
                        "allowed_input_variable_ids": [
                            f"input.{provider}.{component_suffix}.selection"
                        ],
                        "outputs": [
                            {
                                "output_id": (
                                    f"output.{provider}.{component_suffix}.binding"
                                ),
                                "sensitive": False,
                            }
                        ],
                        "dependency_keys": [],
                    },
                    "runtime_contract": {
                        "provider_runtime_id": f"runtime.{provider}.managed",
                        "platform_handler_adapter_id": (
                            f"handler-adapter.{provider}.baseline"
                        ),
                        "timeout_seconds_min": 1,
                        "timeout_seconds_max": 300,
                        "memory_mb_min": 128,
                        "memory_mb_max": 4096,
                        "trigger_adapter_id": f"trigger-adapter.{provider}.baseline",
                        "package_layout_id": "package-layout.platform-v1",
                        "user_override_allowed": False,
                    },
                    "configuration_schema_ref": {
                        "id": f"configuration.{provider}.{component_suffix}",
                        "version": "1",
                    },
                    "input_ports": [
                        _catalog_port(provider, port_id, "deployer_output")
                        for port_id in input_ports
                    ],
                    "output_ports": [
                        _catalog_port(provider, port_id, "deployer_output")
                        for port_id in output_ports
                    ],
                    "required_permission_capabilities": [
                        f"permission.{provider}.{component_suffix}"
                    ],
                    "pricing_model_refs": [f"pricing.{provider}.{component_suffix}"],
                    "formula_refs": [f"formula.{component_suffix}"],
                    "deployment_specification_bindings": [
                        {
                            "specification_schema_version": (
                                "resolved-deployment-specification.v1"
                            ),
                            "component_id": deployment_component_id,
                            "slot_id": slot_id,
                        }
                        for deployment_component_id in config["deployment_components"][
                            component_id
                        ]
                    ],
                    "extension_slot_refs": [],
                    "error_contract_ref": {
                        "id": "architecture-runtime-errors",
                        "version": "1",
                    },
                    "observability_contract_ref": {
                        "id": "observability.baseline",
                        "version": "1",
                    },
                    "cleanup_contract_ref": {
                        "id": "cleanup.baseline",
                        "version": "1",
                    },
                    "compatibility": {
                        "architecture_profile_versions": [
                            {"id": "five-layer-baseline", "version": "1"}
                        ],
                        "provider_profile_versions": [provider_profile_ref],
                        "deployment_specification_versions": [
                            "resolved-deployment-specification.v1"
                        ],
                    },
                }
            )
        for edge in profile["edges"]:
            edge_tuple = next(
                item for item in LOGICAL_EDGES if item[0] == edge["edge_id"]
            )
            source_component_id = edge_tuple[1]
            destination_component_id = edge_tuple[3]
            edge_implementations.append(
                {
                    "edge_implementation_id": _edge_implementation_id(
                        provider,
                        edge["edge_id"],
                    ),
                    "edge_implementation_version": "1",
                    "provider": provider,
                    "logical_edge_ids": [edge["edge_id"]],
                    "mechanism": edge_tuple[5],
                    "source_component_ids": [
                        _deployment_id(provider, source_component_id)
                    ],
                    "destination_component_ids": [
                        _deployment_id(provider, destination_component_id)
                    ],
                    "source_output_port_id": (
                        f"catalog.{provider}.{edge['source_port_id']}"
                    ),
                    "destination_input_port_id": (
                        f"catalog.{provider}.{edge['destination_port_id']}"
                    ),
                    "transfer_route_class": "same_provider_same_region",
                    "pricing_model_refs": [f"pricing.{provider}.transfer"],
                    "formula_refs": ["formula.transfer"],
                    "required_permission_capabilities": [
                        f"permission.{provider}.edge-runtime"
                    ],
                    "compatibility": {
                        "architecture_profile_versions": [
                            {"id": "five-layer-baseline", "version": "1"}
                        ],
                        "provider_profile_versions": [provider_profile_ref],
                        "deployment_specification_versions": [
                            "resolved-deployment-specification.v1"
                        ],
                    },
                }
            )
    mixed_edge = LOGICAL_EDGES[0]
    edge_implementations.append(
        {
            "edge_implementation_id": (
                "edge-implementation.aws-to-azure.ingestion-to-processing"
            ),
            "edge_implementation_version": "1",
            "provider": "aws",
            "logical_edge_ids": [mixed_edge[0]],
            "mechanism": "cross_provider_adapter",
            "source_component_ids": [_deployment_id("aws", "component.ingestion")],
            "destination_component_ids": [
                _deployment_id("azure", "component.processing")
            ],
            "source_output_port_id": ("catalog.aws.port.ingestion.telemetry-out"),
            "destination_input_port_id": ("catalog.azure.port.processing.telemetry-in"),
            "transfer_route_class": "cross_provider",
            "pricing_model_refs": ["pricing.cross-provider.transfer"],
            "formula_refs": ["formula.transfer"],
            "required_permission_capabilities": ["permission.cross-provider.adapter"],
            "compatibility": {
                "architecture_profile_versions": [
                    {"id": "five-layer-baseline", "version": "1"}
                ],
                "provider_profile_versions": [
                    {"id": "provider-profile.aws.baseline", "version": "1"},
                    {"id": "provider-profile.azure.baseline", "version": "1"},
                ],
                "deployment_specification_versions": [
                    "resolved-deployment-specification.v1"
                ],
            },
        }
    )
    catalog = {
        "schema_version": "deployment-component-catalog.v1",
        "catalog_id": "baseline-component-catalog",
        "catalog_version": "1",
        "lifecycle_status": "active",
        "components": components,
        "edge_implementations": edge_implementations,
        "package_artifacts": artifacts,
        "compatibility": {
            "architecture_profile_schema_versions": ["architecture-profile.v1"],
            "provider_profile_schema_versions": ["provider-implementation-profile.v1"],
            "resolver_versions": ["1"],
            "deployer_runtime_versions": ["1"],
            "deployment_specification_versions": [
                "resolved-deployment-specification.v1"
            ],
        },
        "content_digest": "",
    }
    return _redigest(catalog)


def _resolved_architecture(
    profile: dict[str, Any],
    provider_profiles: dict[str, dict[str, Any]],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    provider_by_component = {
        "component.ingestion": "aws",
        **{
            component_id: "azure"
            for component_id, _, _, _ in LOGICAL_COMPONENTS
            if component_id != "component.ingestion"
        },
    }
    assignments = []
    assignment_by_component: dict[str, str] = {}
    for component in profile["components"]:
        component_id = component["component_id"]
        provider = provider_by_component[component_id]
        config = PROVIDER_CONFIG[provider]
        assignment_id = f"assignment.{component_id.removeprefix('component.')}"
        assignment_by_component[component_id] = assignment_id
        assignments.append(
            {
                "assignment_id": assignment_id,
                "responsibility_id": component["responsibility_id"],
                "logical_component_id": component_id,
                "provider": provider,
                "provider_implementation_profile_ref": {
                    "id": config["profile_id"],
                    "version": "1",
                    "digest": provider_profiles[provider]["content_digest"],
                },
                "deployment_component_id": _deployment_id(provider, component_id),
                "deployment_component_version": "1",
                "service_id": (f"{provider}.{component_id.removeprefix('component.')}"),
                "region": config["region"],
                "capability_evidence": component["required_capability_ids"],
                "pricing_model_refs": [
                    f"pricing.{provider}.{component_id.removeprefix('component.')}"
                ],
                "formula_refs": [f"formula.{component_id.removeprefix('component.')}"],
                "deployment_specification_component_ids": list(
                    config["deployment_components"][component_id]
                ),
                "cost_contribution": {
                    "currency": "USD",
                    "monthly_amount": "1",
                },
                "required": True,
            }
        )
    resolved_edges = []
    for edge in profile["edges"]:
        edge_tuple = next(item for item in LOGICAL_EDGES if item[0] == edge["edge_id"])
        source_component_id = edge_tuple[1]
        destination_component_id = edge_tuple[3]
        source_provider = provider_by_component[source_component_id]
        destination_provider = provider_by_component[destination_component_id]
        is_cross_provider = source_provider != destination_provider
        if is_cross_provider:
            edge_implementation_id = (
                "edge-implementation.aws-to-azure.ingestion-to-processing"
            )
            mechanism = "cross_provider_adapter"
            route_class = "cross_provider"
        else:
            edge_implementation_id = _edge_implementation_id(
                source_provider,
                edge["edge_id"],
            )
            mechanism = edge_tuple[5]
            route_class = "same_provider_same_region"
        resolved_edges.append(
            {
                "resolved_edge_id": (
                    f"resolved.{edge['edge_id'].removeprefix('edge.')}"
                ),
                "edge_id": edge["edge_id"],
                "source_assignment_id": assignment_by_component[source_component_id],
                "source_port_id": (
                    f"catalog.{source_provider}.{edge['source_port_id']}"
                ),
                "destination_assignment_id": assignment_by_component[
                    destination_component_id
                ],
                "destination_port_id": (
                    f"catalog.{destination_provider}.{edge['destination_port_id']}"
                ),
                "edge_implementation_id": edge_implementation_id,
                "mechanism": mechanism,
                "delivery_semantics": edge["delivery_requirements"],
                "transfer_route_class": route_class,
                "transfer_evidence_refs": [
                    (
                        "evidence.cross-provider.transfer"
                        if is_cross_provider
                        else f"evidence.{source_provider}.transfer"
                    )
                ],
                "formula_refs": ["formula.transfer"],
                "cost_contribution": {
                    "currency": "USD",
                    "monthly_amount": "0.1",
                },
                "trust_contract_ref": {
                    "id": "trust.baseline",
                    "version": "1",
                },
                "observability_contract_ref": {
                    "id": "observability.baseline",
                    "version": "1",
                },
                "deployment_input_binding_ids": [
                    f"binding.input.{edge['edge_id'].removeprefix('edge.')}"
                ],
                "deployment_output_binding_ids": [
                    f"binding.output.{edge['edge_id'].removeprefix('edge.')}"
                ],
            }
        )
    existing_spec = _read_json(
        ROOT
        / "contracts"
        / "resolved-deployment-specification"
        / "v1"
        / "fixtures"
        / "valid"
        / "mixed-providers.json"
    )
    bundle = profile["optimization_bundle"]
    capabilities = sorted(
        {
            capability
            for component in profile["components"]
            for capability in component["required_capability_ids"]
        }
    )
    validation_payload = {
        "capabilities": capabilities,
        "profile_digest": profile["content_digest"],
        "catalog_digest": catalog["content_digest"],
    }
    resolution = {
        "schema_version": "resolved-twin-architecture.v1",
        "resolution_id": "00000000-0000-0000-0000-000000000000",
        "calculation_run_id": existing_spec["calculation_run_id"],
        "architecture_profile_ref": {
            "id": profile["profile_id"],
            "version": profile["profile_version"],
            "digest": profile["content_digest"],
        },
        "optimization_bundle_ref": {
            field: bundle[field]
            for field in (
                "optimization_strategy_id",
                "optimization_strategy_version",
                "calculation_strategy_id",
                "calculation_strategy_version",
                "formula_set_id",
                "formula_set_version",
                "scoring_strategy_id",
                "scoring_strategy_version",
                "compatibility_digest",
            )
        },
        "provider_profile_refs": [
            {
                "id": provider_profiles[provider]["implementation_profile_id"],
                "version": "1",
                "digest": provider_profiles[provider]["content_digest"],
                "provider": provider,
            }
            for provider in ("aws", "azure")
        ],
        "workload_contract_ref": profile["workload_contract_ref"],
        "pricing_evidence_refs": [
            {
                "id": f"pricing-evidence.{provider}.baseline",
                "version": "1",
                "digest": _sha256({"provider": provider, "version": "1"}),
                "provider": provider,
                "currency": "USD",
            }
            for provider in ("aws", "azure")
        ],
        "component_assignments": assignments,
        "resolved_edges": resolved_edges,
        "extension_bindings": [],
        "deployment_specification_ref": {
            "schema_version": existing_spec["schema_version"],
            "digest": existing_spec["digest"],
            "calculation_run_id": existing_spec["calculation_run_id"],
        },
        "cost_summary": {
            "currency": "USD",
            "responsibility_totals": [
                {
                    "item_id": responsibility_id,
                    "monthly_amount": (
                        "3" if responsibility_id == "responsibility.storage" else "1"
                    ),
                }
                for responsibility_id, _, _, _ in RESPONSIBILITIES
            ],
            "component_totals": [
                {
                    "item_id": component["component_id"],
                    "monthly_amount": "1",
                }
                for component in profile["components"]
            ],
            "edge_totals": [
                {"item_id": edge["edge_id"], "monthly_amount": "0.1"}
                for edge in profile["edges"]
            ],
            "monthly_total": "7.6",
        },
        "functional_completeness": {
            "status": "complete",
            "required_capability_ids": capabilities,
            "provided_capability_ids": capabilities,
            "provider_extra_capability_ids": [],
            "missing_capability_ids": [],
            "validator_version": "1",
            "validation_digest": _sha256(validation_payload),
        },
        "content_digest": "",
    }
    resolution["resolution_id"] = runtime.calculate_resolution_id(resolution)
    return _redigest(resolution)


def generate_contract_data() -> None:
    """Regenerate the reviewed registry and canonical fixture matrix."""
    registry = _semantic_registry()
    profile = _architecture_profile()
    provider_profiles = {
        provider: _provider_profile(provider, profile) for provider in ("aws", "azure")
    }
    catalog = _catalog(profile, provider_profiles)
    resolution = _resolved_architecture(profile, provider_profiles, catalog)

    _write_json(SOURCE_V1 / "semantic-registry.json", registry)
    if VALID_ROOT.exists():
        shutil.rmtree(VALID_ROOT)
    if INVALID_ROOT.exists():
        shutil.rmtree(INVALID_ROOT)
    valid_documents = {
        "five-layer-baseline-profile.json": profile,
        "aws-baseline-provider-profile.json": provider_profiles["aws"],
        "azure-baseline-provider-profile.json": provider_profiles["azure"],
        "baseline-component-catalog.json": catalog,
        "mixed-baseline-resolved-architecture.json": resolution,
    }
    for filename, document in valid_documents.items():
        _write_json(VALID_ROOT / filename, document)

    unknown_version = copy.deepcopy(profile)
    unknown_version["schema_version"] = "architecture-profile.v2"
    _redigest(unknown_version)

    duplicate_id = copy.deepcopy(profile)
    duplicate_id["components"].append(copy.deepcopy(duplicate_id["components"][0]))
    _redigest(duplicate_id)

    unresolved_reference = copy.deepcopy(profile)
    unresolved_reference["edges"][0]["destination_component_id"] = "component.missing"
    _redigest(unresolved_reference)

    illegal_cycle = copy.deepcopy(profile)
    illegal_cycle["edges"].append(
        {
            "edge_id": "edge.twin-state-to-hot-storage-cycle",
            "source_component_id": "component.twin-state",
            "source_port_id": "port.twin-state.query-out",
            "destination_component_id": "component.hot-storage",
            "destination_port_id": "port.hot-storage.write-in",
            "edge_contract_id": "twin-query-result",
            "edge_contract_version": "1",
            "required": True,
            "delivery_requirements": _delivery_requirements("synchronous"),
            "trust_requirements": {
                "authentication": "workload_identity",
                "authorization": "least_privilege_capability_set",
                "transport": "tls",
            },
            "observability_requirements": {
                "correlation": "required",
                "metrics": "required",
                "bounded_error_contract": "required",
            },
            "transfer_workload_ref": {
                "id": "logical-query-count",
                "version": "1",
            },
            "cost_owner_ids": ["cost.twin-state-to-hot-storage-cycle"],
        }
    )
    _redigest(illegal_cycle)

    capability_mismatch = copy.deepcopy(provider_profiles["aws"])
    capability_mismatch["capability_claims"]["provided_capability_ids"].remove(
        "capability.visualization"
    )
    _redigest(capability_mismatch)

    secret_like_field = copy.deepcopy(profile)
    secret_like_field["client_secret"] = "forbidden"
    _redigest(secret_like_field)

    digest_tamper = copy.deepcopy(profile)
    digest_tamper["display_name"] = "Tampered after digest"

    invalid_documents = {
        "unknown-version.json": ("ARCH_VERSION_UNSUPPORTED", unknown_version),
        "duplicate-id.json": ("ARCH_DUPLICATE_ID", duplicate_id),
        "unresolved-reference.json": (
            "ARCH_REFERENCE_UNRESOLVED",
            unresolved_reference,
        ),
        "illegal-cycle.json": ("ARCH_GRAPH_CYCLE_FORBIDDEN", illegal_cycle),
        "capability-mismatch.json": (
            "ARCH_CAPABILITY_INCOMPLETE",
            capability_mismatch,
        ),
        "secret-like-field.json": (
            "ARCH_SECRET_FIELD_FORBIDDEN",
            secret_like_field,
        ),
        "digest-tamper.json": ("ARCH_DIGEST_MISMATCH", digest_tamper),
    }
    for filename, (expected_error, document) in invalid_documents.items():
        _write_json(
            INVALID_ROOT / filename,
            {
                "expected_error": expected_error,
                "document": document,
            },
        )


def _source_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != ".contract-sha256"
    )


def contract_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in _source_files():
        digest.update(path.relative_to(SOURCE_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def load_valid_documents() -> list[dict[str, Any]]:
    return [_read_json(path) for path in sorted(VALID_ROOT.glob("*.json"))]


def validate_source() -> None:
    for filename in SCHEMA_FILES:
        schema = _read_json(SOURCE_V1 / filename)
        Draft202012Validator.check_schema(schema)

    valid_paths = sorted(VALID_ROOT.glob("*.json"))
    invalid_paths = sorted(INVALID_ROOT.glob("*.json"))
    if not MANDATORY_VALID_FIXTURES.issubset({path.name for path in valid_paths}):
        raise RuntimeError("Mandatory valid architecture fixtures are incomplete")
    if {path.name for path in invalid_paths} != set(MANDATORY_INVALID_FIXTURES):
        raise RuntimeError("Mandatory invalid architecture fixtures are incomplete")

    registry = _read_json(SOURCE_V1 / "semantic-registry.json")
    runtime.validate_document(registry, bundle_root=SOURCE_V1)
    valid_documents = [_read_json(path) for path in valid_paths]
    for document in valid_documents:
        runtime.validate_document(
            document,
            bundle_root=SOURCE_V1,
            linked_documents=valid_documents,
        )
    runtime.validate_bundle(valid_documents, bundle_root=SOURCE_V1)

    for path in invalid_paths:
        wrapper = _read_json(path)
        expected_error = wrapper.get("expected_error")
        document = wrapper.get("document")
        if expected_error != MANDATORY_INVALID_FIXTURES[path.name] or not isinstance(
            document, dict
        ):
            raise RuntimeError(f"{path} has an invalid negative-fixture wrapper")
        try:
            runtime.validate_document(
                document,
                bundle_root=SOURCE_V1,
                linked_documents=valid_documents,
            )
        except runtime.ContractError as exc:
            if exc.code != expected_error:
                raise RuntimeError(
                    f"{path} expected {expected_error}, got {exc.code}: {exc}"
                ) from exc
        else:
            raise RuntimeError(f"{path} unexpectedly passed validation")


def synchronize() -> None:
    tree_digest = contract_tree_digest()
    for target in GENERATED_TARGETS:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            SOURCE_ROOT,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (target / ".contract-sha256").write_text(
            tree_digest + "\n",
            encoding="utf-8",
        )


def check_synchronized() -> None:
    expected_files = {
        path.relative_to(SOURCE_ROOT): path.read_bytes() for path in _source_files()
    }
    tree_digest = contract_tree_digest()
    for target in GENERATED_TARGETS:
        if not target.is_dir():
            raise RuntimeError(f"Missing generated architecture contract: {target}")
        actual_files = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
            and path.name != ".contract-sha256"
            and "__pycache__" not in path.parts
        }
        if actual_files != expected_files:
            raise RuntimeError(f"Generated architecture contract is stale: {target}")
        marker = target / ".contract-sha256"
        if (
            not marker.is_file()
            or marker.read_text(encoding="utf-8").strip() != tree_digest
        ):
            raise RuntimeError(f"Generated architecture digest is stale: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate-fixtures",
        action="store_true",
        help="Regenerate the semantic registry and reviewed fixture matrix.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Validate the source and refresh all generated service copies.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the source and require byte-identical generated copies.",
    )
    args = parser.parse_args()
    if not (args.generate_fixtures or args.sync or args.check):
        parser.error("at least one action is required")
    try:
        if args.generate_fixtures:
            generate_contract_data()
        validate_source()
        if args.sync:
            synchronize()
        if args.check:
            check_synchronized()
    except (RuntimeError, runtime.ContractError) as exc:
        code = getattr(exc, "code", "ARCH_CONTRACT_GATE_FAILED")
        path = getattr(exc, "path", "$")
        print(f"ERROR [{code}] {path}: {exc}", file=sys.stderr)
        return 1
    print(
        "architecture-profile-contracts: OK "
        f"(source_digest={contract_tree_digest()}, "
        f"generated_copies={len(GENERATED_TARGETS)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
