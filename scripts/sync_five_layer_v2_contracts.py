#!/usr/bin/env python3
"""Generate and verify the additive Five-layer v2 architecture and RDS contracts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import uuid
from decimal import Decimal, ROUND_CEILING
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
ARCH_ROOT = ROOT / "contracts" / "architecture-profiles"
ARCH_V1 = ARCH_ROOT / "v1"
ARCH_V2 = ARCH_ROOT / "v2"
DEFINITIONS = ARCH_ROOT / "definitions"
RDS_ROOT = ROOT / "contracts" / "resolved-deployment-specification"
RDS_V2 = RDS_ROOT / "v2"
DEPLOYMENT_MANIFEST_ROOT = ROOT / "contracts" / "deployment-manifest"
DEPLOYMENT_MANIFEST_V3 = DEPLOYMENT_MANIFEST_ROOT / "v3"
DEPLOYMENT_MANIFEST_V4 = DEPLOYMENT_MANIFEST_ROOT / "v4"
SERVICE_ROOT = ROOT / "docs" / "research" / "evidence" / "phase_08_service_bundles"
SERVICE_DECISION = SERVICE_ROOT / "decision.json"
SERVICE_COMPONENTS = SERVICE_ROOT / "implementation-component-manifest.json"
SERVICE_BUNDLES = SERVICE_ROOT / "complete-provider-bundles.json"
SERVICE_WORKLOAD = SERVICE_ROOT / "workload-scenarios.json"
SERVICE_PRICING = SERVICE_ROOT / "pricing-ownership-matrix.json"
SERVICE_SOURCES = SERVICE_ROOT / "source-ledger.json"
AWS_V2_RUNTIME_SOURCE = (
    "3-cloud-deployer/src/providers/aws/lambda_functions/five-layer-v2"
)
AZURE_V2_RUNTIME_SOURCE = (
    "3-cloud-deployer/src/providers/azure/azure_functions/five-layer-v2"
)
GCP_V2_RUNTIME_SOURCE = "3-cloud-deployer/src/providers/gcp/containers/five-layer-v2"
BRIDGE_RUNTIME_SOURCE = "3-cloud-deployer/src/runtime/eventing"
WORKLOAD_ROOT = ROOT / "contracts" / "five-layer-workload"
WORKLOAD_CATALOG = WORKLOAD_ROOT / "v2" / "eventing-scenario-catalog.json"
ARCH_TARGETS = (
    ROOT
    / "2-twin2clouds"
    / "backend"
    / "contracts"
    / "generated"
    / "architecture-profiles",
    ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "architecture-profiles",
    ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "architecture-profiles",
)
RDS_TARGETS = (
    ROOT
    / "2-twin2clouds"
    / "backend"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification",
    ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification",
    ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification",
)
DEPLOYMENT_MANIFEST_TARGETS = (
    ROOT
    / "twin2multicloud_backend"
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest",
    ROOT
    / "3-cloud-deployer"
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest",
)
FLUTTER_DEMO_ROOT = ROOT / "twin2multicloud_flutter" / "assets" / "demo" / "v1"
FLUTTER_DEMO_CONTRACTS = {
    "architecture-profile-five-layer-v2.json": (
        ARCH_V2 / "fixtures" / "valid" / "five-layer-baseline-v2-profile.json"
    ),
    "provider-profile-five-layer-v2-aws.json": (
        ARCH_V2 / "fixtures" / "valid" / "aws-five-layer-v2-provider-profile.json"
    ),
    "provider-profile-five-layer-v2-azure.json": (
        ARCH_V2 / "fixtures" / "valid" / "azure-five-layer-v2-provider-profile.json"
    ),
    "provider-profile-five-layer-v2-gcp.json": (
        ARCH_V2 / "fixtures" / "valid" / "gcp-five-layer-v2-provider-profile.json"
    ),
    "resolved-deployment-specification-v2-small.json": (
        RDS_V2 / "fixtures" / "valid" / "single-cloud-aws-small.json"
    ),
    "resolved-deployment-specification-v2-medium.json": (
        RDS_V2 / "fixtures" / "valid" / "two-cloud-azure-l3l5-gcp-l4-medium.json"
    ),
    "resolved-deployment-specification-v2-large.json": (
        RDS_V2 / "fixtures" / "valid" / "three-cloud-mixed-large.json"
    ),
    "resolved-twin-architecture-v2-small.json": (
        ARCH_V2 / "fixtures" / "valid" / "single-cloud-aws-small-resolved.json"
    ),
    "resolved-twin-architecture-v2-medium.json": (
        ARCH_V2
        / "fixtures"
        / "valid"
        / "two-cloud-azure-l3l5-gcp-l4-medium-resolved.json"
    ),
    "resolved-twin-architecture-v2-large.json": (
        ARCH_V2 / "fixtures" / "valid" / "three-cloud-mixed-large-resolved.json"
    ),
}
PROVIDERS = ("aws", "azure", "gcp")
REGIONS = {"aws": "eu-central-1", "azure": "westeurope", "gcp": "europe-west1"}
LOGICAL_COMPONENTS = (
    "component.ingestion",
    "component.processing",
    "component.hot-storage",
    "component.cool-storage",
    "component.archive-storage",
    "component.twin-state",
    "component.visualization",
)
LOGICAL_TO_LAYER = {
    "component.ingestion": "l1_acquisition",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot",
    "component.cool-storage": "l3_cool",
    "component.archive-storage": "l3_archive",
    "component.twin-state": "l4_twin",
    "component.visualization": "l5_visualization",
}
LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}
SCHEMA_NAMES = (
    "architecture-profile.schema.json",
    "provider-implementation-profile.schema.json",
    "deployment-component-catalog.schema.json",
    "resolved-twin-architecture.schema.json",
    "semantic-registry.schema.json",
)
VERSION_REPLACEMENTS = {
    "architecture-profile.v1": "architecture-profile.v2",
    "provider-implementation-profile.v1": "provider-implementation-profile.v2",
    "deployment-component-catalog.v1": "deployment-component-catalog.v2",
    "resolved-twin-architecture.v1": "resolved-twin-architecture.v2",
    "semantic-registry.v1": "semantic-registry.v2",
    "resolved-deployment-specification.v1": "resolved-deployment-specification.v2",
}
VALID_PLACEMENTS = tuple((base, twin) for base in PROVIDERS for twin in PROVIDERS)
EVENT_LOGICAL_COMPONENTS = (
    "component.ingestion",
    "component.processing",
    "component.hot-storage",
    "component.twin-state",
)
DOMAIN_EVENT_CONTRACT_ID = "canonical-domain-event.v1"
TWIN_PROJECTION_CONTRACT_ID = "twin_projection.v1"
STORAGE_TRANSITION_CONTRACT_ID = "storage_transition.v1"
RAW_HISTORY_CONTRACT_ID = "raw_history_query.v1"


class ContractError(ValueError):
    """Stable Five-layer v2 contract failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message[:400])
        self.code = code


def fail(code: str, message: str) -> NoReturn:
    raise ContractError(code, message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read JSON source {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain an object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode()).hexdigest()}"


def file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def tree_digest(root: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.name == ".contract-sha256"
            or "__pycache__" in path.parts
        ):
            continue
        result.update(path.relative_to(root).as_posix().encode("utf-8"))
        result.update(b"\0")
        result.update(path.read_bytes())
        result.update(b"\0")
    return f"sha256:{result.hexdigest()}"


def deployment_manifest_tree_digest(root: Path) -> str:
    """Mirror the dedicated DeploymentManifest synchronizer's marker policy."""

    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name != ".contract-sha256"
        and "__pycache__" not in path.parts
    ]
    return f"sha256:{hashlib.sha256(canonical_json(entries).encode()).hexdigest()}"


def package_source_digest(repository_source_path: str) -> str:
    """Mirror the Deployer's canonical platform-package digest policy."""

    source_path = ROOT / repository_source_path
    paths = [source_path] if source_path.is_file() else sorted(source_path.rglob("*"))
    result = hashlib.sha256()
    included = 0
    for path in paths:
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or ".git" in path.parts
            or path.suffix.lower() == ".zip"
            or path.name.startswith(".git")
            or path.name == ".DS_Store"
        ):
            continue
        relative = (
            repository_source_path
            if source_path.is_file()
            else f"{repository_source_path}/{path.relative_to(source_path).as_posix()}"
        )
        result.update(relative.encode("utf-8"))
        result.update(b"\0")
        result.update(path.read_bytes())
        result.update(b"\0")
        included += 1
    if included == 0:
        raise RuntimeError(f"Package source is empty: {repository_source_path}")
    return f"sha256:{result.hexdigest()}"


