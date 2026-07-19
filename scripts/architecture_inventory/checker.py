"""Semantic builder and drift gate for the Phase 8.0 current graph."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

from .baseline import (
    BaselineDecisionError,
    check_baseline_decision,
)
from .canonical import content_digest, pretty_json, source_tree_digest
from .extractors import (
    ALLOWLISTED_ANCHORS,
    BASELINE_EDGES,
    FIXED_SLOT_CONSUMERS,
    MANAGEMENT_CHEAPEST_CONSUMERS,
    OPTIMIZER_SLOT_ORDER,
    PROVIDER_KEY_CONSUMERS,
    PROVIDERS,
    extract_artifact_sources,
    extract_deployment_contract,
    extract_optimizer_shape,
    extract_static_functions,
    extract_terraform_objects,
    deployer_container,
    repository_root,
    verify_allowlisted_anchors,
)


SCHEMA_VERSION = "architecture-inventory.v1"
INVENTORY_ID = "current-five-layer-implementation"
MAX_FINDINGS = 100
DIAGRAM_MANIFEST_START = "<!-- architecture-inventory-diagram-ids:"
DIAGRAM_MANIFEST_END = "-->"
AUDITED_SOURCE_PATHS = (
    "2-twin2clouds/backend/calculation_v2",
    "2-twin2clouds/backend/executable_topology.py",
    "3-cloud-deployer/src/deployment_specification",
    "3-cloud-deployer/src/core/executable_topology.py",
    "3-cloud-deployer/src/function_registry.py",
    "3-cloud-deployer/src/provider_capabilities.py",
    "3-cloud-deployer/src/providers/aws/lambda_functions",
    "3-cloud-deployer/src/providers/azure/azure_functions",
    "3-cloud-deployer/src/providers/gcp/cloud_functions",
    "3-cloud-deployer/src/providers/terraform/package_builder.py",
    "3-cloud-deployer/src/providers/terraform/package_builders",
    "3-cloud-deployer/src/terraform",
    "3-cloud-deployer/templates/digital-twin/cloud_functions",
    "contracts/resolved-deployment-specification/v1",
    "twin2multicloud_backend/src/contracts/executable_topology.py",
    (
        "twin2multicloud_backend/src/contracts/generated/"
        "resolved-deployment-specification"
    ),
    "twin2multicloud_backend/src/contracts/generated/user-function-extension",
    "twin2multicloud_backend/src/api/routes/twin_operations.py",
    "twin2multicloud_backend/src/models/cost_calculation.py",
    "twin2multicloud_backend/src/models/optimizer_config.py",
    "twin2multicloud_backend/src/services/cost_calculation_run_service.py",
    "twin2multicloud_backend/src/services/credential_resolution_service.py",
    "twin2multicloud_backend/src/services/deployment_operation_service.py",
    "twin2multicloud_backend/src/services/deployment_read_service.py",
    "twin2multicloud_backend/src/services/deployment_service.py",
    "twin2multicloud_backend/src/services/optimizer_config_projection.py",
    "twin2multicloud_backend/src/services/optimizer_configuration_service.py",
    "twin2multicloud_backend/src/services/project_zip_extraction_service.py",
    "twin2multicloud_backend/src/services/simulator_service.py",
    "twin2multicloud_backend/src/services/test_deployment_service.py",
    "twin2multicloud_backend/src/services/verification_service.py",
    "twin2multicloud_flutter/lib/models/architecture_path.dart",
    "twin2multicloud_flutter/lib/services/management_api.dart",
    "twin2multicloud_flutter/lib/services/sse_service.dart",
    (
        "twin2multicloud_flutter/lib/features/configuration_workspace/"
        "presentation/deployment/deployment_config_section.dart"
    ),
    (
        "twin2multicloud_flutter/lib/features/configuration_workspace/"
        "presentation/deployment/deployment_layer_overview.dart"
    ),
    "twin2multicloud_flutter/lib/widgets/architecture",
    "twin2multicloud_flutter/lib/widgets/architecture_graph.dart",
    "twin2multicloud_flutter/lib/widgets/file_inputs/config_visualization_block.dart",
)
PAPER_REFERENCES = (
    "docs/research/digital_twin_architecture_and_eventing_layer.md",
    "thesis/sections/03_concept.tex",
)
RESPONSIBILITY_BY_SLOT = {
    "l1_ingestion": "responsibility.l1.ingestion",
    "l2_processing": "responsibility.l2.processing",
    "l3_hot_storage": "responsibility.l3.hot-storage",
    "l3_cool_storage": "responsibility.l3.cool-storage",
    "l3_archive_storage": "responsibility.l3.archive-storage",
    "l4_twin_state": "responsibility.l4.twin-state",
    "l5_visualization": "responsibility.l5.visualization",
    "transition_runtime": "responsibility.storage-transition",
    "cross_cloud_glue": "responsibility.cross-cloud-glue",
}
COST_BY_RESPONSIBILITY = {
    responsibility_id: f"cost.{_slot.replace('_', '-')}"
    for _slot, responsibility_id in RESPONSIBILITY_BY_SLOT.items()
}
PAPER_LAYER_BY_SLOT = {
    "l1_ingestion": "L1",
    "l2_processing": "L2",
    "l3_hot_storage": "L3",
    "l3_cool_storage": "L3",
    "l3_archive_storage": "L3",
    "l4_twin_state": "L4",
    "l5_visualization": "L5",
    "transition_runtime": None,
    "cross_cloud_glue": None,
}
SLOT_NAME = {
    "l1_ingestion": "Telemetry acquisition",
    "l2_processing": "Telemetry processing",
    "l3_hot_storage": "Hot storage",
    "l3_cool_storage": "Cool storage",
    "l3_archive_storage": "Archive storage",
    "l4_twin_state": "Digital-twin state",
    "l5_visualization": "Visualization",
    "transition_runtime": "Storage transition runtime",
    "cross_cloud_glue": "Cross-provider glue",
}
FUNCTION_RESPONSIBILITY = {
    "dispatcher": "responsibility.l1.ingestion",
    "connector": "responsibility.cross-cloud-glue",
    "ingestion": "responsibility.cross-cloud-glue",
    "persister": "responsibility.l2.processing",
    "event-checker": "responsibility.l2.processing",
    "event-feedback": "responsibility.l2.processing",
    "processor_wrapper": "responsibility.l2.processing",
    "event_feedback_wrapper": "responsibility.l2.processing",
    "hot-writer": "responsibility.cross-cloud-glue",
    "cold-writer": "responsibility.cross-cloud-glue",
    "archive-writer": "responsibility.cross-cloud-glue",
    "adt-pusher": "responsibility.l4.twin-state",
    "l0-hot-reader": "responsibility.cross-cloud-glue",
    "l0-hot-reader-last-entry": "responsibility.cross-cloud-glue",
    "hot-reader": "responsibility.l3.hot-storage",
    "hot-reader-last-entry": "responsibility.l3.hot-storage",
    "hot-to-cold-mover": "responsibility.storage-transition",
    "cold-to-archive-mover": "responsibility.storage-transition",
    "digital-twin-data-connector": "responsibility.l4.twin-state",
    "digital-twin-data-connector-last-entry": "responsibility.l4.twin-state",
}
TERRAFORM_FILE_SLOT_OWNERS = {
    "aws_iot.tf": ("l1_ingestion",),
    "aws_compute.tf": (
        "l1_ingestion",
        "l2_processing",
        "l3_hot_storage",
        "transition_runtime",
    ),
    "aws_storage.tf": (
        "l3_hot_storage",
        "l3_cool_storage",
        "l3_archive_storage",
        "transition_runtime",
    ),
    "aws_twins.tf": ("l4_twin_state",),
    "aws_grafana.tf": ("l5_visualization",),
    "aws_glue.tf": ("cross_cloud_glue",),
    "azure_iot.tf": ("l1_ingestion",),
    "azure_compute.tf": (
        "l1_ingestion",
        "l2_processing",
        "l3_hot_storage",
        "transition_runtime",
    ),
    "azure_storage.tf": (
        "l3_hot_storage",
        "l3_cool_storage",
        "l3_archive_storage",
        "transition_runtime",
    ),
    "azure_twins.tf": ("l4_twin_state",),
    "azure_grafana.tf": ("l5_visualization",),
    "azure_user.tf": ("l5_visualization",),
    "azure_glue.tf": ("cross_cloud_glue",),
    "azure_function_keys.tf": ("l1_ingestion", "l2_processing"),
    "gcp_iot.tf": ("l1_ingestion",),
    "gcp_compute.tf": (
        "l1_ingestion",
        "l2_processing",
        "l3_hot_storage",
        "transition_runtime",
    ),
    "gcp_storage.tf": (
        "l3_hot_storage",
        "l3_cool_storage",
        "l3_archive_storage",
        "transition_runtime",
    ),
    "gcp_glue.tf": ("cross_cloud_glue",),
}


class InventoryCheckError(RuntimeError):
    """Stable bounded checker failure."""

    def __init__(self, category: str, findings: Iterable[str]):
        values = sorted({str(item)[:500] for item in findings})
        self.category = category
        self.total = len(values)
        self.findings = tuple(values[:MAX_FINDINGS])
        super().__init__(f"{category}: {self.total} finding(s)")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized or not normalized[0].isalpha():
        normalized = f"id-{normalized}"
    return normalized


def _source(path: str, anchor: str) -> str:
    return f"{path}#{anchor}"


def _git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _component_kind(slot: str, service_id: str) -> str:
    if slot in {"l3_hot_storage", "l3_cool_storage", "l3_archive_storage"}:
        return "storage"
    if slot == "l4_twin_state":
        return "twin-service"
    if slot == "l5_visualization":
        return "visualization"
    if slot == "transition_runtime":
        return "scheduler"
    if (
        "workflow" in service_id
        or "step_functions" in service_id
        or "logic" in service_id
    ):
        return "workflow"
    return (
        "function" if "function" in service_id or "lambda" in service_id else "bridge"
    )


def _provider_for_terraform(record: dict[str, Any]) -> str:
    if record["kind"] not in {"resource", "data"}:
        return "platform"
    parts = record["address"].split(".")
    resource_type = parts[1] if record["kind"] == "data" else parts[0]
    provider_prefix = resource_type.split("_", 1)[0]
    return {
        "aws": "aws",
        "awscc": "aws",
        "azuread": "azure",
        "azurerm": "azure",
        "google": "gcp",
    }.get(provider_prefix, "platform")


def _terraform_id(record: dict[str, Any]) -> str:
    return f"terraform.{record['kind']}.{_slug(record['address'])}"


def _catalog_component_ids(component_key: str) -> tuple[str, str]:
    token = _slug(component_key)
    return f"component.catalog.{token}", f"implementation.catalog.{token}"


def _function_component_ids(provider: str, name: str) -> tuple[str, str]:
    return (
        f"component.function.{_slug(name)}",
        f"implementation.{provider}.function.{_slug(name)}",
    )


def _platform_component(
    component_id: str,
    implementation_id: str,
    responsibility_id: str,
    kind: str,
    entrypoint: str,
    source_reference: str,
) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "implementation_id": implementation_id,
        "responsibility_id": responsibility_id,
        "provider": "platform",
        "kind": kind,
        "deployment_lifecycle": "always",
        "package_artifact_ids": [],
        "terraform_object_ids": [],
        "runtime_entrypoint": entrypoint,
        "platform_owned_fields": ["runtime code and service contract"],
        "user_owned_fields": [],
        "required_permission_capabilities": [],
        "observable_signals": ["structured application logs"],
        "source_references": [source_reference],
    }


def _build_responsibilities() -> list[dict[str, Any]]:
    records = []
    for slot, responsibility_id in RESPONSIBILITY_BY_SLOT.items():
        cost_id = f"cost.{_slug(slot)}"
        records.append(
            {
                "responsibility_id": responsibility_id,
                "name": SLOT_NAME[slot],
                "paper_layer_reference": PAPER_LAYER_BY_SLOT[slot],
                "optimizer_slot_ids": [slot] if slot in OPTIMIZER_SLOT_ORDER else [],
                "required_capability_ids": (
                    [f"capability.{slot}"] if slot in OPTIMIZER_SLOT_ORDER else []
                ),
                "cost_owner_ids": [cost_id],
                "description": (
                    "Current executable responsibility reconstructed from the "
                    "Optimizer and resolved-deployment registries."
                ),
                "source_references": [
                    _source(
                        "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
                        f"slots.{slot}",
                    )
                ],
            }
        )
    records.extend(
        [
            {
                "responsibility_id": "responsibility.platform.orchestration",
                "name": "Management and deployment orchestration",
                "paper_layer_reference": None,
                "optimizer_slot_ids": [],
                "required_capability_ids": ["capability.management-api"],
                "cost_owner_ids": ["cost.platform.orchestration"],
                "description": "Platform control-plane orchestration outside the deployed Twin layers.",
                "source_references": [
                    _source(
                        "twin2multicloud_backend/src/services/deployment_service.py",
                        "DeploymentPackage",
                    )
                ],
            },
            {
                "responsibility_id": "responsibility.user-extension",
                "name": "User-defined processing and event actions",
                "paper_layer_reference": "L2",
                "optimizer_slot_ids": ["l2_processing"],
                "required_capability_ids": ["capability.user-functions"],
                "cost_owner_ids": ["cost.user-extension"],
                "description": "User code packaged through provider-specific adapters without owning infrastructure fields.",
                "source_references": [
                    _source(
                        "3-cloud-deployer/src/providers/terraform/package_builders/user.py",
                        "build_user_packages",
                    )
                ],
            },
        ]
    )
    return sorted(records, key=lambda item: item["responsibility_id"])


def _build_components(
    contract: dict[str, Any],
    functions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    terraform: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        _platform_component(
            "component.platform.optimizer",
            "implementation.platform.optimizer",
            "responsibility.platform.orchestration",
            "api",
            "POST /calculate and resolved deployment specification builder",
            _source(
                "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
                "evaluate_complete_paths",
            ),
        ),
        _platform_component(
            "component.platform.management-api",
            "implementation.platform.management-api",
            "responsibility.platform.orchestration",
            "api",
            "Management API HTTP and SSE routes",
            _source(
                "twin2multicloud_backend/src/services/deployment_service.py",
                "DeploymentService",
            ),
        ),
        _platform_component(
            "component.platform.deployer",
            "implementation.platform.deployer",
            "responsibility.platform.orchestration",
            "api",
            "Deployer package validation and Terraform orchestration",
            _source("3-cloud-deployer/src/terraform_runner.py", "TerraformRunner"),
        ),
        _platform_component(
            "component.platform.flutter",
            "implementation.platform.flutter",
            "responsibility.platform.orchestration",
            "visualization",
            "ManagementApi adapter and fixed-slot architecture views",
            _source(
                "twin2multicloud_flutter/lib/services/management_api.dart",
                "ManagementApi",
            ),
        ),
    ]

    terraform_ids_by_provider: dict[str, list[str]] = defaultdict(list)
    for item in terraform:
        terraform_id = _terraform_id(item)
        for owner in _terraform_owner_ids(item, contract):
            match = re.fullmatch(
                r"implementation\.(platform|aws|azure|gcp)\.terraform-root",
                owner,
            )
            if match:
                terraform_ids_by_provider[match.group(1)].append(terraform_id)
    for provider in ("platform", *PROVIDERS):
        records.append(
            {
                "component_id": f"component.{provider}.terraform-root",
                "implementation_id": f"implementation.{provider}.terraform-root",
                "responsibility_id": "responsibility.platform.orchestration",
                "provider": provider,
                "kind": "bridge",
                "deployment_lifecycle": "always"
                if provider == "platform"
                else "provider-selected",
                "package_artifact_ids": [],
                "terraform_object_ids": sorted(terraform_ids_by_provider[provider]),
                "runtime_entrypoint": "single Terraform root module",
                "platform_owned_fields": ["Terraform resource and binding definitions"],
                "user_owned_fields": [],
                "required_permission_capabilities": [
                    "selected provider deployment identity"
                ],
                "observable_signals": ["bounded Terraform operation events"],
                "source_references": [
                    _source("3-cloud-deployer/src/terraform/main.tf", "root module")
                ],
            }
        )

    artifact_by_function = {
        (
            item["provider"],
            item["function_name"],
        ): f"artifact.{item['provider']}.function.{_slug(item['function_name'])}"
        for item in artifacts
        if item["source_key"].startswith("static:") and item["exists"]
    }
    terraform_ids_by_owner: dict[str, list[str]] = defaultdict(list)
    for item in terraform:
        terraform_id = _terraform_id(item)
        for owner in _terraform_owner_ids(item, contract):
            terraform_ids_by_owner[owner].append(terraform_id)
    for function in functions:
        responsibility = FUNCTION_RESPONSIBILITY[function["name"]]
        for provider in function["providers"]:
            component_id, implementation_id = _function_component_ids(
                provider, function["name"]
            )
            artifact_id = artifact_by_function.get((provider, function["name"]))
            is_user_feedback = function["name"] == "event-feedback"
            records.append(
                {
                    "component_id": component_id,
                    "implementation_id": implementation_id,
                    "responsibility_id": responsibility,
                    "provider": provider,
                    "kind": "user-extension" if is_user_feedback else "function",
                    "deployment_lifecycle": (
                        "feature-gated"
                        if function["optional"] or is_user_feedback
                        else (
                            "cross-provider-only"
                            if function["boundary"] and function["layer"] == "L0_GLUE"
                            else "provider-selected"
                        )
                    ),
                    "package_artifact_ids": [artifact_id] if artifact_id else [],
                    "terraform_object_ids": [],
                    "runtime_entrypoint": (
                        "operation-package user source"
                        if is_user_feedback
                        else f"{function['dir_name']}/{function['terraform_output_suffix']}"
                    ),
                    "platform_owned_fields": [
                        "wrapper, environment contract, and deployment binding"
                    ],
                    "user_owned_fields": (
                        ["event feedback handler source"] if is_user_feedback else []
                    ),
                    "required_permission_capabilities": [
                        "provider function invocation and logging"
                    ],
                    "observable_signals": ["provider function logs"],
                    "source_references": [
                        _source(
                            "3-cloud-deployer/src/function_registry.py",
                            f"FunctionDefinition name={function['name']}",
                        )
                    ],
                }
            )

    for component_key, definition in sorted(contract["components"].items()):
        component_id, implementation_id = _catalog_component_ids(component_key)
        slot = definition["slot_id"]
        records.append(
            {
                "component_id": component_id,
                "implementation_id": implementation_id,
                "responsibility_id": RESPONSIBILITY_BY_SLOT[slot],
                "provider": definition["provider"],
                "kind": _component_kind(slot, definition["service_id"]),
                "deployment_lifecycle": (
                    "cross-provider-only"
                    if slot == "cross_cloud_glue"
                    else "provider-selected"
                ),
                "package_artifact_ids": [],
                "terraform_object_ids": sorted(
                    terraform_ids_by_owner[implementation_id]
                ),
                "runtime_entrypoint": definition["service_id"],
                "platform_owned_fields": sorted(
                    definition.get("dimensions", {}).keys()
                ),
                "user_owned_fields": [],
                "required_permission_capabilities": [f"provider capability for {slot}"],
                "observable_signals": [
                    "calculation evidence and deployment operation logs"
                ],
                "source_references": [
                    _source(
                        "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
                        f"components.{component_key}",
                    )
                ],
            }
        )

    user_artifacts = [
        item for item in artifacts if item["source_key"].startswith("user-template:")
    ]
    for item in user_artifacts:
        token = _slug(item["source_key"].removeprefix("user-template:"))
        records.append(
            {
                "component_id": f"component.user-template.{token}",
                "implementation_id": f"implementation.platform.user-template.{token}",
                "responsibility_id": "responsibility.user-extension",
                "provider": "platform",
                "kind": "user-extension",
                "deployment_lifecycle": "feature-gated",
                "package_artifact_ids": [f"artifact.platform.user-template.{token}"],
                "terraform_object_ids": [],
                "runtime_entrypoint": item["handler"],
                "platform_owned_fields": ["package validation and provider wrapper"],
                "user_owned_fields": ["function source and dependencies"],
                "required_permission_capabilities": [
                    "bounded user function invocation"
                ],
                "observable_signals": ["function build hash and provider logs"],
                "source_references": [_source(item["path"], "template root")],
            }
        )
    for item in artifacts:
        if item["source_key"].startswith("user-package-base:"):
            token = _slug(item["function_name"])
            records.append(
                {
                    "component_id": (
                        f"component.{item['provider']}.user-package-base.{token}"
                    ),
                    "implementation_id": (
                        f"implementation.{item['provider']}.user-package-base.{token}"
                    ),
                    "responsibility_id": "responsibility.user-extension",
                    "provider": item["provider"],
                    "kind": "user-extension",
                    "deployment_lifecycle": "feature-gated",
                    "package_artifact_ids": [
                        f"artifact.{item['provider']}.wrapper.{token}"
                    ],
                    "terraform_object_ids": [],
                    "runtime_entrypoint": item["handler"],
                    "platform_owned_fields": ["provider wrapper and runtime envelope"],
                    "user_owned_fields": [
                        "processor implementation merged at package time"
                    ],
                    "required_permission_capabilities": [
                        "bounded user function invocation"
                    ],
                    "observable_signals": ["function build hash and provider logs"],
                    "source_references": [_source(item["path"], item["handler"])],
                }
            )
        elif item["source_key"].startswith("registry-excluded-source:"):
            token = _slug(item["function_name"])
            records.append(
                {
                    "component_id": f"component.registry-excluded.{token}",
                    "implementation_id": (
                        f"implementation.{item['provider']}.registry-excluded.{token}"
                    ),
                    "responsibility_id": "responsibility.l4.twin-state",
                    "provider": item["provider"],
                    "kind": "function",
                    "deployment_lifecycle": "unsupported",
                    "package_artifact_ids": [
                        f"artifact.{item['provider']}.source.{token}"
                    ],
                    "terraform_object_ids": [],
                    "runtime_entrypoint": item["handler"],
                    "platform_owned_fields": [
                        "source file only; excluded by live registry"
                    ],
                    "user_owned_fields": [],
                    "required_permission_capabilities": [],
                    "observable_signals": [],
                    "source_references": [
                        _source(item["path"], "registry-excluded source")
                    ],
                }
            )
    return sorted(records, key=lambda item: item["implementation_id"])


def _build_artifacts(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for item in sources:
        if not item["exists"]:
            continue
        if item["source_key"].startswith("static:"):
            artifact_id = (
                f"artifact.{item['provider']}.function.{_slug(item['function_name'])}"
            )
            _, owner = _function_component_ids(item["provider"], item["function_name"])
            kind = "static-package"
            builder = f"builder.{item['provider']}.static"
        elif item["source_key"].startswith("user-template:"):
            token = _slug(item["source_key"].removeprefix("user-template:"))
            artifact_id = f"artifact.platform.user-template.{token}"
            owner = f"implementation.platform.user-template.{token}"
            kind = "template"
            builder = "builder.provider-selected.user-package"
        elif item["source_key"].startswith("user-package-base:"):
            token = _slug(item["function_name"])
            artifact_id = f"artifact.{item['provider']}.wrapper.{token}"
            owner = f"implementation.{item['provider']}.user-package-base.{token}"
            kind = "wrapper-library"
            builder = f"builder.{item['provider']}.user-package"
        else:
            token = _slug(item["function_name"])
            artifact_id = f"artifact.{item['provider']}.source.{token}"
            owner = f"implementation.{item['provider']}.registry-excluded.{token}"
            kind = "source"
            builder = "builder.registry-excluded"
        records.append(
            {
                "artifact_id": artifact_id,
                "provider": item["provider"],
                "artifact_kind": kind,
                "repository_paths": [item["path"]],
                "builder_adapter_id": builder,
                "runtime_handler": item["handler"],
                "included_path_rules": [
                    "validated files below the declared source root"
                ],
                "excluded_path_rules": [
                    "credentials, runtime state, caches, and generated package bytes"
                ],
                "owning_implementation_ids": [owner],
                "evidence_status": "verified",
                "source_references": [
                    _source(
                        item["path"],
                        item["handler"]
                        if kind == "static-package"
                        else "template root",
                    ),
                    _source(
                        "3-cloud-deployer/src/providers/terraform/package_builders/user.py"
                        if kind in {"template", "wrapper-library"}
                        else "3-cloud-deployer/src/function_registry.py"
                        if kind == "source"
                        else "3-cloud-deployer/src/providers/terraform/package_builder.py",
                        "build_user_packages"
                        if kind in {"template", "wrapper-library"}
                        else "STATIC_FUNCTIONS"
                        if kind == "source"
                        else "build_all_packages",
                    ),
                ],
            }
        )
    for provider in PROVIDERS:
        path = {
            "aws": "3-cloud-deployer/src/providers/aws/lambda_functions/_shared",
            "azure": "3-cloud-deployer/src/providers/azure/azure_functions/_shared",
            "gcp": "3-cloud-deployer/src/providers/gcp/cloud_functions/_shared",
        }[provider]
        records.append(
            {
                "artifact_id": f"artifact.{provider}.shared-wrapper-library",
                "provider": provider,
                "artifact_kind": "wrapper-library",
                "repository_paths": [path],
                "builder_adapter_id": f"builder.{provider}.static",
                "runtime_handler": "provider shared runtime helpers",
                "included_path_rules": [
                    "shared Python modules selected by package adapter"
                ],
                "excluded_path_rules": [
                    "credentials, caches, and generated package bytes"
                ],
                "owning_implementation_ids": [
                    f"implementation.{provider}.terraform-root"
                ],
                "evidence_status": "verified",
                "source_references": [_source(path, "shared package root")],
            }
        )
    return sorted(records, key=lambda item: item["artifact_id"])


def _catalog_owners_for_slot(
    contract: dict[str, Any], provider: str, slot: str
) -> list[str]:
    return sorted(
        _catalog_component_ids(component_key)[1]
        for component_key, definition in contract["components"].items()
        if definition["provider"] == provider and definition["slot_id"] == slot
    )


def _terraform_owner_ids(item: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    """Resolve ownership through an explicit file/slot audit map."""

    object_provider = _provider_for_terraform(item)
    filename = Path(item["path"]).name
    provider_from_file = next(
        (provider for provider in PROVIDERS if filename.startswith(f"{provider}_")),
        None,
    )
    infrastructure_provider = provider_from_file or object_provider
    owners = {
        f"implementation.{infrastructure_provider}.terraform-root"
        if infrastructure_provider in PROVIDERS
        else "implementation.platform.terraform-root"
    }
    if provider_from_file:
        for slot in TERRAFORM_FILE_SLOT_OWNERS.get(filename, ()):
            owners.update(_catalog_owners_for_slot(contract, provider_from_file, slot))
    return sorted(owners)


def _build_terraform_objects(
    extracted: list[dict[str, Any]],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    records = []
    for item in extracted:
        provider = _provider_for_terraform(item)
        role = {
            "resource": "resource",
            "data": "dependency",
            "output": "output",
            "module": "dependency",
            "variable": "input",
            "local": "calculation",
        }[item["kind"]]
        records.append(
            {
                "terraform_object_id": _terraform_id(item),
                "provider": provider,
                "object_kind": item["kind"],
                "terraform_address": item["address"],
                "module_path": "3-cloud-deployer/src/terraform",
                "owning_implementation_ids": _terraform_owner_ids(item, contract),
                "binding_role": role,
                "sensitive": bool(item["sensitive"]),
                "evidence_status": "verified",
                "source_references": [
                    _source(f"3-cloud-deployer/{item['path']}", item["address"])
                ],
            }
        )
    return sorted(records, key=lambda item: item["terraform_object_id"])


def _representative_component(
    contract: dict[str, Any], slot: str, provider: str
) -> tuple[str, str]:
    requirement = contract["slot_requirements"][slot][provider]
    key = requirement["required_components"][0]
    return _catalog_component_ids(key)


def _representative_component_reference(
    contract: dict[str, Any], slot: str, provider: str
) -> str:
    requirement = contract["slot_requirements"][slot][provider]
    key = requirement["required_components"][0]
    return _source(
        "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
        f"components.{key}",
    )


def _edge_record(
    *,
    edge_id: str,
    source: tuple[str, str],
    destination: tuple[str, str],
    edge_kind: str,
    protocol: str,
    semantics: str,
    trust: str,
    classification: str,
    references: list[str],
    transfer_route_id: str | None = None,
    phase: str = "runtime",
    reference_mechanism: str = "resolved deployment selection",
    cost_owner_ids: list[str] | None = None,
    payload_contract: str = "current provider adapter contract",
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "source_component_id": source[0],
        "destination_component_id": destination[0],
        "source_implementation_id": source[1],
        "destination_implementation_id": destination[1],
        "phase": phase,
        "edge_kind": edge_kind,
        "protocol": protocol,
        "payload_contract": payload_contract,
        "invocation_semantics": semantics,
        "delivery_guarantee": "provider-native service contract",
        "retry_policy": "provider-native defaults; no cross-provider override",
        "dead_letter_policy": "none declared by the cross-project baseline",
        "idempotency_scope": "component-specific handling only",
        "ordering_scope": "no global ordering guarantee",
        "trust_boundary_id": trust,
        "authentication": "provider workload identity or service-managed authorization",
        "transfer_route_id": transfer_route_id,
        "cost_owner_ids": cost_owner_ids or ["cost.transfer.baseline"],
        "observability": [
            "calculation evidence",
            "provider logs",
            "deployment operation events",
        ],
        "reference_mechanism": reference_mechanism,
        "classification": classification,
        "evidence_status": "verified",
        "source_references": references,
    }


def _build_edges(
    contract: dict[str, Any],
    functions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    path_reference = _source(
        "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
        "build_baseline_edge_workloads",
    )
    for provider in ("aws", "azure"):
        for token, source_slot, destination_slot in BASELINE_EDGES:
            record = _edge_record(
                edge_id=f"edge.runtime.{provider}.{token}",
                source=_representative_component(contract, source_slot, provider),
                destination=_representative_component(
                    contract, destination_slot, provider
                ),
                edge_kind="provider_trigger",
                protocol=f"{provider} provider-native service integration",
                semantics="asynchronous",
                trust="trust.provider-account",
                classification="baseline_required",
                references=[
                    path_reference,
                    _representative_component_reference(
                        contract, source_slot, provider
                    ),
                    _representative_component_reference(
                        contract, destination_slot, provider
                    ),
                ],
            )
            if token == "l4-to-l5":
                record.update(
                    {
                        "protocol": (
                            "Optimizer-modeled L4-to-L5 query-result edge; no "
                            "matching Deployer L4 datasource binding"
                        ),
                        "delivery_guarantee": (
                            "not an evidenced deployed runtime edge"
                        ),
                        "retry_policy": "none",
                        "dead_letter_policy": "none",
                        "idempotency_scope": "none",
                        "ordering_scope": "none",
                        "authentication": (
                            "not established for the modeled L4-to-L5 edge"
                        ),
                        "reference_mechanism": ("Optimizer baseline segment only"),
                        "classification": "unsafe_debt",
                        "source_references": [
                            path_reference,
                            _representative_component_reference(
                                contract, source_slot, provider
                            ),
                            _representative_component_reference(
                                contract, destination_slot, provider
                            ),
                            _source(
                                f"3-cloud-deployer/src/providers/terraform/{provider}_deployer.py",
                                f"configure_{provider}_grafana",
                            ),
                        ],
                    }
                )
            records.append(record)
    for token, source_slot, destination_slot in BASELINE_EDGES[:4]:
        records.append(
            _edge_record(
                edge_id=f"edge.runtime.gcp.{token}",
                source=_representative_component(contract, source_slot, "gcp"),
                destination=_representative_component(
                    contract, destination_slot, "gcp"
                ),
                edge_kind="provider_trigger",
                protocol="gcp provider-native service integration",
                semantics="asynchronous",
                trust="trust.provider-account",
                classification="baseline_required",
                references=[
                    path_reference,
                    _representative_component_reference(contract, source_slot, "gcp"),
                    _representative_component_reference(
                        contract, destination_slot, "gcp"
                    ),
                ],
            )
        )

    mixed_providers = ("aws", "azure", "gcp", "gcp", "gcp", "aws", "azure")
    for index, (token, source_slot, destination_slot) in enumerate(BASELINE_EDGES):
        source_provider = mixed_providers[index]
        destination_provider = mixed_providers[index + 1]
        record = _edge_record(
            edge_id=f"edge.runtime.mixed.{token}",
            source=_representative_component(contract, source_slot, source_provider),
            destination=_representative_component(
                contract, destination_slot, destination_provider
            ),
            edge_kind="http",
            protocol=f"{source_provider}-to-{destination_provider} destination bridge",
            semantics="asynchronous",
            trust="trust.cross-provider",
            classification="baseline_required",
            references=[
                path_reference,
                _representative_component_reference(
                    contract, source_slot, source_provider
                ),
                _representative_component_reference(
                    contract, destination_slot, destination_provider
                ),
                _source(
                    "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
                    f"cross_cloud_glue_policy.boundaries.{index if index < 4 else 4}",
                ),
            ],
            transfer_route_id=f"transfer.dynamic.{token}",
        )
        if token == "l4-to-l5":
            record.update(
                {
                    "protocol": (
                        "Optimizer-priced L4-to-L5 edge without a cross-provider "
                        "Deployer datasource binding"
                    ),
                    "delivery_guarantee": "not executable when L5 differs from L3 hot",
                    "retry_policy": "none",
                    "dead_letter_policy": "none",
                    "idempotency_scope": "none",
                    "ordering_scope": "none",
                    "authentication": "no cross-provider L5 reader binding exists",
                    "reference_mechanism": (
                        "missing from cross_cloud_glue_policy; provider-local "
                        "post-deployment reader output is required"
                    ),
                    "classification": "unsafe_debt",
                    "source_references": [
                        path_reference,
                        _representative_component_reference(
                            contract, source_slot, source_provider
                        ),
                        _representative_component_reference(
                            contract, destination_slot, destination_provider
                        ),
                        _source(
                            "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
                            "cross_cloud_glue_policy.boundaries",
                        ),
                        _source(
                            "3-cloud-deployer/src/providers/terraform/aws_deployer.py",
                            "configure_aws_grafana",
                        ),
                        _source(
                            "3-cloud-deployer/src/providers/terraform/azure_deployer.py",
                            "configure_azure_grafana",
                        ),
                    ],
                }
            )
        records.append(record)

    for provider in ("aws", "azure"):
        records.append(
            _edge_record(
                edge_id=f"edge.runtime.{provider}.l3-hot-to-l5-reader",
                source=_function_component_ids(provider, "hot-reader"),
                destination=_representative_component(
                    contract, "l5_visualization", provider
                ),
                edge_kind="http",
                protocol="Grafana JSON datasource to provider-local hot-reader URL",
                semantics="synchronous",
                trust="trust.provider-account",
                classification="unsafe_debt",
                references=[
                    _source(
                        f"3-cloud-deployer/src/providers/terraform/{provider}_deployer.py",
                        f"configure_{provider}_grafana",
                    ),
                    _source(
                        f"3-cloud-deployer/src/terraform/{provider}_grafana.tf",
                        "Grafana datasource configuration",
                    ),
                ],
                reference_mechanism=(
                    f"{provider}_l3_hot_reader_url Terraform output consumed "
                    "after apply"
                ),
                cost_owner_ids=[
                    "cost.l3-hot-storage",
                    "cost.l5-visualization",
                ],
                payload_contract="Grafana JSON datasource to Hot Reader HTTP response",
            )
        )

    function_names = {item["name"] for item in functions}
    artifact_references_by_owner = {
        artifact["owning_implementation_ids"][0]: artifact["source_references"]
        for artifact in artifacts
        if artifact["owning_implementation_ids"]
    }
    function_links = (
        ("dispatcher", "processor_wrapper", "provider_trigger"),
        ("processor_wrapper", "persister", "http"),
        ("hot-to-cold-mover", "cold-writer", "schedule"),
        ("cold-to-archive-mover", "archive-writer", "schedule"),
    )
    for provider in PROVIDERS:
        for source_name, destination_name, kind in function_links:
            if {source_name, destination_name} - function_names:
                continue
            source = _function_component_ids(provider, source_name)
            destination = _function_component_ids(provider, destination_name)
            records.append(
                _edge_record(
                    edge_id=(
                        f"edge.runtime.{provider}.function-"
                        f"{_slug(source_name)}-to-{_slug(destination_name)}"
                    ),
                    source=source,
                    destination=destination,
                    edge_kind=kind,
                    protocol=f"{provider} function invocation",
                    semantics="scheduled" if kind == "schedule" else "asynchronous",
                    trust="trust.user-code"
                    if source_name == "processor_wrapper"
                    else "trust.provider-account",
                    classification="implementation_internal",
                    references=list(
                        dict.fromkeys(
                            [
                                _source(
                                    "3-cloud-deployer/src/function_registry.py",
                                    f"FunctionDefinition name={source_name}",
                                ),
                                *artifact_references_by_owner.get(source[1], []),
                                *artifact_references_by_owner.get(destination[1], []),
                            ]
                        )
                    ),
                    cost_owner_ids=[
                        COST_BY_RESPONSIBILITY[FUNCTION_RESPONSIBILITY[source_name]]
                    ],
                    reference_mechanism=(
                        "static function registry plus both package entrypoints"
                    ),
                    payload_contract=f"{provider} function runtime envelope",
                )
            )

    deployer = ("component.platform.deployer", "implementation.platform.deployer")
    for artifact in artifacts:
        owner = artifact["owning_implementation_ids"][0]
        if ".function." not in owner:
            continue
        provider = artifact["provider"]
        function_name = owner.rsplit(".", 1)[-1]
        target = (f"component.function.{function_name}", owner)
        records.append(
            _edge_record(
                edge_id=f"edge.binding.{provider}.package-{function_name}",
                source=deployer,
                destination=target,
                edge_kind="package_binding",
                protocol="content-addressed ZIP package input",
                semantics="deployment_only",
                trust="trust.management-to-deployer",
                classification="implementation_internal",
                references=artifact["source_references"],
                phase="deployment",
                reference_mechanism=artifact["artifact_id"],
                cost_owner_ids=["cost.platform.orchestration"],
            )
        )

    records.extend(
        [
            _edge_record(
                edge_id="edge.runtime.flutter-to-management",
                source=(
                    "component.platform.flutter",
                    "implementation.platform.flutter",
                ),
                destination=(
                    "component.platform.management-api",
                    "implementation.platform.management-api",
                ),
                edge_kind="http",
                protocol="HTTPS JSON and text/event-stream",
                semantics="synchronous",
                trust="trust.flutter-to-management",
                classification="baseline_required",
                references=[
                    _source(
                        "twin2multicloud_flutter/lib/services/management_api.dart",
                        "ManagementApi",
                    )
                ],
                cost_owner_ids=["cost.platform.orchestration"],
            ),
            _edge_record(
                edge_id="edge.runtime.management-to-optimizer",
                source=(
                    "component.platform.management-api",
                    "implementation.platform.management-api",
                ),
                destination=(
                    "component.platform.optimizer",
                    "implementation.platform.optimizer",
                ),
                edge_kind="http",
                protocol="HTTP JSON calculation contract",
                semantics="synchronous",
                trust="trust.management-to-optimizer",
                classification="baseline_required",
                references=[
                    _source(
                        "twin2multicloud_backend/src/services/cost_calculation_run_service.py",
                        "CostCalculationRunService",
                    )
                ],
                cost_owner_ids=["cost.platform.orchestration"],
            ),
            _edge_record(
                edge_id="edge.binding.management-to-deployer",
                source=(
                    "component.platform.management-api",
                    "implementation.platform.management-api",
                ),
                destination=(
                    "component.platform.deployer",
                    "implementation.platform.deployer",
                ),
                edge_kind="http",
                protocol="private one-use deployment operation package",
                semantics="deployment_only",
                trust="trust.management-to-deployer",
                classification="baseline_required",
                references=[
                    _source(
                        "twin2multicloud_backend/src/services/deployment_service.py",
                        "deployment package projection",
                    )
                ],
                phase="deployment",
                reference_mechanism="selected resolved deployment specification and credential selection",
                cost_owner_ids=["cost.platform.orchestration"],
            ),
        ]
    )
    return sorted(records, key=lambda item: item["edge_id"])


def _build_cost_owners(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    implementations_by_responsibility: dict[str, list[str]] = defaultdict(list)
    for item in components:
        implementations_by_responsibility[item["responsibility_id"]].append(
            item["implementation_id"]
        )
    records = []
    for slot, responsibility_id in RESPONSIBILITY_BY_SLOT.items():
        kind = (
            "transfer"
            if slot == "cross_cloud_glue"
            else "workflow"
            if slot == "transition_runtime"
            else "storage"
            if slot.startswith("l3_")
            else "service"
        )
        records.append(
            {
                "cost_owner_id": f"cost.{_slug(slot)}",
                "cost_kind": kind,
                "responsibility_ids": [responsibility_id],
                "owning_implementation_ids": sorted(
                    implementations_by_responsibility[responsibility_id]
                ),
                "pricing_intent_ids": [f"pricing-intent.{slot}"],
                "formula_ids": [f"formula.{slot}"],
                "transfer_route_ids": (
                    [f"transfer.dynamic.{edge[0]}" for edge in BASELINE_EDGES]
                    if slot == "cross_cloud_glue"
                    else []
                ),
                "evidence_status": "verified",
                "source_references": [
                    _source(
                        "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
                        "CompletePathEvaluation",
                    )
                ],
            }
        )
    records.extend(
        [
            {
                "cost_owner_id": "cost.transfer.baseline",
                "cost_kind": "transfer",
                "responsibility_ids": ["responsibility.cross-cloud-glue"],
                "owning_implementation_ids": sorted(
                    implementations_by_responsibility["responsibility.cross-cloud-glue"]
                ),
                "pricing_intent_ids": ["pricing-intent.cross-provider-transfer"],
                "formula_ids": ["formula.complete-path-transfer-cost"],
                "transfer_route_ids": [
                    f"transfer.dynamic.{edge[0]}" for edge in BASELINE_EDGES
                ],
                "evidence_status": "verified",
                "source_references": [
                    _source(
                        "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
                        "transfer_cost",
                    )
                ],
            },
            {
                "cost_owner_id": "cost.platform.orchestration",
                "cost_kind": "account",
                "responsibility_ids": ["responsibility.platform.orchestration"],
                "owning_implementation_ids": sorted(
                    implementations_by_responsibility[
                        "responsibility.platform.orchestration"
                    ]
                ),
                "pricing_intent_ids": ["pricing-intent.outside-twin-path"],
                "formula_ids": ["formula.not-included-in-optimizer-total"],
                "transfer_route_ids": [],
                "evidence_status": "verified",
                "source_references": [
                    _source(
                        "twin2multicloud_backend/src/services/deployment_service.py",
                        "DeploymentPackage",
                    )
                ],
            },
            {
                "cost_owner_id": "cost.user-extension",
                "cost_kind": "function",
                "responsibility_ids": ["responsibility.user-extension"],
                "owning_implementation_ids": sorted(
                    implementations_by_responsibility["responsibility.user-extension"]
                ),
                "pricing_intent_ids": ["pricing-intent.l2-user-runtime"],
                "formula_ids": ["formula.l2-processing"],
                "transfer_route_ids": [],
                "evidence_status": "verified",
                "source_references": [
                    _source(
                        "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
                        "L2",
                    )
                ],
            },
        ]
    )
    return sorted(records, key=lambda item: item["cost_owner_id"])


def _build_trust_boundaries() -> list[dict[str, Any]]:
    definitions = (
        (
            "trust.provider-account",
            "Twin component",
            "Provider-managed service in the same selected account",
            "cloud-account",
            "provider workload identity and service-managed authorization",
            "Deployer-created workload identity",
            "user-selected provider credential authorizes creation only",
            "provider transport encryption",
            "3-cloud-deployer/src/terraform/main.tf",
            "provider configuration",
        ),
        (
            "trust.cross-provider",
            "Source provider workload",
            "Destination provider bridge",
            "provider",
            "destination function authentication configured at deployment",
            "destination provider workload identity",
            "private deployment operation package",
            "HTTPS",
            "3-cloud-deployer/src/function_registry.py",
            "L0 cross-cloud glue",
        ),
        (
            "trust.user-code",
            "Platform wrapper",
            "User-supplied function code",
            "user-code",
            "provider function invocation identity",
            "platform wrapper",
            "provider runtime configuration",
            "provider transport encryption or same-process boundary",
            "3-cloud-deployer/src/providers/terraform/package_builders/user.py",
            "build_user_packages",
        ),
        (
            "trust.flutter-to-management",
            "Flutter client",
            "Management API",
            "management",
            "authenticated Management API session",
            "end user",
            "Management API",
            "HTTPS",
            "twin2multicloud_flutter/lib/services/management_api.dart",
            "ManagementApi",
        ),
        (
            "trust.management-to-optimizer",
            "Management API",
            "Optimizer",
            "service",
            "private service-network request",
            "Management API service",
            "runtime operator",
            "container-network transport",
            "twin2multicloud_backend/src/services/cost_calculation_run_service.py",
            "optimizer request",
        ),
        (
            "trust.management-to-deployer",
            "Management API",
            "Deployer",
            "service",
            "private one-use operation package and service request",
            "Management API service",
            "Management API credential store",
            "container-network transport; provider API TLS",
            "twin2multicloud_backend/src/services/deployment_service.py",
            "deployment package",
        ),
    )
    return [
        {
            "trust_boundary_id": item[0],
            "source_scope": item[1],
            "destination_scope": item[2],
            "boundary_kind": item[3],
            "authentication": item[4],
            "identity_owner": item[5],
            "credential_owner": item[6],
            "encryption": item[7],
            "evidence_status": "verified",
            "source_references": [_source(item[8], item[9])],
        }
        for item in definitions
    ]


def _build_fixed_assumptions() -> list[dict[str, Any]]:
    cheapest_consumers = [
        _source(path, anchors[0])
        for path, anchors in MANAGEMENT_CHEAPEST_CONSUMERS.items()
    ]
    provider_key_consumers = [
        _source(path, anchors[0]) for path, anchors in PROVIDER_KEY_CONSUMERS.items()
    ]
    fixed_slot_consumers = [
        _source(path, anchors[0]) for path, anchors in FIXED_SLOT_CONSUMERS.items()
    ]
    assumptions = [
        (
            "assumption.optimizer-slot-order",
            ["optimizer", "management-api", "flutter"],
            "Seven slots remain ordered L1, L2, L3_hot, L3_cool, L3_archive, L4, L5.",
            [
                _source(
                    "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
                    "LAYER_ORDER",
                ),
                *fixed_slot_consumers,
            ],
            "Costs, selected providers, and UI labels bind to the wrong layer.",
            "extract_optimizer_shape and allowlisted Flutter anchors",
            "Phase 8.2 and 8.7",
        ),
        (
            "assumption.cheapest-columns",
            ["management-api"],
            "Optimizer selections persist in seven cheapest_l* columns.",
            cheapest_consumers,
            "Selected-run persistence and deployment projection diverge.",
            "allowlisted Management fixed-field anchors",
            "Phase 8.4",
        ),
        (
            "assumption.deployer-provider-keys",
            ["optimizer", "management-api", "deployer", "flutter"],
            "Deployment config uses seven layer_*_provider keys and maps GCP to google.",
            [
                _source(
                    "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
                    "slots",
                ),
                *provider_key_consumers,
            ],
            "Package building or Terraform selection targets the wrong provider.",
            "deployment contract plus allowlisted source anchors",
            "Phase 8.2 through 8.6",
        ),
        (
            "assumption.function-output-suffix",
            ["deployer"],
            "Static function outputs use the registry suffix _function_name.",
            [
                _source(
                    "3-cloud-deployer/src/function_registry.py",
                    "terraform_output_suffix",
                )
            ],
            "Post-deployment function binding cannot resolve an output.",
            "complete Function Registry extraction",
            "Phase 8.6",
        ),
        (
            "assumption.provider-handler-convention",
            ["deployer"],
            "AWS, Azure, and GCP static handlers use registry-owned provider roots and handler filenames.",
            [_source("3-cloud-deployer/src/function_registry.py", "PROVIDER_PATHS")],
            "A registered function has no buildable source handler.",
            "extract_artifact_sources",
            "Phase 8.3 and 8.6",
        ),
        (
            "assumption.user-function-paths",
            ["deployer"],
            "User processors, event actions, and feedback are discovered under provider-selected operation-package roots.",
            [
                _source(
                    "3-cloud-deployer/src/providers/terraform/package_builders/user.py",
                    "_UserPackageLayout",
                )
            ],
            "User source is omitted or packaged under the wrong provider adapter.",
            "template inventory and focused package-builder tests",
            "Phase 8.3",
        ),
        (
            "assumption.flutter-fixed-slots",
            ["flutter", "management-api"],
            "Architecture views render fixed slot identifiers and fixed provider service labels.",
            [
                *fixed_slot_consumers,
                *(
                    reference
                    for reference in provider_key_consumers
                    if reference.startswith("twin2multicloud_flutter/")
                ),
            ],
            "Profile-defined components cannot be represented or are mislabeled.",
            "allowlisted Flutter anchors",
            "Phase 8.7",
        ),
    ]
    return [
        {
            "assumption_id": item[0],
            "affected_projects": item[1],
            "convention": item[2],
            "current_consumers": item[3],
            "failure_mode": item[4],
            "automated_drift_test": item[5],
            "phase_8_owner": item[6],
            "source_references": item[3],
        }
        for item in assumptions
    ]


def _build_findings() -> list[dict[str, Any]]:
    return [
        {
            "finding_id": "finding.l5-reader-binding-divergence",
            "category": "functional-completeness",
            "summary": (
                "The Optimizer models L4-to-L5, while AWS and Azure Grafana "
                "post-deployment bind directly to a provider-local L3 hot reader."
            ),
            "affected_entity_ids": [
                "edge.runtime.aws.l4-to-l5",
                "edge.runtime.azure.l4-to-l5",
                "edge.runtime.mixed.l4-to-l5",
                "edge.runtime.aws.l3-hot-to-l5-reader",
                "edge.runtime.azure.l3-hot-to-l5-reader",
                "implementation.platform.optimizer",
                "implementation.platform.deployer",
            ],
            "missing_evidence": (
                "No current cross-provider L5 datasource binding maps the "
                "selected L3 hot reader into the selected L5 provider."
            ),
            "risk": (
                "A cost-ranked path with L5 different from L3 hot can pass the "
                "resolved contract but fail or bind the wrong reader after apply."
            ),
            "phase_8_owner": "Phase 8.1 baseline decision and Phase 8.6 graph resolver",
            "source_references": [
                _source(
                    "2-twin2clouds/backend/calculation_v2/path_optimizer.py",
                    "L4_to_L5",
                ),
                _source(
                    "contracts/resolved-deployment-specification/v1/deployment-dimensions.json",
                    "cross_cloud_glue_policy.boundaries",
                ),
                _source(
                    "3-cloud-deployer/src/providers/terraform/aws_deployer.py",
                    "configure_aws_grafana",
                ),
                _source(
                    "3-cloud-deployer/src/providers/terraform/azure_deployer.py",
                    "configure_azure_grafana",
                ),
            ],
        }
    ]


def build_inventory(
    root: Path | None = None,
    *,
    generated_at: str | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Reconstruct a deterministic inventory from current source registries."""

    root = root or repository_root()
    functions = extract_static_functions()
    extracted_artifacts = extract_artifact_sources(root)
    missing = [
        item["source_key"]
        for item in extracted_artifacts
        if not item["exists"] and item["function_name"] != "event-feedback"
    ]
    if missing:
        raise InventoryCheckError("SOURCE_ENTITY_UNMAPPED", missing)
    contract = extract_deployment_contract(root)
    extract_optimizer_shape(root)
    verify_allowlisted_anchors(root)
    extracted_terraform = extract_terraform_objects()
    artifacts = _build_artifacts(extracted_artifacts)
    terraform = _build_terraform_objects(extracted_terraform, contract)
    components = _build_components(
        contract, functions, extracted_artifacts, extracted_terraform
    )
    inventory: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "inventory_id": INVENTORY_ID,
        "source_commit": source_commit or _git_head(root),
        "audited_source_paths": sorted(AUDITED_SOURCE_PATHS),
        "audited_source_tree_digest": source_tree_digest(root, AUDITED_SOURCE_PATHS),
        "generated_at": generated_at
        or datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "paper_model_references": sorted(PAPER_REFERENCES),
        "responsibilities": _build_responsibilities(),
        "components": components,
        "artifacts": artifacts,
        "terraform_objects": terraform,
        "edges": _build_edges(contract, functions, artifacts),
        "cost_owners": _build_cost_owners(components),
        "trust_boundaries": sorted(
            _build_trust_boundaries(), key=lambda item: item["trust_boundary_id"]
        ),
        "fixed_assumptions": sorted(
            _build_fixed_assumptions(), key=lambda item: item["assumption_id"]
        ),
        "unresolved_findings": _build_findings(),
    }
    inventory["content_digest"] = content_digest(inventory)
    return inventory