def replace_versions(value: object) -> object:
    if isinstance(value, dict):
        return {key: replace_versions(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [replace_versions(nested) for nested in value]
    if isinstance(value, str):
        result = value.replace("/v1/", "/v2/")
        for old, new in VERSION_REPLACEMENTS.items():
            result = result.replace(old, new)
        return result
    return value


def load_v1_runtime() -> ModuleType:
    path = ARCH_V1 / "runtime.py"
    spec = importlib.util.spec_from_file_location("five_layer_v2_v1_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load architecture runtime {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V1_RUNTIME = load_v1_runtime()


def architecture_digest(document: dict[str, Any]) -> str:
    return V1_RUNTIME.calculate_digest(document)


def redigest_architecture(document: dict[str, Any]) -> dict[str, Any]:
    document["content_digest"] = architecture_digest(document)
    return document


def generate_v2_schemas() -> None:
    ARCH_V2.mkdir(parents=True, exist_ok=True)
    for name in SCHEMA_NAMES:
        source = read_json(ARCH_V1 / name)
        transformed = replace_versions(source)
        if not isinstance(transformed, dict):
            raise RuntimeError(f"Transformed schema is not an object: {name}")
        transformed["title"] = str(transformed.get("title", name)).replace("v1", "v2")
        if name == "resolved-twin-architecture.schema.json":
            transformed["required"].insert(1, "resolution_status")
            transformed["properties"]["resolution_status"] = {
                "enum": ["offline_contract_fixture", "publishable"]
            }
            pricing_currency = transformed["$defs"]["pricing_evidence_ref"][
                "properties"
            ]["currency"]
            pricing_currency.pop("const", None)
            pricing_currency["enum"] = ["USD", "EUR"]
        write_json(ARCH_V2 / name, transformed)

    runtime_source = (ARCH_V1 / "runtime.py").read_text(encoding="utf-8")
    for old, new in VERSION_REPLACEMENTS.items():
        runtime_source = runtime_source.replace(old, new)
    runtime_source = runtime_source.replace(
        "Shared, network-free runtime for architecture-profile contract v1.",
        "Shared, network-free runtime for architecture-profile contract v2.",
    )
    placement_needle = """    by_component = {
        assignment["logical_component_id"]: assignment
        for assignment in document["component_assignments"]
    }
"""
    placement_guard = (
        placement_needle
        + """    hot_assignment = by_component.get("component.hot-storage")
    visualization_assignment = by_component.get("component.visualization")
    if (
        hot_assignment is not None
        and visualization_assignment is not None
        and hot_assignment["provider"] != visualization_assignment["provider"]
    ):
        _fail(
            "ARCH_BUNDLE_INCOMPATIBLE",
            "component_assignments",
            "Five-layer v2 requires provider-local L3 hot and L5",
        )
"""
    )
    if placement_needle not in runtime_source:
        raise RuntimeError("Cannot install Five-layer v2 placement guard")
    runtime_source = runtime_source.replace(placement_needle, placement_guard, 1)
    runtime_source = runtime_source.replace(
        '    if profile["lifecycle_status"] != "active":\n',
        "    if (\n"
        '        document["resolution_status"] == "publishable"\n'
        '        and profile["lifecycle_status"] != "active"\n'
        "    ):\n",
        1,
    )
    runtime_source = runtime_source.replace(
        '    if catalog is not None and catalog["lifecycle_status"] != "active":\n',
        "    if (\n"
        '        document["resolution_status"] == "publishable"\n'
        "        and catalog is not None\n"
        '        and catalog["lifecycle_status"] != "active"\n'
        "    ):\n",
        1,
    )
    provider_status_needle = """        if (
            provider_profile["lifecycle_status"] != "active"
            or not provider_profile["supported"]
        ):
"""
    provider_status_guard = """        if (
            not provider_profile["supported"]
            or (
                document["resolution_status"] == "publishable"
                and provider_profile["lifecycle_status"] != "active"
            )
        ):
"""
    if provider_status_needle not in runtime_source:
        raise RuntimeError("Cannot install Five-layer v2 resolution status guard")
    runtime_source = runtime_source.replace(
        provider_status_needle,
        provider_status_guard,
        1,
    )
    runtime_source = runtime_source.replace(
        '        "resolution_id",\n        "architecture_profile_ref",\n',
        '        "resolution_id",\n        "resolution_status",\n'
        '        "architecture_profile_ref",\n',
        1,
    )
    (ARCH_V2 / "runtime.py").write_text(runtime_source, encoding="utf-8")


def load_v2_runtime() -> ModuleType:
    path = ARCH_V2 / "runtime.py"
    spec = importlib.util.spec_from_file_location("five_layer_v2_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load architecture runtime {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def workload_contract_digest() -> str:
    path = ROOT / "scripts" / "sync_five_layer_workload_contract.py"
    spec = importlib.util.spec_from_file_location(
        "five_layer_v2_workload_contract",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load workload contract generator {path}")
    workload = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(workload)
    return workload.contract_digest(workload.expected_documents())


def service_decision_digest() -> str:
    decision = read_json(SERVICE_DECISION)
    return str(decision["package_digest"])


def optimization_bundle() -> dict[str, Any]:
    bundle = {
        "optimization_strategy_id": "cost-minimization-v2",
        "optimization_strategy_version": "2",
        "calculation_strategy_id": "profile-resolution-v2",
        "calculation_strategy_version": "2",
        "formula_set_id": "phase-08-complete-service-bundles",
        "formula_set_version": "1",
        "scoring_strategy_id": "profile-local-min-total-cost-v2",
        "scoring_strategy_version": "2",
        "pricing_registry_id": "phase-08-complete-service-pricing",
        "pricing_registry_versions": ["1"],
        "workload_contract_id": "five-layer-workload",
        "workload_contract_version": "2",
        "deployment_specification_versions": ["resolved-deployment-specification.v2"],
    }
    bundle["compatibility_digest"] = digest(bundle)
    return bundle


def build_profile() -> dict[str, Any]:
    profile = replace_versions(
        read_json(
            DEFINITIONS / "profiles" / "five-layer-baseline" / "1" / "profile.json"
        )
    )
    if not isinstance(profile, dict):
        raise RuntimeError("Five-layer profile template is invalid")
    profile.update(
        {
            "schema_version": "architecture-profile.v2",
            "profile_version": "2",
            "lifecycle_status": "active",
            "display_name": "Five-layer baseline v2",
            "description": (
                "Functionally complete thesis-PoC profile with mandatory embedded "
                "domain events, provider-local L3-hot/L5 raw history, and an "
                "independently placeable L4 Twin."
            ),
            "workload_contract_ref": {
                "id": "five-layer-workload",
                "version": "2",
                "digest": workload_contract_digest(),
            },
            "optimization_bundle": optimization_bundle(),
        }
    )
    profile["compatibility"] = {
        "supported_contract_versions": [
            "five-layer-workload.v2",
            "resolved-deployment-specification.v2",
        ],
        "provider_implementation_schema_versions": [
            "provider-implementation-profile.v2"
        ],
        "catalog_schema_versions": ["deployment-component-catalog.v2"],
        "resolved_architecture_schema_versions": ["resolved-twin-architecture.v2"],
    }
    profile["graph_policy"] = {
        "cycle_policy": "allowlisted",
        "allowed_cycle_ids": ["cycle.ingestion.processing"],
        "optional_components": [],
        "user_topology_editable": False,
    }
    components = {item["component_id"]: item for item in profile["components"]}
    components["component.ingestion"]["required_capability_ids"].append(
        "capability.embedded-domain-event-ingress"
    )
    components["component.ingestion"]["input_port_ids"] = [
        "port.ingestion.device-command-in"
    ]
    components["component.ingestion"]["output_port_ids"] = [
        "port.ingestion.telemetry-event-out",
        "port.ingestion.command-outcome-event-out",
    ]
    components["component.processing"]["required_capability_ids"].extend(
        [
            "capability.embedded-domain-event-routing",
            "capability.mandatory-rule-action-feedback",
        ]
    )
    components["component.processing"]["input_port_ids"] = [
        "port.processing.telemetry-event-in"
    ]
    components["component.processing"]["output_port_ids"] = [
        "port.processing.persistence-event-out",
        "port.processing.device-command-out",
    ]
    components["component.hot-storage"]["input_port_ids"] = [
        "port.hot-storage.processing-event-in",
        "port.hot-storage.command-outcome-event-in",
    ]
    components["component.hot-storage"]["output_port_ids"] = [
        "port.hot-storage.transition-out",
        "port.hot-storage.twin-projection-out",
    ]
    components["component.hot-storage"]["output_port_ids"].append(
        "port.hot-storage.raw-history-out"
    )
    components["component.twin-state"]["input_port_ids"] = [
        "port.twin-state.projection-in"
    ]
    components["component.twin-state"]["output_port_ids"] = []
    components["component.visualization"]["input_port_ids"] = [
        "port.visualization.raw-history-in"
    ]
    for edge in profile["edges"]:
        edge_id = edge["edge_id"]
        if edge_id == "edge.ingestion-to-processing":
            edge.update(
                {
                    "source_port_id": "port.ingestion.telemetry-event-out",
                    "destination_port_id": "port.processing.telemetry-event-in",
                    "edge_contract_id": DOMAIN_EVENT_CONTRACT_ID,
                }
            )
        elif edge_id == "edge.processing-to-hot-storage":
            edge.update(
                {
                    "source_port_id": "port.processing.persistence-event-out",
                    "destination_port_id": "port.hot-storage.processing-event-in",
                    "edge_contract_id": DOMAIN_EVENT_CONTRACT_ID,
                }
            )
        elif edge_id == "edge.hot-storage-to-twin-state":
            edge.update(
                {
                    "source_port_id": "port.hot-storage.twin-projection-out",
                    "destination_port_id": "port.twin-state.projection-in",
                    "edge_contract_id": TWIN_PROJECTION_CONTRACT_ID,
                }
            )
        elif edge_id in {
            "edge.hot-to-cool-storage",
            "edge.cool-to-archive-storage",
        }:
            edge["edge_contract_id"] = STORAGE_TRANSITION_CONTRACT_ID
        elif edge_id == "edge.twin-state-to-visualization":
            edge.update(
                {
                    "edge_id": "edge.hot-storage-to-visualization",
                    "source_component_id": "component.hot-storage",
                    "source_port_id": "port.hot-storage.raw-history-out",
                    "destination_port_id": "port.visualization.raw-history-in",
                    "edge_contract_id": RAW_HISTORY_CONTRACT_ID,
                    "cost_owner_ids": ["cost.hot-storage-to-visualization"],
                }
            )
    ingress_edge = next(
        edge
        for edge in profile["edges"]
        if edge["edge_id"] == "edge.ingestion-to-processing"
    )
    command_edge = copy.deepcopy(ingress_edge)
    command_edge.update(
        {
            "edge_id": "edge.processing-to-ingestion",
            "source_component_id": "component.processing",
            "source_port_id": "port.processing.device-command-out",
            "destination_component_id": "component.ingestion",
            "destination_port_id": "port.ingestion.device-command-in",
            "edge_contract_id": DOMAIN_EVENT_CONTRACT_ID,
        }
    )
    profile["edges"].append(command_edge)
    outcome_edge = copy.deepcopy(ingress_edge)
    outcome_edge.update(
        {
            "edge_id": "edge.ingestion-to-hot-storage",
            "source_component_id": "component.ingestion",
            "source_port_id": "port.ingestion.command-outcome-event-out",
            "destination_component_id": "component.hot-storage",
            "destination_port_id": "port.hot-storage.command-outcome-event-in",
            "edge_contract_id": DOMAIN_EVENT_CONTRACT_ID,
        }
    )
    profile["edges"].append(outcome_edge)
    profile["functional_completeness_rules"].extend(
        [
            {
                "capability_id": "capability.embedded-domain-event-flow",
                "evidence": "phase-08-eventing-decision@1 mandatory shared behavior",
                "required": True,
            },
            {
                "capability_id": "capability.provider-local-raw-visualization",
                "evidence": "L3 hot and L5 assignments share one provider",
                "required": True,
            },
            {
                "capability_id": "capability.independent-twin-placement",
                "evidence": "L3-hot-to-L4 typed Twin projection edge",
                "required": True,
            },
        ]
    )
    return redigest_architecture(profile)


def build_semantic_registry(profile: dict[str, Any]) -> dict[str, Any]:
    registry = replace_versions(read_json(ARCH_V1 / "semantic-registry.json"))
    if not isinstance(registry, dict):
        raise RuntimeError("Architecture semantic registry template is invalid")
    registry["registry_version"] = "2"
    registry["compatible_optimization_bundles"] = [
        copy.deepcopy(profile["optimization_bundle"])
    ]
    registry["deployment_specification_compatibility"] = [
        {
            "schema_version": "resolved-deployment-specification.v2",
            "architecture_profile_ids": ["five-layer-baseline"],
            "architecture_profile_versions": ["2"],
        }
    ]
    registry["cycle_contracts"].append(
        {
            "cycle_id": "cycle.ingestion.processing",
            "workflow_semantics": (
                "Bounded mandatory device-command request and outcome feedback "
                "between L2 processing and L1 ingestion."
            ),
            "compatibility_version": "1",
        }
    )
    registry["field_ownership"].append(
        {
            "contract_kind": "resolved-twin-architecture.v2",
            "field_path": "/resolution_status",
            "author": "optimizer_derived",
            "mutability": "immutable_derived",
        }
    )
    port_contracts = {item["port_id"]: item for item in registry["port_contracts"]}
    for obsolete in (
        "port.ingestion.telemetry-out",
        "port.processing.telemetry-in",
        "port.processing.telemetry-out",
        "port.hot-storage.write-in",
        "port.hot-storage.twin-update-out",
        "port.twin-state.update-in",
        "port.twin-state.query-out",
        "port.visualization.query-in",
    ):
        port_contracts.pop(obsolete, None)
    for port_id in (
        "port.hot-storage.transition-out",
        "port.cool-storage.write-in",
        "port.cool-storage.transition-out",
        "port.archive-storage.write-in",
    ):
        port_contracts[port_id]["schema_ref"] = STORAGE_TRANSITION_CONTRACT_ID
    for port_id, semantics in {
        "port.ingestion.device-command-in": (
            "Canonical device-command request consumed by L1."
        ),
        "port.ingestion.telemetry-event-out": (
            "Canonical telemetry-received events emitted by L1 for L2."
        ),
        "port.ingestion.command-outcome-event-out": (
            "Canonical device-command-outcome events emitted by L1 for L3 hot."
        ),
        "port.processing.telemetry-event-in": (
            "Canonical telemetry-received events consumed by L2."
        ),
        "port.processing.persistence-event-out": (
            "Canonical processed and terminal-outcome events emitted by L2 for L3 hot."
        ),
        "port.processing.device-command-out": (
            "Canonical device-command request emitted by L2 for L1."
        ),
        "port.hot-storage.processing-event-in": (
            "Canonical processed and processing-owned outcome events persisted by L3 hot."
        ),
        "port.hot-storage.command-outcome-event-in": (
            "Canonical device-command-outcome events persisted directly by L3 hot."
        ),
    }.items():
        port_contracts[port_id] = {
            "port_id": port_id,
            "schema_ref": DOMAIN_EVENT_CONTRACT_ID,
            "envelope_ref": "contract-envelope",
            "semantics": semantics,
            "compatibility_version": "1",
        }
    for port_id, semantics in {
        "port.hot-storage.twin-projection-out": (
            "Typed canonical Twin projection emitted after durable L3 acceptance."
        ),
        "port.twin-state.projection-in": (
            "Typed canonical Twin projection consumed by L4."
        ),
    }.items():
        port_contracts[port_id] = {
            "port_id": port_id,
            "schema_ref": TWIN_PROJECTION_CONTRACT_ID,
            "envelope_ref": "contract-envelope",
            "semantics": semantics,
            "compatibility_version": "1",
        }
    port_contracts["port.hot-storage.raw-history-out"] = {
        "port_id": "port.hot-storage.raw-history-out",
        "schema_ref": RAW_HISTORY_CONTRACT_ID,
        "envelope_ref": "contract-envelope",
        "semantics": "Typed bounded raw or hourly-rollup history response.",
        "compatibility_version": "1",
    }
    port_contracts["port.visualization.raw-history-in"] = {
        "port_id": "port.visualization.raw-history-in",
        "schema_ref": RAW_HISTORY_CONTRACT_ID,
        "envelope_ref": "contract-envelope",
        "semantics": "Typed bounded raw-history query consumed by L5.",
        "compatibility_version": "1",
    }
    registry["port_contracts"] = list(port_contracts.values())
    registry["content_digest"] = ""
    return redigest_architecture(registry)


@lru_cache(maxsize=1)
def service_component_index() -> dict[tuple[str, str], dict[str, Any]]:
    source = read_json(SERVICE_COMPONENTS)
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in source["components"]:
        key = (str(item["provider"]), str(item["component_id"]))
        if key in result:
            raise RuntimeError(f"Duplicate service component tuple {key}")
        result[key] = item
    return result


def service_groups() -> dict[str, dict[str, list[str]]]:
    bundles = read_json(SERVICE_BUNDLES)
    groups: dict[str, dict[str, list[str]]] = {}
    for provider_bundle in bundles["providers"]:
        provider = str(provider_bundle["provider"])
        layers = provider_bundle["layers"]
        provider_groups = {
            logical: list(layers[layer]) for logical, layer in LOGICAL_TO_LAYER.items()
        }
        for logical in EVENT_LOGICAL_COMPONENTS:
            provider_groups[logical].extend(
                provider_bundle["embedded_event_components"]
            )
        for component_id in provider_bundle["support_components"]:
            if "artifact-registry" in component_id:
                owners = [
                    "component.ingestion",
                    "component.processing",
                    "component.hot-storage",
                    "component.cool-storage",
                    "component.twin-state",
                    "component.visualization",
                ]
            elif any(
                marker in component_id
                for marker in (
                    "scheduler",
                    "storage-mover",
                    "scheduled-storage-job",
                    "storage-job",
                    ".ecr-",
                    ".acr-",
                )
            ):
                owners = ["component.hot-storage", "component.cool-storage"]
            elif any(
                marker in component_id
                for marker in (
                    "cloudwatch",
                    ".monitor",
                    "cloud-monitoring",
                    "cloud-logging",
                    "log-analytics",
                )
            ):
                owners = list(LOGICAL_COMPONENTS)
            elif any(
                marker in component_id
                for marker in (
                    "identity-center-layer-access",
                    "entra-layer-access",
                    "direct-iap-layer-access",
                )
            ):
                owners = ["component.twin-state", "component.visualization"]
            elif "grafana-tls-load-balancer" in component_id:
                owners = ["component.visualization"]
            else:
                raise RuntimeError(
                    f"Unclassified Five-layer support component: {component_id}"
                )
            for owner in owners:
                provider_groups[owner].append(component_id)
        groups[provider] = {
            logical: list(dict.fromkeys(values))
            for logical, values in provider_groups.items()
        }
    if tuple(groups) != PROVIDERS:
        raise RuntimeError("Complete provider bundles use a non-canonical order")
    index = service_component_index()
    for provider, provider_groups in groups.items():
        flattened = {
            component_id
            for logical in LOGICAL_COMPONENTS
            for component_id in provider_groups[logical]
        }
        for component_id in flattened:
            component = index.get((provider, component_id))
            if component is None:
                raise RuntimeError(
                    f"Unknown selected component {provider}/{component_id}"
                )
            if "five-layer-baseline@2" not in component["profile_refs"]:
                raise RuntimeError(
                    f"Component is not approved for Five-layer v2: {component_id}"
                )
    return groups


def assignment_for_bundle(base_provider: str, twin_provider: str) -> dict[str, str]:
    return {
        logical: twin_provider if logical == "component.twin-state" else base_provider
        for logical in LOGICAL_COMPONENTS
    }


@lru_cache(maxsize=1)
def provider_bundle_index() -> dict[str, dict[str, Any]]:
    return {item["provider"]: item for item in read_json(SERVICE_BUNDLES)["providers"]}


def selected_groups_for_assignment(
    assignment: dict[str, str],
) -> list[tuple[str, str, str]]:
    if set(assignment) != set(LOGICAL_COMPONENTS) or any(
        provider not in PROVIDERS for provider in assignment.values()
    ):
        raise RuntimeError("Assignment must contain every logical component provider")
    if assignment["component.hot-storage"] != assignment["component.visualization"]:
        fail(
            "PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED",
            "L3 hot and L5 must share one provider",
        )

    bundle_index = provider_bundle_index()
    selected: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(provider: str, logical: str, component_ids: list[str]) -> None:
        for component_id in component_ids:
            key = (provider, component_id)
            if key in seen:
                continue
            seen.add(key)
            selected.append((provider, logical, component_id))

    for logical in LOGICAL_COMPONENTS:
        provider = assignment[logical]
        add(
            provider,
            logical,
            list(bundle_index[provider]["layers"][LOGICAL_TO_LAYER[logical]]),
        )

    event_providers = {assignment[logical] for logical in EVENT_LOGICAL_COMPONENTS}
    for provider in sorted(event_providers):
        owner = next(
            logical
            for logical in EVENT_LOGICAL_COMPONENTS
            if assignment[logical] == provider
        )
        embedded = list(bundle_index[provider]["embedded_event_components"])
        if len(event_providers) == 1:
            embedded = [
                component_id
                for component_id in embedded
                if "only-for-reviewed-remote" not in component_id
            ]
        add(provider, owner, embedded)

    provider_logicals = {
        provider: [
            logical for logical in LOGICAL_COMPONENTS if assignment[logical] == provider
        ]
        for provider in PROVIDERS
    }
    for provider, logicals in provider_logicals.items():
        if not logicals:
            continue
        supports = list(bundle_index[provider]["support_components"])
        observability = [
            item
            for item in supports
            if any(
                marker in item
                for marker in (
                    "cloudwatch",
                    ".monitor",
                    "cloud-monitoring",
                    "cloud-logging",
                    "log-analytics",
                )
            )
        ]
        add(provider, logicals[0], observability)

        if any(
            assignment[logical] == provider
            for logical in ("component.twin-state", "component.visualization")
        ):
            access = [
                item
                for item in supports
                if any(
                    marker in item
                    for marker in (
                        "identity-center-layer-access",
                        "entra-layer-access",
                        "direct-iap-layer-access",
                    )
                )
            ]
            owner = (
                "component.twin-state"
                if assignment["component.twin-state"] == provider
                else "component.visualization"
            )
            add(provider, owner, access)

        if assignment["component.visualization"] == provider:
            add(
                provider,
                "component.visualization",
                [item for item in supports if "grafana-tls-load-balancer" in item],
            )

    hot_provider = assignment["component.hot-storage"]
    cool_provider = assignment["component.cool-storage"]
    archive_provider = assignment["component.archive-storage"]
    mover_owners = [(hot_provider, "component.hot-storage")]
    if cool_provider != archive_provider:
        mover_owners.append((cool_provider, "component.cool-storage"))
    for provider, logical in mover_owners:
        supports = bundle_index[provider]["support_components"]
        add(
            provider,
            logical,
            [
                item
                for item in supports
                if any(
                    marker in item
                    for marker in (
                        "scheduler",
                        "storage-mover",
                        "scheduled-storage-job",
                        "storage-job",
                        "artifact-registry",
                        ".ecr-",
                        ".acr-",
                    )
                )
            ],
        )

    if any(
        assignment[logical] == "gcp"
        for logical in (
            "component.ingestion",
            "component.processing",
            "component.twin-state",
            "component.visualization",
        )
    ):
        owner = next(
            logical
            for logical in (
                "component.ingestion",
                "component.processing",
                "component.twin-state",
                "component.visualization",
            )
            if assignment[logical] == "gcp"
        )
        add(
            "gcp",
            owner,
            [
                item
                for item in bundle_index["gcp"]["support_components"]
                if "artifact-registry" in item
            ],
        )

    return selected


def deployment_component_id(provider: str, logical: str) -> str:
    return f"deployment.{provider}.{logical.removeprefix('component.')}.v2"


def provider_profile_id(provider: str) -> str:
    return f"provider-profile.{provider}.five-layer-baseline-v2"


def catalog_port(provider: str, port_id: str) -> dict[str, Any]:
    contract_id = (
        RAW_HISTORY_CONTRACT_ID
        if "raw-history" in port_id
        else (
            STORAGE_TRANSITION_CONTRACT_ID
            if (
                "transition-out" in port_id
                or any(
                    layer in port_id
                    for layer in ("cool-storage.write-in", "archive-storage.write-in")
                )
            )
            else (
                TWIN_PROJECTION_CONTRACT_ID
                if "projection" in port_id
                else DOMAIN_EVENT_CONTRACT_ID
            )
        )
    )
    return {
        "port_id": f"catalog.{provider}.{port_id}",
        "schema_ref": {"id": contract_id, "version": "1"},
        "envelope_ref": {"id": "contract-envelope", "version": "1"},
        "value_type": "json_document",
        "sensitivity": "internal",
        "cardinality": "many",
        "producer_consumer_phase": "runtime",
        "resolution_stage": "catalog",
        "compatibility_version": "1",
    }


def safe_tf_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]", "_", value.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized[:100] or "component"


def terraform_resource_address(
    provider: str,
    component_id: str,
    resource_type: str,
) -> str:
    """Return the reviewed address, including intentional PoC sharing."""

    if (
        provider == "azure"
        and component_id == "azure.blob-cool"
        and resource_type == "azurerm_storage_account"
    ):
        # Flex package hosting and bounded Blob history share the provider
        # foundation account; a second account adds no thesis value.
        return "azurerm_storage_account.main"
    if (
        provider == "gcp"
        and component_id == "gcp.firestore-native-standard-bounded-twin"
        and resource_type == "google_firestore_database"
    ):
        # L3 and L4 use separate collections, indexes, identities, and cost
        # ownership in one deployment database; a second database adds no PoC
        # capability and would contradict the reviewed service decision.
        return (
            "google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup"
        )
    if (
        provider == "gcp"
        and component_id == "gcp.direct-iap-layer-access"
        and resource_type == "google_iap_web_cloud_run_service_iam_member"
    ):
        # Direct IAP support and the Explorer share one exact human-principal
        # accessor binding. A duplicate IAM member would conflict at apply.
        return (
            "google_iap_web_cloud_run_service_iam_member."
            "gcp_gcp_cloud_run_iap_twin_explorer"
        )
    return f"{resource_type}.{safe_tf_name(provider + '_' + component_id)}"


def component_kind(logical: str) -> str:
    return {
        "component.ingestion": "managed_service",
        "component.processing": "serverless_function",
        "component.hot-storage": "storage_service",
        "component.cool-storage": "storage_service",
        "component.archive-storage": "storage_service",
        "component.twin-state": "twin_service",
        "component.visualization": "visualization_service",
    }[logical]


def build_catalog_component(
    provider: str,
    logical: str,
    service_ids: list[str],
    profile: dict[str, Any],
    service_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    logical_doc = next(
        item for item in profile["components"] if item["component_id"] == logical
    )
    selected = [service_index[(provider, item)] for item in service_ids]
    resource_addresses = sorted(
        {
            terraform_resource_address(
                provider,
                item["component_id"],
                resource_type,
            )
            for item in selected
            for resource_type in item["terraform_resource_types"]
        }
    )
    if not resource_addresses:
        resource_addresses = [
            f"terraform_data.{safe_tf_name(provider + '_' + logical)}"
        ]
    permission_refs = sorted(
        {permission for item in selected for permission in item["permission_set_refs"]}
    )
    return {
        "deployment_component_id": deployment_component_id(provider, logical),
        "component_version": "1",
        "provider": provider,
        "logical_component_ids": [logical],
        "decision_implementation_ids": service_ids,
        "service_id": f"{provider}.{logical.removeprefix('component.')}.v2",
        "service_ids": service_ids,
        "component_kind": component_kind(logical),
        "package_artifact_ref": {
            "id": f"artifact.platform.{provider}.five-layer-v2",
            "version": "1",
        },
        "terraform_binding": {
            "resource_addresses": resource_addresses,
            "module_addresses": [],
            "allowed_input_variable_ids": [],
            "input_bindings": [],
            "outputs": [
                {
                    "output_id": (
                        f"output.{provider}.{logical.removeprefix('component.')}.v2"
                    ),
                    "terraform_output": (
                        f"{safe_tf_name(provider + '_' + logical)}_output"
                    ),
                    "sensitive": False,
                }
            ],
            "dependency_keys": [],
        },
        "runtime_contract": {
            "provider_runtime_id": f"runtime.{provider}.five-layer-v2",
            "platform_handler_adapter_id": f"adapter.{provider}.five-layer-v2",
            "timeout_seconds_min": 1,
            "timeout_seconds_max": 900,
            "memory_mb_min": 128,
            "memory_mb_max": 32768,
            "trigger_adapter_id": f"trigger.{provider}.five-layer-v2",
            "package_layout_id": f"package-layout.{provider}.five-layer-v2",
            "user_override_allowed": False,
        },
        "configuration_schema_ref": {
            "id": f"configuration.{provider}.{logical.removeprefix('component.')}.v2",
            "version": "1",
        },
        "input_ports": [
            catalog_port(provider, port_id) for port_id in logical_doc["input_port_ids"]
        ],
        "output_ports": [
            catalog_port(provider, port_id)
            for port_id in logical_doc["output_port_ids"]
        ],
        "required_permission_capabilities": permission_refs
        or [f"{provider}_thesis_demo_v2"],
        "pricing_model_refs": [
            f"pricing.{provider}.{logical.removeprefix('component.')}.v2"
        ],
        "formula_refs": ["formula.phase-08-complete-service-bundles"],
        "deployment_specification_bindings": [
            {
                "specification_schema_version": (
                    "resolved-deployment-specification.v2"
                ),
                "component_id": component_id,
                "slot_id": LOGICAL_TO_SLOT[logical],
            }
            for component_id in service_ids
        ],
        "extension_slot_refs": (
            [{"id": "processor.telemetry", "version": "1"}]
            if logical == "component.processing"
            else []
        ),
        "error_contract_ref": {"id": "architecture-runtime-errors", "version": "1"},
        "observability_contract_ref": {
            "id": "observability.five-layer-v2",
            "version": "1",
        },
        "cleanup_contract_ref": {"id": "cleanup.five-layer-v2", "version": "1"},
        "compatibility": {
            "architecture_profile_versions": [
                {"id": "five-layer-baseline", "version": "2"}
            ],
            "provider_profile_versions": [
                {"id": provider_profile_id(provider), "version": "1"}
            ],
            "deployment_specification_versions": [
                "resolved-deployment-specification.v2"
            ],
        },
    }


def edge_implementation_id(source: str, target: str, edge_id: str) -> str:
    return (
        f"edge-implementation.{source}-to-{target}.{edge_id.removeprefix('edge.')}.v2"
    )


def build_edge_implementation(
    source: str,
    target: str,
    edge: dict[str, Any],
) -> dict[str, Any]:
    local = source == target
    mechanism = (
        "typed_synchronous_api"
        if edge["edge_id"] == "edge.hot-storage-to-visualization"
        else (
            "source_owned_transition_runtime"
            if "to-cool" in edge["edge_id"] or "to-archive" in edge["edge_id"]
            else "provider_native_trigger"
        )
    )
    if not local:
        mechanism = "cross_provider_adapter"
    source_deployment = deployment_component_id(source, edge["source_component_id"])
    target_deployment = deployment_component_id(
        target, edge["destination_component_id"]
    )
    return {
        "edge_implementation_id": edge_implementation_id(
            source, target, edge["edge_id"]
        ),
        "edge_implementation_version": "1",
        "provider": source,
        "decision_edge_ids": [
            f"decision.route.{source}-to-{target}.{edge['edge_id'].removeprefix('edge.')}"
        ],
        "logical_edge_ids": [edge["edge_id"]],
        "mechanism": mechanism,
        "source_component_ids": [source_deployment],
        "destination_component_ids": [target_deployment],
        "source_output_port_id": f"catalog.{source}.{edge['source_port_id']}",
        "destination_input_port_id": f"catalog.{target}.{edge['destination_port_id']}",
        "terraform_binding": {
            "source_output_id": (
                f"output.{source}.{edge['source_component_id'].removeprefix('component.')}.v2"
            ),
            # Graph translation binds an edge to the destination node's
            # declared catalog port. A synthetic input.* identifier is not a
            # node port and therefore cannot be resolved by Terraform.
            "destination_input_id": (f"catalog.{target}.{edge['destination_port_id']}"),
            "dependency_keys": [],
        },
        "transfer_route_class": (
            "same_provider_same_region" if local else "cross_provider"
        ),
        "payload_contract_ref": {
            "id": edge["edge_contract_id"],
            "version": edge["edge_contract_version"],
        },
        "delivery_requirements": edge["delivery_requirements"],
        "trust_contract_ref": {
            "id": "trust.workload-identity-federation",
            "version": "1",
        },
        "pricing_model_refs": [f"pricing.transfer.{source}-to-{target}.v2"],
        "formula_refs": ["formula.phase-08-complete-service-bundles"],
        "required_permission_capabilities": [f"{source}_thesis_demo_v2"],
        "glue_component_ids": [] if local else [source_deployment],
        "error_contract_ref": {"id": "architecture-runtime-errors", "version": "1"},
        "observability_contract_ref": {
            "id": "observability.five-layer-v2",
            "version": "1",
        },
        "compatibility": {
            "architecture_profile_versions": [
                {"id": "five-layer-baseline", "version": "2"}
            ],
            "provider_profile_versions": [
                {"id": provider_profile_id(source), "version": "1"},
                *(
                    [{"id": provider_profile_id(target), "version": "1"}]
                    if not local
                    else []
                ),
            ],
            "deployment_specification_versions": [
                "resolved-deployment-specification.v2"
            ],
        },
    }


def build_catalog(
    profile: dict[str, Any],
    groups: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    service_index = service_component_index()
    components = [
        build_catalog_component(
            provider,
            logical,
            groups[provider][logical],
            profile,
            service_index,
        )
        for provider in PROVIDERS
        for logical in LOGICAL_COMPONENTS
    ]
    edge_implementations = []
    for edge in profile["edges"]:
        for source in PROVIDERS:
            targets = (
                (source,)
                if edge["edge_id"] == "edge.hot-storage-to-visualization"
                else PROVIDERS
            )
            for target in targets:
                edge_implementations.append(
                    build_edge_implementation(source, target, edge)
                )
    catalog = {
        "schema_version": "deployment-component-catalog.v2",
        "catalog_id": "complete-service-component-catalog",
        "catalog_version": "1",
        "lifecycle_status": "active",
        "components": components,
        "edge_implementations": edge_implementations,
        "package_artifacts": [
            {
                "artifact_id": f"artifact.platform.{provider}.five-layer-v2",
                "artifact_version": "1",
                "decision_implementation_ids": sorted(
                    {
                        component_id
                        for logical in LOGICAL_COMPONENTS
                        for component_id in groups[provider][logical]
                    }
                ),
                "repository_source_path": (
                    AWS_V2_RUNTIME_SOURCE
                    if provider == "aws"
                    else AZURE_V2_RUNTIME_SOURCE
                    if provider == "azure"
                    else GCP_V2_RUNTIME_SOURCE
                ),
                "platform_handler": f"handler.{provider}.five-layer-v2",
                "digest_policy": "sha256.canonical-source.v1",
                "source_digest": (
                    package_source_digest(AWS_V2_RUNTIME_SOURCE)
                    if provider == "aws"
                    else package_source_digest(AZURE_V2_RUNTIME_SOURCE)
                    if provider == "azure"
                    else package_source_digest(GCP_V2_RUNTIME_SOURCE)
                ),
                "included_paths": (
                    [
                        "handler.py",
                        "storage-mover/Dockerfile",
                        "storage-mover/constraints.txt",
                        "storage-mover/requirements.txt",
                        "storage-mover/storage_mover.py",
                    ]
                    if provider == "aws"
                    else [
                        "core.py",
                        "function_app.py",
                        "host.json",
                        "requirements.txt",
                        "storage-mover/Dockerfile",
                        "storage-mover/constraints.txt",
                        "storage-mover/requirements.txt",
                        "storage-mover/storage_mover.py",
                    ]
                    if provider == "azure"
                    else [
                        "Dockerfile",
                        "grafana/Dockerfile",
                        "grafana/dashboard.json.template",
                        "grafana/entrypoint.sh",
                        "grafana/provisioning/dashboards/twin2multicloud.yaml",
                        "grafana/provisioning/datasources/twin2multicloud.yaml",
                        "platform/app.py",
                        "platform/constraints.txt",
                        "platform/core.py",
                        "platform/mqtt_adapter.py",
                        "platform/requirements.txt",
                    ]
                ),
                "excluded_paths": [],
                "dependency_artifact_refs": [
                    {
                        "id": "artifact.shared.phase8-bridge-runtime",
                        "version": "1",
                    }
                ],
                "builder_adapter_id": f"builder.{provider}.five-layer-v2",
                "supported_runtimes": [f"runtime.{provider}.five-layer-v2"],
                "user_source_policy": "platform_only",
                "compatibility": {
                    "component_versions": ["1"],
                    "builder_versions": ["2"],
                },
            }
            for provider in PROVIDERS
        ]
        + [
            {
                "artifact_id": "artifact.shared.phase8-bridge-runtime",
                "artifact_version": "1",
                "decision_implementation_ids": [],
                "repository_source_path": BRIDGE_RUNTIME_SOURCE,
                "platform_handler": "provider.shared-runtime",
                "digest_policy": "sha256.canonical-source.v1",
                "source_digest": package_source_digest(BRIDGE_RUNTIME_SOURCE),
                "included_paths": ["__init__.py", "bridge_core.py"],
                "excluded_paths": [],
                "dependency_artifact_refs": [],
                "builder_adapter_id": "builder.shared.phase8-bridge-runtime",
                "supported_runtimes": [
                    "runtime.aws.five-layer-v2",
                    "runtime.azure.five-layer-v2",
                    "runtime.gcp.five-layer-v2",
                ],
                "user_source_policy": "platform_only",
                "compatibility": {
                    "component_versions": ["1"],
                    "builder_versions": ["2"],
                },
            }
        ],
        "compatibility": {
            "architecture_profile_schema_versions": ["architecture-profile.v2"],
            "provider_profile_schema_versions": ["provider-implementation-profile.v2"],
            "resolver_versions": ["2"],
            "deployer_runtime_versions": ["2"],
            "deployment_specification_versions": [
                "resolved-deployment-specification.v2"
            ],
        },
        "content_digest": "",
    }
    return redigest_architecture(catalog)


def build_provider_profile(
    provider: str,
    profile: dict[str, Any],
    catalog: dict[str, Any],
    groups: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    mappings = []
    for component in profile["components"]:
        logical = component["component_id"]
        mappings.append(
            {
                "component_id": logical,
                "deployment_component_candidates": [
                    deployment_component_id(provider, logical)
                ],
                "required_capability_ids": component["required_capability_ids"],
                "provided_capability_ids": component["required_capability_ids"],
                "service_model_refs": [
                    f"service-model.{provider}.{item}"
                    for item in groups[provider][logical]
                ],
                "formula_refs": ["formula.phase-08-complete-service-bundles"],
                "supported_region_ids": [f"region.{provider}.{REGIONS[provider]}"],
                "deployment_specification_component_ids": groups[provider][logical],
                "deployment_specification_slot_ids": [LOGICAL_TO_SLOT[logical]],
            }
        )
    edge_mappings = [
        {
            "edge_id": edge["edge_id"],
            "edge_implementation_id": edge_implementation_id(
                provider, provider, edge["edge_id"]
            ),
            "source_deployment_component_ids": [
                deployment_component_id(provider, edge["source_component_id"])
            ],
            "destination_deployment_component_ids": [
                deployment_component_id(provider, edge["destination_component_id"])
            ],
            "mechanism": build_edge_implementation(provider, provider, edge)[
                "mechanism"
            ],
            "catalog_input_port_id": (
                f"catalog.{provider}.{edge['destination_port_id']}"
            ),
            "catalog_output_port_id": f"catalog.{provider}.{edge['source_port_id']}",
            "transfer_route_class": "same_provider_same_region",
            "cost_owner_ids": edge["cost_owner_ids"],
        }
        for edge in profile["edges"]
    ]
    capabilities = sorted(
        {
            capability
            for component in profile["components"]
            for capability in component["required_capability_ids"]
        }
    )
    provider_profile = {
        "schema_version": "provider-implementation-profile.v2",
        "implementation_profile_id": provider_profile_id(provider),
        "implementation_profile_version": "1",
        "architecture_profile_ref": {
            "id": "five-layer-baseline",
            "version": "2",
            "digest": profile["content_digest"],
        },
        "provider": provider,
        "lifecycle_status": "active",
        "region_policy_ref": {
            "id": f"region-policy.{provider}.five-layer-v2",
            "version": "1",
        },
        "permission_set_ref": {
            "id": f"permission-set.{provider}.thesis-demo-v2",
            "version": "1",
        },
        "supported": True,
        "component_mappings": mappings,
        "edge_mappings": edge_mappings,
        "capability_claims": {
            "required_capability_ids": capabilities,
            "provided_capability_ids": capabilities,
            "extra_capability_ids": [],
            "missing_capability_ids": [],
            "evidence_refs": [f"evidence.phase-08-complete-service-bundles.{provider}"],
        },
        "unsupported_reasons": [],
        "compatibility": {
            "compatible_catalog_versions": [
                {"id": catalog["catalog_id"], "version": catalog["catalog_version"]}
            ],
            "compatible_resolver_versions": ["2"],
            "compatible_runtime_versions": ["2"],
            "compatible_deployment_specification_versions": [
                "resolved-deployment-specification.v2"
            ],
        },
        "content_digest": "",
    }
    return redigest_architecture(provider_profile)


def rds_schema() -> dict[str, Any]:
    digest_ref = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
    stable_id = {
        "type": "string",
        "pattern": "^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        "maxLength": 256,
    }
    pinned_ref = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "version", "digest"],
        "properties": {
            "id": stable_id,
            "version": {"type": "string", "pattern": "^[1-9][0-9]*$"},
            "digest": digest_ref,
        },
    }
    dimension = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "dimension_id",
            "classification",
            "value",
            "unit",
            "formula_reference",
            "evidence_reference",
        ],
        "properties": {
            "dimension_id": stable_id,
            "classification": {
                "enum": [
                    "deployable_selection",
                    "capacity",
                    "usage",
                    "fixed_poc",
                    "account_scope",
                ]
            },
            "value": {"type": ["string", "integer", "number", "boolean"]},
            "unit": {"type": "string", "minLength": 1, "maxLength": 64},
            "formula_reference": stable_id,
            "evidence_reference": digest_ref,
            "terraform_target": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9_]{2,127}$",
            },
        },
    }
    selection = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "selection_id",
            "architecture_assignment_id",
            "logical_component_id",
            "implementation_component_id",
            "implementation_component_digest",
            "provider",
            "region",
            "required",
            "dimensions",
        ],
        "properties": {
            "selection_id": stable_id,
            "architecture_assignment_id": stable_id,
            "logical_component_id": stable_id,
            "implementation_component_id": stable_id,
            "implementation_component_digest": digest_ref,
            "provider": {"enum": list(PROVIDERS)},
            "region": {"type": "string", "minLength": 2, "maxLength": 64},
            "required": {"const": True},
            "dimensions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": dimension,
            },
        },
    }
    binding = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "binding_id",
            "source_kind",
            "source_ref",
            "destination_selection_id",
            "destination_input_id",
            "value_type",
            "sensitivity",
            "resolution_stage",
            "validator_id",
            "compatibility_version",
        ],
        "properties": {
            "binding_id": stable_id,
            "source_kind": {
                "enum": [
                    "catalog_constant",
                    "deployment_dimension",
                    "component_output",
                    "platform_configuration",
                    "extension_artifact",
                    "platform_runtime_secret_reference",
                ]
            },
            "source_ref": stable_id,
            "destination_selection_id": stable_id,
            "destination_input_id": stable_id,
            "value_type": {
                "enum": ["string", "integer", "number", "boolean", "json_document"]
            },
            "sensitivity": {"enum": ["public", "internal", "sensitive_reference"]},
            "resolution_stage": {
                "enum": ["package", "preplan", "terraform", "postapply"]
            },
            "validator_id": stable_id,
            "compatibility_version": {"const": "1"},
        },
    }
    fixed = read_json(SERVICE_WORKLOAD)["fixed_dimensions"]
    fixed_properties = {
        key: {"type": "integer", "const": value} for key, value in fixed.items()
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://twin2multicloud.local/contracts/resolved-deployment-specification/v2/schema.json",
        "title": "ResolvedDeploymentSpecification v2",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "calculation_run_id",
            "architecture_profile_ref",
            "optimization_context",
            "readiness",
            "currency",
            "fixed_dimensions",
            "component_selections",
            "bindings",
            "digest",
        ],
        "properties": {
            "schema_version": {"const": "resolved-deployment-specification.v2"},
            "calculation_run_id": {"type": "string", "format": "uuid"},
            "architecture_profile_ref": pinned_ref,
            "optimization_context": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "service_decision_ref",
                    "component_catalog_ref",
                    "workload_ref",
                    "eventing_scenario_ref",
                    "formula_set_ref",
                    "pricing_evidence_refs",
                ],
                "properties": {
                    "service_decision_ref": pinned_ref,
                    "component_catalog_ref": pinned_ref,
                    "workload_ref": pinned_ref,
                    "eventing_scenario_ref": pinned_ref,
                    "formula_set_ref": pinned_ref,
                    "pricing_evidence_refs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["provider", "digest"],
                            "properties": {
                                "provider": {"enum": list(PROVIDERS)},
                                "digest": digest_ref,
                            },
                        },
                    },
                },
            },
            "readiness": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status", "blocking_gate_ids"],
                "properties": {
                    "status": {
                        "enum": ["offline_contract_fixture", "deployment_ready"]
                    },
                    "blocking_gate_ids": {
                        "type": "array",
                        "maxItems": 16,
                        "uniqueItems": True,
                        "items": stable_id,
                    },
                },
            },
            "currency": {"enum": ["USD", "EUR"]},
            "fixed_dimensions": {
                "type": "object",
                "additionalProperties": False,
                "required": list(fixed_properties),
                "properties": fixed_properties,
            },
            "component_selections": {
                "type": "array",
                "minItems": 7,
                "maxItems": 128,
                "items": selection,
            },
            "bindings": {
                "type": "array",
                "minItems": 7,
                "maxItems": 256,
                "items": binding,
            },
            "digest": digest_ref,
        },
    }