def _schema_validate_document(
    root: Path,
    schema_path: Path,
    instance: dict[str, Any],
    *,
    category: str,
) -> None:
    schema = json.loads(
        (root / schema_path).read_text(encoding="utf-8")
    )
    payload = json.dumps({"schema": schema, "instance": instance})
    script = r"""
import json, sys
from jsonschema import Draft202012Validator, FormatChecker
payload = json.load(sys.stdin)
validator = Draft202012Validator(payload["schema"], format_checker=FormatChecker())
errors = sorted(validator.iter_errors(payload["instance"]), key=lambda item: list(item.path))
print(json.dumps([
    {"path": ".".join(str(part) for part in error.path) or "$", "message": error.message[:240]}
    for error in errors[:100]
]))
"""
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            deployer_container(root),
            "python",
            "-c",
            script,
        ],
        input=payload,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if completed.returncode:
        raise InventoryCheckError(
            category, ["JSON Schema validator unavailable"]
        )
    errors = json.loads(completed.stdout)
    if errors:
        raise InventoryCheckError(
            category,
            [f"{item['path']}: {item['message']}" for item in errors],
        )


def _schema_validate(root: Path, inventory: dict[str, Any]) -> None:
    _schema_validate_document(
        root,
        Path("contracts/architecture-inventory/v1/current-graph.schema.json"),
        inventory,
        category="SCHEMA_INVALID",
    )