def rds_digest(specification: dict[str, Any]) -> str:
    payload = dict(specification)
    payload.pop("digest", None)
    return digest(payload)


def component_capacity_registry() -> dict[str, Any]:
    """Build the minimal runtime registry needed to resolve atomic v2 costs."""

    manifest = read_json(SERVICE_COMPONENTS)
    pricing = read_json(SERVICE_PRICING)
    capacity = read_json(SERVICE_ROOT / "capacity-matrix.json")
    owners = {item["component_id"]: item for item in pricing["component_owners"]}
    components = []
    for component in manifest["components"]:
        component_id = component["component_id"]
        owner = owners.get(component_id)
        if owner is None:
            raise RuntimeError(
                f"Missing pricing owner for implementation component {component_id}"
            )
        if owner["dimensions"] != component["capacity_dimensions"]:
            raise RuntimeError(f"Capacity/pricing dimensions differ for {component_id}")
        components.append(
            {
                "component_id": component_id,
                "component_digest": digest(component),
                "provider": component["provider"],
                "responsibilities": component["responsibilities"],
                "capacity_dimensions": component["capacity_dimensions"],
                "pricing_owner_id": owner["cost_owner_id"],
                "pricing_catalog_key": owner["pricing_catalog_key"],
                "deduplication_key": owner["deduplication_key"],
            }
        )
    registry = {
        "schema_version": "five-layer-v2-component-capacity-registry.v1",
        "package_ref": {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": service_decision_digest(),
        },
        "capacity_evidence_digest": file_digest(SERVICE_ROOT / "capacity-matrix.json"),
        "pricing_ownership_digest": file_digest(SERVICE_PRICING),
        "price_value_policy": pricing["price_value_policy"],
        "same_provider_rule": pricing["same_provider_rule"],
        "shared_support_rules": pricing["shared_support_rules"],
        "provider_bundles": read_json(SERVICE_BUNDLES)["providers"],
        "scenario_capacity": capacity["scenario_results"],
        "components": sorted(components, key=lambda item: item["component_id"]),
        "route_owners": pricing["route_owners"],
        "content_digest": "",
    }
    registry["content_digest"] = digest(registry)
    return registry