def _check_ids_and_references(inventory: dict[str, Any]) -> None:
    primary = {
        "responsibilities": "responsibility_id",
        "components": "implementation_id",
        "artifacts": "artifact_id",
        "terraform_objects": "terraform_object_id",
        "edges": "edge_id",
        "cost_owners": "cost_owner_id",
        "trust_boundaries": "trust_boundary_id",
        "fixed_assumptions": "assumption_id",
        "unresolved_findings": "finding_id",
    }
    all_primary: list[str] = []
    for collection, key in primary.items():
        all_primary.extend(item[key] for item in inventory[collection])
    duplicates = [value for value in set(all_primary) if all_primary.count(value) > 1]
    if duplicates:
        raise InventoryCheckError("DUPLICATE_ID", duplicates)

    implementations = {
        item["implementation_id"]: item for item in inventory["components"]
    }
    logical: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inventory["components"]:
        logical[item["component_id"]].append(item)
    divergent = []
    semantic_fields = (
        "responsibility_id",
        "kind",
        "runtime_entrypoint",
        "platform_owned_fields",
        "user_owned_fields",
    )
    for component_id, variants in logical.items():
        baseline = variants[0]
        if any(
            any(item[field] != baseline[field] for field in semantic_fields)
            for item in variants[1:]
        ):
            divergent.append(component_id)
    if divergent:
        raise InventoryCheckError("DUPLICATE_ID", divergent)

    responsibility_ids = {
        item["responsibility_id"] for item in inventory["responsibilities"]
    }
    component_ids = set(logical)
    artifact_ids = {item["artifact_id"] for item in inventory["artifacts"]}
    terraform_ids = {
        item["terraform_object_id"] for item in inventory["terraform_objects"]
    }
    cost_ids = {item["cost_owner_id"] for item in inventory["cost_owners"]}
    trust_ids = {item["trust_boundary_id"] for item in inventory["trust_boundaries"]}
    unresolved: list[str] = []
    for item in inventory["responsibilities"]:
        unresolved.extend(
            f"{item['responsibility_id']}->{target}"
            for target in item["cost_owner_ids"]
            if target not in cost_ids
        )
    for item in inventory["components"]:
        if item["responsibility_id"] not in responsibility_ids:
            unresolved.append(
                f"{item['implementation_id']}->{item['responsibility_id']}"
            )
        unresolved.extend(
            f"{item['implementation_id']}->{target}"
            for target in item["package_artifact_ids"]
            if target not in artifact_ids
        )
        unresolved.extend(
            f"{item['implementation_id']}->{target}"
            for target in item["terraform_object_ids"]
            if target not in terraform_ids
        )
    for item in inventory["artifacts"]:
        unresolved.extend(
            f"{item['artifact_id']}->{target}"
            for target in item["owning_implementation_ids"]
            if target not in implementations
        )
    for item in inventory["terraform_objects"]:
        unresolved.extend(
            f"{item['terraform_object_id']}->{target}"
            for target in item["owning_implementation_ids"]
            if target not in implementations
        )
    for item in inventory["edges"]:
        pairs = (
            ("source_component_id", component_ids),
            ("destination_component_id", component_ids),
            ("source_implementation_id", implementations),
            ("destination_implementation_id", implementations),
            ("trust_boundary_id", trust_ids),
        )
        for key, known in pairs:
            if item[key] not in known:
                unresolved.append(f"{item['edge_id']}->{item[key]}")
        if item["source_implementation_id"] in implementations and (
            implementations[item["source_implementation_id"]]["component_id"]
            != item["source_component_id"]
        ):
            unresolved.append(f"{item['edge_id']}->source-logical-mismatch")
        if item["destination_implementation_id"] in implementations and (
            implementations[item["destination_implementation_id"]]["component_id"]
            != item["destination_component_id"]
        ):
            unresolved.append(f"{item['edge_id']}->destination-logical-mismatch")
        unresolved.extend(
            f"{item['edge_id']}->{target}"
            for target in item["cost_owner_ids"]
            if target not in cost_ids
        )
    for item in inventory["cost_owners"]:
        unresolved.extend(
            f"{item['cost_owner_id']}->{target}"
            for target in item["responsibility_ids"]
            if target not in responsibility_ids
        )
        unresolved.extend(
            f"{item['cost_owner_id']}->{target}"
            for target in item["owning_implementation_ids"]
            if target not in implementations
        )
    known_entity_ids = {
        *responsibility_ids,
        *component_ids,
        *implementations,
        *artifact_ids,
        *terraform_ids,
        *{item["edge_id"] for item in inventory["edges"]},
        *cost_ids,
        *trust_ids,
        *{item["assumption_id"] for item in inventory["fixed_assumptions"]},
    }
    for item in inventory["unresolved_findings"]:
        unresolved.extend(
            f"{item['finding_id']}->{target}"
            for target in item["affected_entity_ids"]
            if target not in known_entity_ids
        )
    if unresolved:
        raise InventoryCheckError("REFERENCE_UNRESOLVED", unresolved)