def scenario_reference(size: str) -> dict[str, str]:
    catalog = read_json(WORKLOAD_CATALOG)
    scenario_id = f"eventing-{size}-v1"
    return {
        "id": scenario_id,
        "version": "1",
        "digest": catalog["scenario_digests"][scenario_id],
    }


def scenario_size(reference: dict[str, str]) -> str:
    known = {f"eventing-{size}-v1": size for size in ("small", "medium", "large")}
    size = known.get(reference["id"])
    if size is None or reference != scenario_reference(size):
        fail(
            "RDS_V2_EVENTING_MISMATCH",
            "Eventing scenario reference is unknown or has drifted",
        )
    return size


@lru_cache(maxsize=3)
def scenario_inputs(size: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    workload = read_json(SERVICE_WORKLOAD)
    capacity = read_json(SERVICE_ROOT / "capacity-matrix.json")
    event_catalog = read_json(WORKLOAD_CATALOG)
    core = next(item for item in workload["core_scenarios"] if item["size"] == size)
    derived = next(
        item for item in capacity["scenario_results"] if item["size"] == size
    )["derived"]
    event = next(
        item
        for item in event_catalog["scenarios"]
        if item["scenario_id"] == f"eventing-{size}-v1"
    )
    return core, derived, event


def blocking_gate_ids(
    size: str,
    providers: list[str],
    assignment: dict[str, str],
) -> list[str]:
    capacity = read_json(SERVICE_ROOT / "capacity-matrix.json")
    scenario = next(
        item for item in capacity["scenario_results"] if item["size"] == size
    )
    gates: list[str] = []
    for provider in sorted(set(providers)):
        provider_gates = scenario["provider_admission"][provider]["live_gates"]
        gates.extend(
            f"gate.live-capacity.{provider}.{gate.replace('_', '-')}"
            for gate in provider_gates
        )
    if assignment["component.twin-state"] == "aws":
        gates.append("gate.live-pricing.aws.twinmaker-account-plan")
    return sorted(set(gates))


def dimension_classification(dimension_id: str) -> str:
    if dimension_id == "capacity_mode":
        return "deployable_selection"
    if dimension_id in {
        "resource_count",
        "node_count",
        "stream_count",
        "shards_per_stream",
        "timestamp_shards",
        "autoscale_max_ru_per_second",
        "task_count",
    }:
        return "capacity"
    return "usage"


def dimension_value_type(value: str | int) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    return "string"


def dimension_validator(dimension_id: str, value: str | int) -> str:
    if dimension_id == "capacity_mode":
        return "validator.capacity-mode.v1"
    if isinstance(value, int):
        return "validator.non-negative-integer.v1"
    return "validator.non-negative-decimal-string.v1"


def build_dimension(
    provider: str,
    component_id: str,
    logical: str,
    dimension_id: str,
    size: str,
) -> dict[str, Any]:
    value, unit = dimension_value(component_id, logical, dimension_id, size)
    return {
        "dimension_id": f"dimension.{provider}.{component_id}.{dimension_id}",
        "classification": dimension_classification(dimension_id),
        "value": value,
        "unit": unit,
        "formula_reference": "formula.phase-08-complete-service-bundles",
        "evidence_reference": file_digest(SERVICE_ROOT / "capacity-matrix.json"),
    }


def decimal_ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal(1)))
    return format(normalized, "f")


def azure_cosmos_autoscale_floor(
    hot_payload_gib: object,
    *,
    peak_messages_per_second: Decimal,
    rollup_writes_per_second: Decimal,
    dashboard_queries_per_second: Decimal,
) -> int:
    required = max(
        Decimal("1000"),
        Decimal(str(hot_payload_gib)) * Decimal("10"),
        (peak_messages_per_second + rollup_writes_per_second) * Decimal("10")
        + peak_messages_per_second
        + dashboard_queries_per_second * Decimal("720"),
    )
    return decimal_ceil(required / Decimal("1000")) * 1000


def dimension_value(
    component_id: str,
    logical: str,
    dimension_id: str,
    size: str,
) -> tuple[str | int, str]:
    core, derived, event = scenario_inputs(size)
    fixed = read_json(SERVICE_WORKLOAD)["fixed_dimensions"]
    month_seconds = Decimal("2592000")
    messages = int(core["messages_per_month"])
    event_count = int(event["events_per_month"])
    event_attempts = decimal_ceil(
        Decimal(event_count)
        * (
            Decimal("1")
            + Decimal(str(event["retry_share"]))
            + Decimal(str(event["replay_share"]))
        )
    )
    command_executions = decimal_ceil(
        Decimal(event_count)
        * Decimal(str(event["rule_match_share"]))
        * Decimal(str(event["device_command_share_of_matches"]))
    )
    consumer_count = len(event["mandatory_processed_consumers"]) + len(
        event["extra_processed_consumers"]
    )
    dashboard_requests = (
        int(core["aggregate_dashboard_refreshes_per_hour"])
        * int(core["api_calls_per_aggregate_dashboard_refresh"])
        * int(core["dashboard_active_hours_per_day"])
        * 30
    )
    twin_operations = decimal_ceil(
        (
            Decimal(str(core["twin_state_materializations_per_second"]))
            + Decimal(str(core["twin_graph_updates_per_second"]))
        )
        * month_seconds
    ) + int(derived["l4_inspection_reads_per_month"])
    request_count = (
        dashboard_requests
        if "reader" in component_id or logical == "component.visualization"
        else event_attempts
        if any(
            token in component_id
            for token in (
                "event-adapter",
                "sqs",
                "sns",
                "pubsub",
                "event-hubs",
                "kinesis",
            )
        )
        else messages
    )
    event_bytes = event_attempts * int(event["average_event_payload_bytes"])
    canonical_payload_bytes = Decimal(str(derived["canonical_payload_bytes"]))
    rollup_document_count = int(core["device_count"]) * int(
        derived["maximum_aggregate_rollup_points"]
    )
    dashboard_point_reads = dashboard_requests * int(
        derived["maximum_aggregate_rollup_points"]
    )
    rollup_storage_gib = (
        Decimal(rollup_document_count) * canonical_payload_bytes / Decimal("1073741824")
    )
    twin_storage_gib = (
        Decimal(int(core["twin_entity_count"]))
        * canonical_payload_bytes
        / Decimal("1073741824")
    )
    storage_gib = {
        "aws.dynamodb-on-demand-raw": str(derived["hot_payload_gib"]),
        "aws.dynamodb-on-demand-hourly-rollup": decimal_text(rollup_storage_gib),
        "azure.cosmos-db-nosql-raw-and-rollup": decimal_text(
            Decimal(str(derived["hot_payload_gib"])) + rollup_storage_gib
        ),
        "gcp.firestore-native-standard-raw-and-rollup": decimal_text(
            Decimal(str(derived["hot_payload_gib"])) + rollup_storage_gib
        ),
        "gcp.firestore-native-standard-bounded-twin": decimal_text(twin_storage_gib),
        "gcp.persistent-disk-rwo": str(fixed["gcp_grafana_persistent_disk_gib"]),
    }.get(
        component_id,
        {
            "component.hot-storage": str(derived["hot_payload_gib"]),
            "component.cool-storage": str(derived["cool_payload_gib"]),
            "component.archive-storage": str(derived["archive_payload_gib"]),
        }.get(logical, "0"),
    )
    units: dict[str, str] = {
        "resource_count": "count",
        "stored_gib_month": "GiB-month",
        "read_requests": "requests/month",
        "write_requests": "requests/month",
        "request_units": "RU/month",
        "capacity_mode": "enum",
        "autoscale_max_ru_per_second": "RU/s",
        "document_reads": "operations/month",
        "document_writes": "operations/month",
        "document_deletes": "operations/month",
        "timestamp_shards": "count",
        "requests": "requests/month",
        "gib_seconds": "GiB-s/month",
        "execution_seconds": "seconds/month",
        "vcpu_seconds": "vCPU-s/month",
        "memory_gib_seconds": "GiB-s/month",
        "workspace_count": "count",
        "editor_seats": "seats/month",
        "viewer_seats": "seats/month",
        "node_count": "count",
        "node_hours": "hours/month",
        "throughput_unit_hours": "TU-hours/month",
        "capacity_unit_hours": "CU-hours/month",
        "stream_count": "count",
        "shards_per_stream": "count",
        "shard_hours": "shard-hours/month",
        "payload_units": "units/month",
        "publish_bytes": "bytes/month",
        "delivery_bytes": "bytes/month",
        "publishes": "requests/month",
        "messaging_unit_hours": "MU-hours/month",
        "operations": "operations/month",
        "log_ingestion_gib": "GiB/month",
        "retained_log_gib_month": "GiB-month",
        "rule_hours": "hours/month",
        "processed_bytes": "bytes/month",
        "connected_devices": "count",
        "messages": "messages/month",
        "twin_entities": "count",
        "twin_operations": "operations/month",
        "scheduled_invocations": "invocations/month",
        "workflow_executions": "executions/month",
        "workflow_transitions": "transitions/month",
        "task_count": "count",
    }
    if dimension_id == "resource_count":
        if "bifromq" in component_id:
            return ({"small": 3, "medium": 3, "large": 12}[size], units[dimension_id])
        return (1, units[dimension_id])
    if dimension_id == "task_count":
        task_count_key = {
            "aws.ecs-fargate-storage-mover": "aws_storage_tasks",
            "azure.container-apps-scheduled-storage-job": "azure_storage_tasks",
            "gcp.cloud-run-storage-job": "gcp_storage_tasks",
        }.get(component_id)
        if task_count_key is None:
            raise RuntimeError(
                f"No exact storage task-count binding for component: {component_id}"
            )
        return int(derived[task_count_key]), units[dimension_id]
    values: dict[str, str | int] = {
        "stored_gib_month": storage_gib,
        "read_requests": (
            messages + dashboard_point_reads
            if component_id == "aws.dynamodb-on-demand-hourly-rollup"
            else 0
        ),
        "write_requests": (
            messages * 2
            if component_id
            in {
                "aws.dynamodb-on-demand-raw",
                "aws.dynamodb-on-demand-hourly-rollup",
            }
            else 0
        ),
        "request_units": messages * 21 + dashboard_point_reads,
        "capacity_mode": (
            "autoscale"
            if size == "large" and "cosmos" in component_id
            else "serverless"
            if "cosmos" in component_id
            else "not_applicable"
        ),
        # Offline comparison uses the storage/operation-driven provisionable
        # maximum. It is not a measured request-charge capacity proof and the
        # corresponding live gates remain mandatory before deployment.
        "autoscale_max_ru_per_second": (
            azure_cosmos_autoscale_floor(
                derived["hot_payload_gib"],
                peak_messages_per_second=Decimal(
                    str(core["average_telemetry_per_second"])
                ),
                rollup_writes_per_second=Decimal(
                    str(core["average_telemetry_per_second"])
                ),
                dashboard_queries_per_second=Decimal(
                    str(derived["aggregate_dashboard_query_rate_per_second"])
                ),
            )
            if size == "large" and "cosmos" in component_id
            else 0
        ),
        "document_reads": (
            int(derived["l4_inspection_reads_per_month"])
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else messages + dashboard_point_reads
        ),
        "document_writes": (
            twin_operations
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else messages * 2
        ),
        "document_deletes": (
            0
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else messages + rollup_document_count
        ),
        "timestamp_shards": (
            1
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else int(derived["firestore_timestamp_shards"])
        ),
        "requests": request_count,
        "gib_seconds": str(Decimal(request_count) * Decimal("0.125")),
        "execution_seconds": request_count,
        "vcpu_seconds": request_count,
        "memory_gib_seconds": str(Decimal(request_count) * Decimal("0.5")),
        "workspace_count": 1,
        "editor_seats": int(core["monthly_editor_seats"]),
        "viewer_seats": int(core["monthly_viewer_seats"]),
        "node_count": (
            {"small": 3, "medium": 3, "large": 12}[size]
            if "bifromq" in component_id
            else {"small": 0, "medium": 0, "large": 4}[size]
            if component_id == "gcp.ordered-mqtt-pubsub-adapter"
            else 1
        ),
        "node_hours": (
            {"small": 2190, "medium": 2190, "large": 8760}[size]
            if "bifromq" in component_id
            else {"small": 0, "medium": 0, "large": 2920}[size]
            if component_id == "gcp.ordered-mqtt-pubsub-adapter"
            else 730
        ),
        "throughput_unit_hours": {"small": 730, "medium": 8030, "large": 0}[size],
        "capacity_unit_hours": {"small": 0, "medium": 0, "large": 4380}[size],
        "stream_count": 2,
        "shards_per_stream": {"small": 1, "medium": 6, "large": 200}[size],
        "shard_hours": {"small": 1460, "medium": 8760, "large": 292000}[size],
        "payload_units": event_attempts,
        "publish_bytes": event_bytes,
        "delivery_bytes": event_bytes * max(1, consumer_count),
        "publishes": event_attempts,
        "messaging_unit_hours": 730,
        "operations": event_attempts,
        "log_ingestion_gib": str(
            Decimal(messages + event_attempts) * Decimal("256") / Decimal(1073741824)
        ),
        "retained_log_gib_month": str(
            Decimal(messages + event_attempts) * Decimal("256") / Decimal(1073741824)
        ),
        "rule_hours": 730,
        "processed_bytes": (
            dashboard_requests
            * int(fixed["reader_maximum_points"])
            * decimal_ceil(Decimal(str(derived["canonical_payload_bytes"])))
            if component_id == "gcp.grafana-tls-load-balancer"
            else int(derived["monthly_raw_payload_bytes"])
        ),
        "connected_devices": int(core["device_count"]),
        "messages": (
            command_executions if component_id == "aws.iot-commands" else messages
        ),
        "twin_entities": int(core["twin_entity_count"]),
        "twin_operations": twin_operations,
        "scheduled_invocations": 8640,
        "workflow_executions": decimal_ceil(
            Decimal(event_count)
            * Decimal(str(event["rule_match_share"]))
            * Decimal(str(event["workflow_start_share_of_matches"]))
        ),
        "workflow_transitions": decimal_ceil(
            Decimal(event_count)
            * Decimal(str(event["rule_match_share"]))
            * Decimal(str(event["workflow_start_share_of_matches"]))
            * Decimal("3")
        ),
    }
    if dimension_id not in values:
        raise RuntimeError(f"Unknown capacity dimension: {dimension_id}")
    return values[dimension_id], units[dimension_id]