def _check_source_reconciliation(root: Path, inventory: dict[str, Any]) -> None:
    functions = extract_static_functions()
    expected_functions = {
        _function_component_ids(provider, item["name"])[1]
        for item in functions
        for provider in item["providers"]
    }
    contract = extract_deployment_contract(root)
    expected_catalog = {
        _catalog_component_ids(key)[1] for key in contract["components"]
    }
    extracted_artifacts = extract_artifact_sources(root)
    expected_implementations = {
        "implementation.platform.optimizer",
        "implementation.platform.management-api",
        "implementation.platform.deployer",
        "implementation.platform.flutter",
        "implementation.platform.terraform-root",
        "implementation.aws.terraform-root",
        "implementation.azure.terraform-root",
        "implementation.gcp.terraform-root",
        *expected_functions,
        *expected_catalog,
    }
    for item in extracted_artifacts:
        if item["source_key"].startswith("user-template:"):
            expected_implementations.add(
                "implementation.platform.user-template."
                f"{_slug(item['source_key'].removeprefix('user-template:'))}"
            )
        elif item["source_key"].startswith("user-package-base:"):
            expected_implementations.add(
                f"implementation.{item['provider']}.user-package-base."
                f"{_slug(item['function_name'])}"
            )
        elif item["source_key"].startswith("registry-excluded-source:"):
            expected_implementations.add(
                f"implementation.{item['provider']}.registry-excluded."
                f"{_slug(item['function_name'])}"
            )
    actual_implementations = {
        item["implementation_id"] for item in inventory["components"]
    }
    expected_terraform = {
        (item["kind"], item["address"], item["path"])
        for item in extract_terraform_objects()
    }
    actual_terraform = {
        (
            item["object_kind"],
            item["terraform_address"],
            item["source_references"][0]
            .split("#", 1)[0]
            .removeprefix("3-cloud-deployer/"),
        )
        for item in inventory["terraform_objects"]
    }
    expected_artifacts = set()
    for item in extracted_artifacts:
        if not item["exists"]:
            continue
        if item["source_key"].startswith("static:"):
            artifact_id = (
                f"artifact.{item['provider']}.function.{_slug(item['function_name'])}"
            )
        elif item["source_key"].startswith("user-template:"):
            artifact_id = (
                "artifact.platform.user-template."
                f"{_slug(item['source_key'].removeprefix('user-template:'))}"
            )
        elif item["source_key"].startswith("user-package-base:"):
            artifact_id = (
                f"artifact.{item['provider']}.wrapper.{_slug(item['function_name'])}"
            )
        else:
            artifact_id = (
                f"artifact.{item['provider']}.source.{_slug(item['function_name'])}"
            )
        expected_artifacts.add(artifact_id)
    expected_artifacts.update(
        f"artifact.{provider}.shared-wrapper-library" for provider in PROVIDERS
    )
    actual_artifacts = {
        item["artifact_id"]
        for item in inventory["artifacts"]
        if item["artifact_kind"]
        in {"static-package", "template", "wrapper-library", "source"}
    }
    expected_edges = {
        "edge.runtime.flutter-to-management",
        "edge.runtime.management-to-optimizer",
        "edge.binding.management-to-deployer",
    }
    for provider in ("aws", "azure"):
        expected_edges.update(
            f"edge.runtime.{provider}.{token}" for token, _, _ in BASELINE_EDGES
        )
    expected_edges.update(
        f"edge.runtime.gcp.{token}" for token, _, _ in BASELINE_EDGES[:4]
    )
    expected_edges.update(
        f"edge.runtime.mixed.{token}" for token, _, _ in BASELINE_EDGES
    )
    expected_edges.update(
        f"edge.runtime.{provider}.l3-hot-to-l5-reader" for provider in ("aws", "azure")
    )
    function_links = (
        ("dispatcher", "processor-wrapper"),
        ("processor-wrapper", "persister"),
        ("hot-to-cold-mover", "cold-writer"),
        ("cold-to-archive-mover", "archive-writer"),
    )
    expected_edges.update(
        f"edge.runtime.{provider}.function-{source}-to-{destination}"
        for provider in PROVIDERS
        for source, destination in function_links
    )
    expected_edges.update(
        f"edge.binding.{item['provider']}.package-"
        f"{item['owning_implementation_ids'][0].rsplit('.', 1)[-1]}"
        for item in inventory["artifacts"]
        if item["artifact_kind"] == "static-package"
    )
    actual_edges = {item["edge_id"] for item in inventory["edges"]}
    expected_assumptions = {
        "assumption.optimizer-slot-order",
        "assumption.cheapest-columns",
        "assumption.deployer-provider-keys",
        "assumption.function-output-suffix",
        "assumption.provider-handler-convention",
        "assumption.user-function-paths",
        "assumption.flutter-fixed-slots",
    }
    actual_assumptions = {
        item["assumption_id"] for item in inventory["fixed_assumptions"]
    }
    expected_slot_map = {
        responsibility_id: [slot] if slot in OPTIMIZER_SLOT_ORDER else []
        for slot, responsibility_id in RESPONSIBILITY_BY_SLOT.items()
    }
    actual_slot_map = {
        item["responsibility_id"]: item["optimizer_slot_ids"]
        for item in inventory["responsibilities"]
        if item["responsibility_id"] in expected_slot_map
    }
    missing = sorted(
        (expected_implementations - actual_implementations)
        | {
            f"terraform:{kind}:{address}:{path}"
            for kind, address, path in expected_terraform - actual_terraform
        }
        | (expected_artifacts - actual_artifacts)
        | (expected_edges - actual_edges)
        | (expected_assumptions - actual_assumptions)
        | {
            f"optimizer-slots:{responsibility_id}"
            for responsibility_id, slots in expected_slot_map.items()
            if actual_slot_map.get(responsibility_id) != slots
        }
    )
    stale = sorted(
        (actual_implementations - expected_implementations)
        | {
            f"terraform:{kind}:{address}:{path}"
            for kind, address, path in actual_terraform - expected_terraform
        }
        | (actual_artifacts - expected_artifacts)
        | (actual_edges - expected_edges)
        | (actual_assumptions - expected_assumptions)
    )
    if missing:
        raise InventoryCheckError("SOURCE_ENTITY_UNMAPPED", missing)
    if stale:
        raise InventoryCheckError("MATRIX_ENTITY_STALE", stale)