def build_rds(
    assignment: dict[str, str],
    profile: dict[str, Any],
    catalog: dict[str, Any],
    *,
    size: str = "small",
) -> dict[str, Any]:
    service_index = service_component_index()
    selections = []
    bindings = []
    for provider, logical, component_id in selected_groups_for_assignment(assignment):
        component = service_index[(provider, component_id)]
        component_digest = digest(component)
        selection_id = f"selection.{provider}.{component_id}"
        dimensions = []
        for dimension_id in component["capacity_dimensions"]:
            dimensions.append(
                build_dimension(
                    provider,
                    component_id,
                    logical,
                    dimension_id,
                    size,
                )
            )
        if not dimensions:
            raise RuntimeError(f"Component has no capacity dimension: {component_id}")
        selections.append(
            {
                "selection_id": selection_id,
                "architecture_assignment_id": (
                    f"assignment.{logical.removeprefix('component.')}"
                ),
                "logical_component_id": logical,
                "implementation_component_id": component_id,
                "implementation_component_digest": component_digest,
                "provider": provider,
                "region": REGIONS[provider],
                "required": True,
                "dimensions": dimensions,
            }
        )
        for dimension_id, dimension in zip(
            component["capacity_dimensions"], dimensions, strict=True
        ):
            bindings.append(
                {
                    "binding_id": (f"binding.{provider}.{component_id}.{dimension_id}"),
                    "source_kind": "deployment_dimension",
                    "source_ref": dimension["dimension_id"],
                    "destination_selection_id": selection_id,
                    "destination_input_id": (
                        f"input.{dimension['classification']}.{dimension_id}"
                    ),
                    "value_type": dimension_value_type(dimension["value"]),
                    "sensitivity": "internal",
                    "resolution_stage": "preplan",
                    "validator_id": dimension_validator(
                        dimension_id, dimension["value"]
                    ),
                    "compatibility_version": "1",
                }
            )
    providers = sorted({item["provider"] for item in selections})
    specification = {
        "schema_version": "resolved-deployment-specification.v2",
        "calculation_run_id": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "twin2multicloud:five-layer-v2:"
                + size
                + ":"
                + ",".join(
                    f"{logical}={assignment[logical]}" for logical in LOGICAL_COMPONENTS
                ),
            )
        ),
        "architecture_profile_ref": {
            "id": "five-layer-baseline",
            "version": "2",
            "digest": profile["content_digest"],
        },
        "optimization_context": {
            "service_decision_ref": {
                "id": "phase-08-complete-service-bundles",
                "version": "1",
                "digest": service_decision_digest(),
            },
            "component_catalog_ref": {
                "id": catalog["catalog_id"],
                "version": catalog["catalog_version"],
                "digest": catalog["content_digest"],
            },
            "workload_ref": {
                "id": "five-layer-workload",
                "version": "2",
                "digest": workload_contract_digest(),
            },
            "eventing_scenario_ref": scenario_reference(size),
            "formula_set_ref": {
                "id": "phase-08-complete-service-bundles",
                "version": "1",
                "digest": file_digest(SERVICE_PRICING),
            },
            "pricing_evidence_refs": [
                {"provider": provider, "digest": file_digest(SERVICE_SOURCES)}
                for provider in providers
            ],
        },
        "readiness": {
            "status": "offline_contract_fixture",
            "blocking_gate_ids": blocking_gate_ids(size, providers, assignment),
        },
        "currency": "USD",
        "fixed_dimensions": read_json(SERVICE_WORKLOAD)["fixed_dimensions"],
        "component_selections": selections,
        "bindings": bindings,
        "digest": "",
    }
    specification["digest"] = rds_digest(specification)
    return specification


def validate_rds(
    specification: dict[str, Any],
    schema: dict[str, Any],
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> None:
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            specification
        ),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        fail("RDS_V2_SCHEMA_INVALID", errors[0].message)
    if specification["digest"] != rds_digest(specification):
        fail("RDS_V2_DIGEST_MISMATCH", "RDS digest differs from canonical content")
    if specification["architecture_profile_ref"] != {
        "id": "five-layer-baseline",
        "version": "2",
        "digest": profile["content_digest"],
    }:
        fail("RDS_V2_PROFILE_MISMATCH", "RDS profile reference drifted")
    context = specification["optimization_context"]
    expected_refs = {
        "service_decision_ref": {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": service_decision_digest(),
        },
        "component_catalog_ref": {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
        },
        "workload_ref": {
            "id": "five-layer-workload",
            "version": "2",
            "digest": workload_contract_digest(),
        },
        "formula_set_ref": {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": file_digest(SERVICE_PRICING),
        },
    }
    for key, expected in expected_refs.items():
        if context[key] != expected:
            fail("RDS_V2_EVIDENCE_MISMATCH", f"RDS {key} drifted")
    size = scenario_size(context["eventing_scenario_ref"])
    if (
        specification["fixed_dimensions"]
        != read_json(SERVICE_WORKLOAD)["fixed_dimensions"]
    ):
        fail("RDS_V2_DIMENSION_MISMATCH", "Fixed PoC dimensions drifted")

    readiness = specification["readiness"]
    selected_providers = sorted(
        {item["provider"] for item in specification["component_selections"]}
    )
    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in specification["component_selections"]
    }
    if context["pricing_evidence_refs"] != [
        {"provider": provider, "digest": file_digest(SERVICE_SOURCES)}
        for provider in selected_providers
    ]:
        fail(
            "RDS_V2_EVIDENCE_MISMATCH",
            "Pricing evidence does not exactly match the selected providers",
        )
    if readiness["status"] == "offline_contract_fixture":
        if readiness["blocking_gate_ids"] != blocking_gate_ids(
            size, selected_providers, assignment
        ):
            fail(
                "RDS_V2_READINESS_INVALID",
                "Offline specification does not retain every activation/live gate",
            )
    elif readiness["blocking_gate_ids"]:
        fail(
            "RDS_V2_READINESS_INVALID",
            "Deployment-ready specification cannot retain blocking gates",
        )
    elif (
        profile["lifecycle_status"] != "active"
        or catalog["lifecycle_status"] != "active"
    ):
        fail(
            "RDS_V2_PROFILE_NOT_ACTIVE",
            "Deployment-ready specification requires active profile and catalog",
        )

    selections = specification["component_selections"]
    selection_ids = [item["selection_id"] for item in selections]
    if len(selection_ids) != len(set(selection_ids)):
        fail("RDS_V2_DUPLICATE_SELECTION", "Component selection IDs repeat")
    logical_providers: dict[str, set[str]] = {}
    for selection in selections:
        logical_providers.setdefault(selection["logical_component_id"], set()).add(
            selection["provider"]
        )
    if set(logical_providers) != set(LOGICAL_COMPONENTS) or any(
        len(providers) != 1 for providers in logical_providers.values()
    ):
        fail(
            "RDS_V2_ASSIGNMENT_INCOMPLETE", "Logical component ownership is incomplete"
        )
    if (
        logical_providers["component.hot-storage"]
        != logical_providers["component.visualization"]
    ):
        fail(
            "PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED",
            "L3 hot and L5 must share one provider",
        )
    assignment = {
        logical: next(iter(providers))
        for logical, providers in logical_providers.items()
    }
    expected_tuples = selected_groups_for_assignment(assignment)
    actual_tuples = [
        (
            item["provider"],
            item["logical_component_id"],
            item["implementation_component_id"],
        )
        for item in selections
    ]
    if actual_tuples != expected_tuples:
        fail("RDS_V2_SELECTION_INCOMPLETE", "Selected service bundle differs")
    service_index = service_component_index()
    for selection in selections:
        component = service_index.get(
            (selection["provider"], selection["implementation_component_id"])
        )
        if component is None:
            fail("RDS_V2_COMPONENT_UNKNOWN", "Selected component is unknown")
        if selection["implementation_component_digest"] != digest(component):
            fail("RDS_V2_EVIDENCE_MISMATCH", "Component digest drifted")
        expected_dimension_ids = [
            (
                f"dimension.{selection['provider']}."
                f"{selection['implementation_component_id']}.{dimension_id}"
            )
            for dimension_id in component["capacity_dimensions"]
        ]
        if [
            item["dimension_id"] for item in selection["dimensions"]
        ] != expected_dimension_ids:
            fail("RDS_V2_DIMENSION_MISMATCH", "Capacity dimensions drifted")
        expected_dimensions = []
        for dimension_id in component["capacity_dimensions"]:
            expected_dimensions.append(
                build_dimension(
                    selection["provider"],
                    selection["implementation_component_id"],
                    selection["logical_component_id"],
                    dimension_id,
                    size,
                )
            )
        for actual, expected in zip(
            selection["dimensions"], expected_dimensions, strict=True
        ):
            dimension_name = actual["dimension_id"].rsplit(".", 1)[-1]
            if (
                readiness["status"] == "deployment_ready"
                and dimension_name == "autoscale_max_ru_per_second"
                and size == "large"
                and "cosmos" in selection["implementation_component_id"]
            ):
                expected_without_value = dict(expected)
                actual_without_value = dict(actual)
                expected_without_value.pop("value")
                expected_evidence = expected_without_value.pop("evidence_reference")
                actual_value = actual_without_value.pop("value")
                actual_evidence = actual_without_value.pop("evidence_reference")
                if (
                    not isinstance(actual_value, int)
                    or isinstance(actual_value, bool)
                    or actual_value <= 0
                    or not isinstance(actual_evidence, str)
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", actual_evidence) is None
                    or actual_evidence == expected_evidence
                    or actual_without_value != expected_without_value
                ):
                    fail(
                        "RDS_V2_CAPACITY_UNRESOLVED",
                        "Deployment-ready Cosmos autoscale requires measured "
                        "positive RU/s and distinct pinned evidence",
                    )
            elif actual != expected:
                fail(
                    "RDS_V2_DIMENSION_MISMATCH",
                    "Capacity dimension values or evidence drifted",
                )
    expected_bindings = []
    for selection in selections:
        for dimension in selection["dimensions"]:
            dimension_name = dimension["dimension_id"].rsplit(".", 1)[-1]
            expected_bindings.append(
                {
                    "binding_id": (
                        f"binding.{selection['provider']}."
                        f"{selection['implementation_component_id']}.{dimension_name}"
                    ),
                    "source_kind": "deployment_dimension",
                    "source_ref": dimension["dimension_id"],
                    "destination_selection_id": selection["selection_id"],
                    "destination_input_id": (
                        f"input.{dimension['classification']}.{dimension_name}"
                    ),
                    "value_type": dimension_value_type(dimension["value"]),
                    "sensitivity": "internal",
                    "resolution_stage": "preplan",
                    "validator_id": dimension_validator(
                        dimension_name, dimension["value"]
                    ),
                    "compatibility_version": "1",
                }
            )
    if specification["bindings"] != expected_bindings:
        fail(
            "RDS_V2_BINDING_INCOMPLETE",
            "Every capacity dimension needs one canonical typed binding",
        )


def build_rta(
    provider_assignment: dict[str, str],
    rds: dict[str, Any],
    profile: dict[str, Any],
    provider_profiles: dict[str, dict[str, Any]],
    catalog: dict[str, Any],
    runtime: ModuleType,
) -> dict[str, Any]:
    assignments = []
    assignment_by_logical: dict[str, dict[str, Any]] = {}
    for component in profile["components"]:
        logical = component["component_id"]
        provider = provider_assignment[logical]
        provider_profile = provider_profiles[provider]
        catalog_component = next(
            item
            for item in catalog["components"]
            if item["deployment_component_id"]
            == deployment_component_id(provider, logical)
        )
        assignment = {
            "assignment_id": f"assignment.{logical.removeprefix('component.')}",
            "responsibility_id": component["responsibility_id"],
            "logical_component_id": logical,
            "provider": provider,
            "provider_implementation_profile_ref": {
                "id": provider_profile["implementation_profile_id"],
                "version": provider_profile["implementation_profile_version"],
                "digest": provider_profile["content_digest"],
            },
            "deployment_component_id": deployment_component_id(provider, logical),
            "deployment_component_version": "1",
            "service_id": catalog_component["service_id"],
            "region": REGIONS[provider],
            "capability_evidence": component["required_capability_ids"],
            "pricing_model_refs": catalog_component["pricing_model_refs"],
            "formula_refs": catalog_component["formula_refs"],
            "deployment_specification_component_ids": [
                selection["implementation_component_id"]
                for selection in rds["component_selections"]
                if selection["architecture_assignment_id"]
                == f"assignment.{logical.removeprefix('component.')}"
            ],
            "cost_contribution": {"currency": "USD", "monthly_amount": "0"},
            "required": True,
        }
        assignments.append(assignment)
        assignment_by_logical[logical] = assignment

    resolved_edges = []
    for edge in profile["edges"]:
        source = assignment_by_logical[edge["source_component_id"]]
        target = assignment_by_logical[edge["destination_component_id"]]
        implementation = build_edge_implementation(
            source["provider"], target["provider"], edge
        )
        resolved_edges.append(
            {
                "resolved_edge_id": f"resolved.{edge['edge_id'].removeprefix('edge.')}",
                "edge_id": edge["edge_id"],
                "source_assignment_id": source["assignment_id"],
                "source_port_id": implementation["source_output_port_id"],
                "destination_assignment_id": target["assignment_id"],
                "destination_port_id": implementation["destination_input_port_id"],
                "edge_implementation_id": implementation["edge_implementation_id"],
                "mechanism": implementation["mechanism"],
                "delivery_semantics": edge["delivery_requirements"],
                "transfer_route_class": implementation["transfer_route_class"],
                "transfer_evidence_refs": [
                    f"evidence.route.{source['provider']}-to-{target['provider']}"
                ],
                "formula_refs": implementation["formula_refs"],
                "cost_contribution": {
                    "currency": "USD",
                    "monthly_amount": "0",
                },
                "trust_contract_ref": implementation["trust_contract_ref"],
                "observability_contract_ref": implementation[
                    "observability_contract_ref"
                ],
                "deployment_input_binding_ids": [
                    f"binding.input.{edge['edge_id'].removeprefix('edge.')}"
                ],
                "deployment_output_binding_ids": [
                    f"binding.output.{edge['edge_id'].removeprefix('edge.')}"
                ],
            }
        )
    used_providers = sorted({item["provider"] for item in assignments})
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
    responsibility_totals = []
    for responsibility in profile["responsibilities"]:
        responsibility_totals.append(
            {
                "item_id": responsibility["responsibility_id"],
                "monthly_amount": "0",
            }
        )
    resolution = {
        "schema_version": "resolved-twin-architecture.v2",
        "resolution_status": "offline_contract_fixture",
        "resolution_id": "00000000-0000-0000-0000-000000000000",
        "calculation_run_id": rds["calculation_run_id"],
        "architecture_profile_ref": {
            "id": profile["profile_id"],
            "version": profile["profile_version"],
            "digest": profile["content_digest"],
        },
        "optimization_bundle_ref": {
            key: profile["optimization_bundle"][key]
            for key in (
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
                "version": provider_profiles[provider][
                    "implementation_profile_version"
                ],
                "digest": provider_profiles[provider]["content_digest"],
                "provider": provider,
            }
            for provider in used_providers
        ],
        "workload_contract_ref": profile["workload_contract_ref"],
        "pricing_evidence_refs": [
            {
                "id": f"pricing-evidence.{provider}.phase-08-v2",
                "version": "1",
                "digest": file_digest(SERVICE_SOURCES),
                "provider": provider,
                "currency": "USD",
            }
            for provider in used_providers
        ],
        "component_assignments": assignments,
        "resolved_edges": resolved_edges,
        "extension_bindings": [
            {
                "slot_id": "processor.telemetry",
                "slot_version": "1",
                "artifact_id": "artifact.user.processor.example",
                "artifact_digest": digest(
                    {"fixture": "five-layer-v2", "runtime": "python311"}
                ),
                "logical_component_id": "component.processing",
                "configuration_digest": digest({"scale_factor": 1}),
                "validation_contract_version": "1",
            }
        ],
        "deployment_specification_ref": {
            "schema_version": rds["schema_version"],
            "digest": rds["digest"],
            "calculation_run_id": rds["calculation_run_id"],
        },
        "cost_summary": {
            "currency": "USD",
            "responsibility_totals": responsibility_totals,
            "component_totals": [
                {"item_id": item["component_id"], "monthly_amount": "0"}
                for item in profile["components"]
            ],
            "edge_totals": [
                {"item_id": item["edge_id"], "monthly_amount": "0"}
                for item in profile["edges"]
            ],
            "monthly_total": "0",
        },
        "functional_completeness": {
            "status": "complete",
            "required_capability_ids": capabilities,
            "provided_capability_ids": capabilities,
            "provider_extra_capability_ids": [],
            "missing_capability_ids": [],
            "validator_version": "2",
            "validation_digest": digest(validation_payload),
        },
        "content_digest": "",
    }
    resolution["resolution_id"] = runtime.calculate_resolution_id(resolution)
    resolution["content_digest"] = runtime.calculate_digest(resolution)
    return resolution