def _expected_diagram_ids(contract: dict[str, Any]) -> set[str]:
    ids = set(RESPONSIBILITY_BY_SLOT.values())
    ids.update(
        {
            "implementation.platform.optimizer",
            "implementation.platform.management-api",
            "implementation.platform.deployer",
            "implementation.platform.flutter",
            "trust.provider-account",
            "trust.cross-provider",
            "trust.user-code",
            "trust.flutter-to-management",
            "trust.management-to-optimizer",
            "trust.management-to-deployer",
        }
    )
    for provider in ("aws", "azure"):
        for _, source_slot, destination_slot in BASELINE_EDGES:
            ids.add(_representative_component(contract, source_slot, provider)[1])
            ids.add(_representative_component(contract, destination_slot, provider)[1])
    for _, source_slot, destination_slot in BASELINE_EDGES[:4]:
        ids.add(_representative_component(contract, source_slot, "gcp")[1])
        ids.add(_representative_component(contract, destination_slot, "gcp")[1])
    ids.update(
        f"edge.runtime.{provider}.{token}"
        for provider in ("aws", "azure")
        for token, _, _ in BASELINE_EDGES
    )
    ids.update(f"edge.runtime.gcp.{token}" for token, _, _ in BASELINE_EDGES[:4])
    ids.update(f"edge.runtime.mixed.{token}" for token, _, _ in BASELINE_EDGES)
    ids.update(
        f"edge.runtime.{provider}.l3-hot-to-l5-reader" for provider in ("aws", "azure")
    )
    return ids


def extract_diagram_manifest(text: str) -> set[str]:
    """Extract the checked stable-ID manifest embedded beside diagrams."""

    start = text.find(DIAGRAM_MANIFEST_START)
    if start < 0:
        return set()
    start += len(DIAGRAM_MANIFEST_START)
    end = text.find(DIAGRAM_MANIFEST_END, start)
    if end < 0:
        return set()
    return {
        token
        for token in re.findall(
            r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+",
            text[start:end],
        )
    }


def _check_diagram_manifests(root: Path) -> None:
    contract = extract_deployment_contract(root)
    expected = _expected_diagram_ids(contract)
    findings = []
    for relative in (
        "docs/research/phase_08_current_function_edge_matrix.md",
        "docs-site/docs/architecture/current-deployment-graph.md",
    ):
        actual = extract_diagram_manifest((root / relative).read_text(encoding="utf-8"))
        findings.extend(f"{relative}:missing:{value}" for value in expected - actual)
        findings.extend(f"{relative}:stale:{value}" for value in actual - expected)
    if findings:
        raise InventoryCheckError("EVIDENCE_INCOMPLETE", findings)


def _check_evidence(root: Path, inventory: dict[str, Any]) -> None:
    findings: list[str] = []
    for collection in (
        "responsibilities",
        "components",
        "artifacts",
        "terraform_objects",
        "edges",
        "cost_owners",
        "trust_boundaries",
        "fixed_assumptions",
        "unresolved_findings",
    ):
        for item in inventory[collection]:
            primary = next(
                value
                for key, value in item.items()
                if key.endswith("_id") and isinstance(value, str)
            )
            for reference in item["source_references"]:
                relative = reference.split("#", 1)[0]
                if not (root / relative).exists():
                    findings.append(f"{primary}->{relative}")
    findings.extend(_secret_material_findings(inventory))
    research_text = (
        root / "docs/research/phase_08_current_function_edge_matrix.md"
    ).read_text(encoding="utf-8")
    findings.extend(
        f"undocumented:{item['finding_id']}"
        for item in inventory["unresolved_findings"]
        if item["finding_id"] not in research_text
    )
    if findings:
        raise InventoryCheckError("EVIDENCE_INCOMPLETE", findings)