def generate_deployment_manifest_v4(
    valid_rds: dict[str, dict[str, Any]],
    valid_rtas: dict[str, dict[str, Any]],
    catalog: dict[str, Any],
) -> None:
    """Generate the additive RTA-v2/RDS-v2 package envelope."""

    schema = copy.deepcopy(read_json(DEPLOYMENT_MANIFEST_V3 / "schema.json"))
    schema["$id"] = (
        "https://twin2multicloud.local/contracts/deployment-manifest/v4/schema.json"
    )
    schema["title"] = "DeploymentManifest v4"
    schema["properties"]["manifest_version"]["const"] = "4.0"
    architecture_schema = schema["$defs"]["resolved_twin_architecture"]
    architecture_schema["properties"]["schema_version"]["const"] = (
        "resolved-twin-architecture.v2"
    )
    specification_schema = schema["$defs"]["resolved_deployment_specification"]
    specification_schema["required"] = [
        "schema_version",
        "calculation_run_id",
        "component_selections",
        "digest",
    ]
    specification_schema["properties"].pop("components")
    specification_schema["properties"]["schema_version"]["const"] = (
        "resolved-deployment-specification.v2"
    )
    specification_schema["properties"]["component_selections"] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 512,
    }

    if DEPLOYMENT_MANIFEST_V4.exists():
        shutil.rmtree(DEPLOYMENT_MANIFEST_V4)
    write_json(DEPLOYMENT_MANIFEST_V4 / "schema.json", schema)
    valid_manifests: dict[str, dict[str, Any]] = {}
    provider_key_by_logical = {
        logical: {
            "component.ingestion": "layer_1_provider",
            "component.processing": "layer_2_provider",
            "component.hot-storage": "layer_3_hot_provider",
            "component.cool-storage": "layer_3_cold_provider",
            "component.archive-storage": "layer_3_archive_provider",
            "component.twin-state": "layer_4_provider",
            "component.visualization": "layer_5_provider",
        }[logical]
        for logical in LOGICAL_COMPONENTS
    }
    for fixture_id in sorted(valid_rds):
        specification = valid_rds[fixture_id]
        architecture = valid_rtas[fixture_id]
        providers = {
            provider_key_by_logical[item["logical_component_id"]]: item["provider"]
            for item in architecture["component_assignments"]
        }
        used_providers = sorted(set(providers.values()))
        manifest = {
            "manifest_version": "4.0",
            "generated_at": "2026-08-03T00:00:00Z",
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
                "name": f"Five-layer v2 {fixture_id}",
                "resource_name": f"five-layer-v2-{fixture_id}",
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
        valid_manifests[fixture_id] = manifest
        write_json(
            DEPLOYMENT_MANIFEST_V4 / "fixtures" / "valid" / f"{fixture_id}.json",
            manifest,
        )

    cross_version = copy.deepcopy(valid_manifests["single-cloud-aws-small"])
    cross_version["resolved_deployment_specification"]["schema_version"] = (
        "resolved-deployment-specification.v1"
    )
    write_json(
        DEPLOYMENT_MANIFEST_V4 / "fixtures" / "invalid" / "cross-version-rds.json",
        {"manifest": cross_version},
    )
    (DEPLOYMENT_MANIFEST_V4 / "README.md").write_text(
        "# DeploymentManifest v4\n\n"
        "Additive package envelope for RTA v2 and RDS v2. Canonical fixtures "
        "remain offline contract evidence and are not executable deployment "
        "claims. Deployment readiness is enforced semantically by Management "
        "and the Deployer. Generated by "
        "`scripts/sync_five_layer_v2_contracts.py`.\n",
        encoding="utf-8",
    )


def generate() -> None:
    generate_v2_schemas()
    profile = build_profile()
    registry = build_semantic_registry(profile)
    write_json(ARCH_V2 / "semantic-registry.json", registry)
    runtime = load_v2_runtime()
    groups = service_groups()
    catalog = build_catalog(profile, groups)
    provider_profiles = {
        provider: build_provider_profile(provider, profile, catalog, groups)
        for provider in PROVIDERS
    }

    definition_paths = {
        DEFINITIONS
        / "profiles"
        / "five-layer-baseline"
        / "2"
        / "profile.json": profile,
        DEFINITIONS
        / "component-catalogs"
        / "complete-service"
        / "1"
        / "catalog.json": catalog,
        **{
            DEFINITIONS
            / "provider-implementations"
            / "five-layer-baseline"
            / "2"
            / provider
            / "1.json": provider_profile
            for provider, provider_profile in provider_profiles.items()
        },
    }
    for path, document in definition_paths.items():
        write_json(path, document)

    schema = rds_schema()
    write_json(RDS_V2 / "schema.json", schema)
    write_json(
        RDS_V2 / "component-capacity-registry.json",
        component_capacity_registry(),
    )
    if (RDS_V2 / "fixtures").exists():
        shutil.rmtree(RDS_V2 / "fixtures")
    fixture_cases = {
        "single-cloud-aws-small": (
            assignment_for_bundle("aws", "aws"),
            "small",
        ),
        "two-cloud-azure-l3l5-gcp-l4-medium": (
            assignment_for_bundle("azure", "gcp"),
            "medium",
        ),
        "three-cloud-mixed-large": (
            {
                "component.ingestion": "aws",
                "component.processing": "azure",
                "component.hot-storage": "gcp",
                "component.cool-storage": "aws",
                "component.archive-storage": "azure",
                "component.twin-state": "aws",
                "component.visualization": "gcp",
            },
            "large",
        ),
    }
    valid_rds: dict[str, dict[str, Any]] = {}
    valid_rtas: dict[str, dict[str, Any]] = {}
    for fixture_id, (provider_assignment, size) in fixture_cases.items():
        specification = build_rds(
            provider_assignment,
            profile,
            catalog,
            size=size,
        )
        valid_rds[fixture_id] = specification
        write_json(
            RDS_V2 / "fixtures" / "valid" / f"{fixture_id}.json",
            specification,
        )
        valid_rtas[fixture_id] = build_rta(
            provider_assignment,
            specification,
            profile,
            provider_profiles,
            catalog,
            runtime,
        )

    if (ARCH_V2 / "fixtures").exists():
        shutil.rmtree(ARCH_V2 / "fixtures")
    valid_documents = {
        "five-layer-baseline-v2-profile.json": profile,
        "complete-service-component-catalog.json": catalog,
        **{
            f"{provider}-five-layer-v2-provider-profile.json": document
            for provider, document in provider_profiles.items()
        },
        **{
            f"{fixture_id}-resolved.json": document
            for fixture_id, document in valid_rtas.items()
        },
    }
    for filename, document in valid_documents.items():
        write_json(ARCH_V2 / "fixtures" / "valid" / filename, document)

    generate_deployment_manifest_v4(valid_rds, valid_rtas, catalog)

    cross_version = copy.deepcopy(valid_rtas["two-cloud-azure-l3l5-gcp-l4-medium"])
    cross_version["deployment_specification_ref"]["schema_version"] = (
        "resolved-deployment-specification.v1"
    )
    cross_version["content_digest"] = runtime.calculate_digest(cross_version)
    colocation = copy.deepcopy(valid_rtas["two-cloud-azure-l3l5-gcp-l4-medium"])
    visual = next(
        item
        for item in colocation["component_assignments"]
        if item["logical_component_id"] == "component.visualization"
    )
    visual.update(
        {
            "provider": "gcp",
            "provider_implementation_profile_ref": {
                "id": provider_profiles["gcp"]["implementation_profile_id"],
                "version": "1",
                "digest": provider_profiles["gcp"]["content_digest"],
            },
            "deployment_component_id": deployment_component_id(
                "gcp", "component.visualization"
            ),
            "service_id": "gcp.visualization.v2",
            "region": REGIONS["gcp"],
            "deployment_specification_component_ids": groups["gcp"][
                "component.visualization"
            ],
        }
    )
    colocation["resolution_id"] = runtime.calculate_resolution_id(colocation)
    colocation["content_digest"] = runtime.calculate_digest(colocation)
    write_json(
        ARCH_V2 / "fixtures" / "invalid" / "cross-version-rds.json",
        {"expected_error": "ARCH_SCHEMA_INVALID", "document": cross_version},
    )
    write_json(
        ARCH_V2 / "fixtures" / "invalid" / "l3-l5-not-colocated.json",
        {"expected_error": "ARCH_BUNDLE_INCOMPATIBLE", "document": colocation},
    )

    invalid_rds = copy.deepcopy(valid_rds["single-cloud-aws-small"])
    invalid_rds["component_selections"][0]["implementation_component_id"] = (
        "aws.unknown"
    )
    invalid_rds["digest"] = rds_digest(invalid_rds)
    invalid_colocation = copy.deepcopy(valid_rds["two-cloud-azure-l3l5-gcp-l4-medium"])
    for visual_selection in invalid_colocation["component_selections"]:
        if visual_selection["logical_component_id"] == "component.visualization":
            visual_selection["provider"] = "gcp"
    invalid_colocation["digest"] = rds_digest(invalid_colocation)
    digest_tamper = copy.deepcopy(valid_rds["single-cloud-aws-small"])
    digest_tamper["currency"] = "EUR"
    invalid_rds_docs = {
        "unknown-component.json": (
            "RDS_V2_SELECTION_INCOMPLETE",
            invalid_rds,
        ),
        "l3-l5-not-colocated.json": (
            "PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED",
            invalid_colocation,
        ),
        "digest-tamper.json": ("RDS_V2_DIGEST_MISMATCH", digest_tamper),
    }
    for filename, (expected_error, specification) in invalid_rds_docs.items():
        write_json(
            RDS_V2 / "fixtures" / "invalid" / filename,
            {"expected_error": expected_error, "specification": specification},
        )

    manifest = {
        "manifest_version": "five-layer-v2-architecture-definitions.v1",
        "activation_status": "active",
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
            for provider, document in provider_profiles.items()
        ],
        "catalog_ref": {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
        },
        "service_decision_ref": {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": service_decision_digest(),
        },
        "workload_ref": {
            "id": "five-layer-workload",
            "version": "2",
            "digest": workload_contract_digest(),
        },
        "supported_placements": [
            f"{base}-l3l5-{twin}-l4" for base, twin in VALID_PLACEMENTS
        ],
    }
    manifest["content_digest"] = digest(manifest)
    write_json(DEFINITIONS / "five-layer-v2-manifest.json", manifest)
    (ARCH_V2 / "README.md").write_text(
        "# Architecture Profile Contracts v2\n\n"
        "Additive Five-layer v2 schemas and strict fixtures. Historical v1 bytes "
        "remain unchanged. Profiles, provider profiles, and the component catalog "
        "remain draft until the reviewed activation gates pass. Resolved-architecture "
        "fixtures cover representative Single-, Two-, and Three-Cloud shapes, use "
        "`offline_contract_fixture`, and carry zero cost values: they verify shape, "
        "ownership, and topology only and are not Optimizer pricing output. "
        "Generated by `scripts/sync_five_layer_v2_contracts.py`.\n",
        encoding="utf-8",
    )
    (RDS_V2 / "README.md").write_text(
        "# ResolvedDeploymentSpecification v2\n\n"
        "Generic component selections, typed dimensions, bindings, and immutable "
        "Five-layer v2 evidence references. Generated fixtures remain "
        "`offline_contract_fixture`, cover representative Single-, Two-, and "
        "Three-Cloud shapes, and list every blocking activation/live-capacity gate. "
        "The exhaustive placement/size matrix remains generated test evidence rather "
        "than duplicated fixture data. Azure Large offline evaluation uses the "
        "storage/operation-driven autoscale maximum as an explicit cost proxy; "
        "deployment still requires the supervised request-charge and autoscale "
        "capacity evidence gates. Generated; do not edit by hand.\n",
        encoding="utf-8",
    )


def load_v2_bundle() -> tuple[
    ModuleType,
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, Any],
    dict[str, dict[str, list[str]]],
]:
    runtime = load_v2_runtime()
    profile = read_json(
        DEFINITIONS / "profiles" / "five-layer-baseline" / "2" / "profile.json"
    )
    catalog = read_json(
        DEFINITIONS / "component-catalogs" / "complete-service" / "1" / "catalog.json"
    )
    provider_profiles = {
        provider: read_json(
            DEFINITIONS
            / "provider-implementations"
            / "five-layer-baseline"
            / "2"
            / provider
            / "1.json"
        )
        for provider in PROVIDERS
    }
    registry = read_json(ARCH_V2 / "semantic-registry.json")
    groups = service_groups()
    return runtime, profile, catalog, provider_profiles, registry, groups


def validate_source() -> None:
    runtime, profile, catalog, provider_profiles, registry, groups = load_v2_bundle()
    for name in SCHEMA_NAMES:
        Draft202012Validator.check_schema(read_json(ARCH_V2 / name))
    architecture_documents = [
        registry,
        profile,
        *provider_profiles.values(),
        catalog,
        *[
            read_json(path)
            for path in sorted((ARCH_V2 / "fixtures" / "valid").glob("*-resolved.json"))
        ],
    ]
    runtime.validate_bundle(architecture_documents, bundle_root=ARCH_V2)
    invalid_architecture = sorted((ARCH_V2 / "fixtures" / "invalid").glob("*.json"))
    if {path.name for path in invalid_architecture} != {
        "cross-version-rds.json",
        "l3-l5-not-colocated.json",
    }:
        raise RuntimeError("Architecture v2 negative fixture set drifted")
    for path in invalid_architecture:
        wrapper = read_json(path)
        try:
            runtime.validate_document(
                wrapper["document"],
                bundle_root=ARCH_V2,
                linked_documents=architecture_documents,
            )
        except runtime.ContractError as exc:
            if exc.code != wrapper["expected_error"]:
                raise RuntimeError(
                    f"{path.name} expected {wrapper['expected_error']}, got {exc.code}"
                ) from exc
        else:
            raise RuntimeError(f"Invalid architecture fixture passed: {path.name}")

    schema = read_json(RDS_V2 / "schema.json")
    Draft202012Validator.check_schema(schema)
    component_registry = read_json(RDS_V2 / "component-capacity-registry.json")
    if component_registry != component_capacity_registry():
        raise RuntimeError("RDS v2 component capacity registry drifted")
    supplied_registry_digest = component_registry["content_digest"]
    component_registry["content_digest"] = ""
    if supplied_registry_digest != digest(component_registry):
        raise RuntimeError("RDS v2 component capacity registry digest drifted")
    valid_paths = sorted((RDS_V2 / "fixtures" / "valid").glob("*.json"))
    if {path.stem for path in valid_paths} != {
        "single-cloud-aws-small",
        "two-cloud-azure-l3l5-gcp-l4-medium",
        "three-cloud-mixed-large",
    }:
        raise RuntimeError("RDS v2 representative fixture set drifted")
    for path in valid_paths:
        validate_rds(read_json(path), schema, profile, catalog)
    invalid_paths = sorted((RDS_V2 / "fixtures" / "invalid").glob("*.json"))
    if {path.name for path in invalid_paths} != {
        "digest-tamper.json",
        "l3-l5-not-colocated.json",
        "unknown-component.json",
    }:
        raise RuntimeError("RDS v2 negative fixture set drifted")
    for path in invalid_paths:
        wrapper = read_json(path)
        try:
            validate_rds(wrapper["specification"], schema, profile, catalog)
        except ContractError as exc:
            if exc.code != wrapper["expected_error"]:
                raise RuntimeError(
                    f"{path.name} expected {wrapper['expected_error']}, got {exc.code}"
                ) from exc
        else:
            raise RuntimeError(f"Invalid RDS fixture passed: {path.name}")

    manifest = read_json(DEFINITIONS / "five-layer-v2-manifest.json")
    supplied = manifest.pop("content_digest")
    if supplied != digest(manifest):
        raise RuntimeError("Five-layer v2 definition manifest digest drifted")
    expected_manifest = {
        "manifest_version": "five-layer-v2-architecture-definitions.v1",
        "activation_status": "active",
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
            for provider, document in provider_profiles.items()
        ],
        "catalog_ref": {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
        },
        "service_decision_ref": {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": service_decision_digest(),
        },
        "workload_ref": {
            "id": "five-layer-workload",
            "version": "2",
            "digest": workload_contract_digest(),
        },
        "supported_placements": [
            f"{base}-l3l5-{twin}-l4" for base, twin in VALID_PLACEMENTS
        ],
    }
    if manifest != expected_manifest:
        raise RuntimeError("Five-layer v2 definition manifest content drifted")


def copy_tree(
    source: Path,
    targets: tuple[Path, ...],
    *,
    marker: str | None = None,
) -> None:
    marker = marker or tree_digest(source)
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (target / ".contract-sha256").write_text(marker + "\n", encoding="utf-8")


def synchronize() -> None:
    copy_tree(ARCH_ROOT, ARCH_TARGETS)
    copy_tree(RDS_ROOT, RDS_TARGETS)
    copy_tree(
        DEPLOYMENT_MANIFEST_ROOT,
        DEPLOYMENT_MANIFEST_TARGETS,
        marker=deployment_manifest_tree_digest(DEPLOYMENT_MANIFEST_ROOT),
    )
    FLUTTER_DEMO_ROOT.mkdir(parents=True, exist_ok=True)
    for target_name, source in FLUTTER_DEMO_CONTRACTS.items():
        shutil.copy2(source, FLUTTER_DEMO_ROOT / target_name)


def check_tree(
    source: Path,
    targets: tuple[Path, ...],
    *,
    marker: str | None = None,
) -> None:
    expected = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
        and path.name != ".contract-sha256"
        and "__pycache__" not in path.parts
    }
    marker = marker or tree_digest(source)
    for target in targets:
        actual = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
            and path.name != ".contract-sha256"
            and "__pycache__" not in path.parts
        }
        if actual != expected:
            raise RuntimeError(f"Generated contract copy drifted: {target}")
        marker_path = target / ".contract-sha256"
        if not marker_path.exists() or marker_path.read_text().strip() != marker:
            raise RuntimeError(f"Generated contract marker drifted: {target}")


def check() -> None:
    validate_source()
    check_tree(ARCH_ROOT, ARCH_TARGETS)
    check_tree(RDS_ROOT, RDS_TARGETS)
    check_tree(
        DEPLOYMENT_MANIFEST_ROOT,
        DEPLOYMENT_MANIFEST_TARGETS,
        marker=deployment_manifest_tree_digest(DEPLOYMENT_MANIFEST_ROOT),
    )
    for target_name, source in FLUTTER_DEMO_CONTRACTS.items():
        target = FLUTTER_DEMO_ROOT / target_name
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"Generated Flutter demo contract drifted: {target}")


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
    except (ContractError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "five-layer-v2-contracts: OK "
        f"(architecture={tree_digest(ARCH_ROOT)}, rds={tree_digest(RDS_ROOT)}, "
        f"deployment-manifest={tree_digest(DEPLOYMENT_MANIFEST_ROOT)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