def _secret_material_findings(inventory: dict[str, Any]) -> list[str]:
    """Return bounded labels for forbidden secret/runtime material."""

    serialized = json.dumps(inventory, sort_keys=True).lower()
    forbidden = (
        "config_credentials.json",
        "terraform.tfstate",
        "aws_access_key_id=",
        "aws_secret_access_key=",
        "-----begin private key-----",
    )
    return [f"forbidden:{value}" for value in forbidden if value in serialized]


def check_inventory(root: Path | None = None) -> dict[str, int]:
    """Validate schema, canonical form, source drift, references, and coverage."""

    root = root or repository_root()
    path = root / "contracts/architecture-inventory/v1/current-graph.json"
    try:
        raw = path.read_text(encoding="utf-8")
        inventory = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryCheckError(
            "SCHEMA_INVALID", [str(path.relative_to(root))]
        ) from exc
    _schema_validate(root, inventory)
    if raw != pretty_json(inventory):
        raise InventoryCheckError(
            "DIGEST_MISMATCH", ["non-canonical JSON serialization"]
        )
    expected_content = content_digest(inventory)
    if inventory["content_digest"] != expected_content:
        raise InventoryCheckError("DIGEST_MISMATCH", ["content_digest"])
    expected_source = source_tree_digest(root, inventory["audited_source_paths"])
    if inventory["audited_source_tree_digest"] != expected_source:
        raise InventoryCheckError("DIGEST_MISMATCH", ["audited_source_tree_digest"])
    extract_optimizer_shape(root)
    verify_allowlisted_anchors(root)
    _check_ids_and_references(inventory)
    _check_source_reconciliation(root, inventory)
    _check_evidence(root, inventory)
    _check_diagram_manifests(root)
    counts = {
        "responsibilities": len(inventory["responsibilities"]),
        "components": len(inventory["components"]),
        "artifacts": len(inventory["artifacts"]),
        "terraform_objects": len(inventory["terraform_objects"]),
        "edges": len(inventory["edges"]),
        "cost_owners": len(inventory["cost_owners"]),
        "trust_boundaries": len(inventory["trust_boundaries"]),
        "fixed_assumptions": len(inventory["fixed_assumptions"]),
        "unresolved_findings": len(inventory["unresolved_findings"]),
        "allowlisted_anchors": sum(
            len(item["anchors"]) for item in ALLOWLISTED_ANCHORS
        ),
    }
    try:
        counts.update(
            check_baseline_decision(
                root,
                inventory,
                lambda schema_path, instance: _schema_validate_document(
                    root,
                    schema_path,
                    instance,
                    category="SCHEMA_INVALID",
                ),
            )
        )
    except BaselineDecisionError as exc:
        raise InventoryCheckError(exc.category, exc.findings) from exc
    return counts
