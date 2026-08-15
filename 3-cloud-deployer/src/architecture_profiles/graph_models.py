"""Immutable typed models for the resolved deployment graph."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def frozen_value(value: Any) -> Any:
    """Deep-freeze registry data before it enters an immutable graph."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): frozen_value(item) for key, item in value.items()}
        )
    if isinstance(value, (tuple, list)):
        return tuple(frozen_value(item) for item in value)
    return value


def frozen_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return frozen_value(value)


def plain_value(value: Any) -> Any:
    """Return a JSON-compatible deep projection of frozen registry values."""

    if isinstance(value, Mapping):
        return {str(key): plain_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class GraphBinding:
    binding_id: str
    binding_kind: str
    source_id: str
    destination_node_id: str
    destination_input_id: str
    value_type: str
    sensitivity: str
    resolution_stage: str
    validator_id: str
    transformer_id: str
    compatibility_version: str
    value: Any = None

    def to_contract(self) -> dict[str, Any]:
        contract = {
            "binding_id": self.binding_id,
            "binding_kind": self.binding_kind,
            "source_id": self.source_id,
            "destination_node_id": self.destination_node_id,
            "destination_input_id": self.destination_input_id,
            "value_type": self.value_type,
            "sensitivity": self.sensitivity,
            "resolution_stage": self.resolution_stage,
            "validator_id": self.validator_id,
            "transformer_id": self.transformer_id,
            "compatibility_version": self.compatibility_version,
        }
        if self.value is not None and self.sensitivity != "secret":
            contract["value"] = self.value
        return contract


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_role: str
    assignment_id: str
    logical_component_id: str
    deployment_component_id: str
    deployment_component_version: str
    provider: str
    service_id: str
    region: str
    package_artifact: Mapping[str, Any]
    package_artifacts: tuple[Mapping[str, Any], ...]
    terraform: Mapping[str, Any]
    deployment_specification_component_ids: tuple[str, ...]
    deployment_dimensions: tuple[Mapping[str, Any], ...]
    input_ports: tuple[Mapping[str, Any], ...]
    output_ports: tuple[Mapping[str, Any], ...]
    extension_artifact_refs: tuple[Mapping[str, Any], ...]
    permission_refs: tuple[str, ...]
    configuration_ref: Mapping[str, Any]
    runtime_contract: Mapping[str, Any]
    error_ref: Mapping[str, Any]
    observability_ref: Mapping[str, Any]
    cleanup_ref: Mapping[str, Any]
    lifecycle_stage_ids: tuple[str, ...]

    def to_contract(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_role": self.node_role,
            "assignment_id": self.assignment_id,
            "logical_component_id": self.logical_component_id,
            "deployment_component_id": self.deployment_component_id,
            "deployment_component_version": self.deployment_component_version,
            "provider": self.provider,
            "service_id": self.service_id,
            "region": self.region,
            "package_artifact": plain_value(self.package_artifact),
            "package_artifacts": [plain_value(item) for item in self.package_artifacts],
            "terraform": plain_value(self.terraform),
            "deployment_specification_component_ids": list(
                self.deployment_specification_component_ids
            ),
            "deployment_dimensions": [
                plain_value(item) for item in self.deployment_dimensions
            ],
            "input_ports": [plain_value(item) for item in self.input_ports],
            "output_ports": [plain_value(item) for item in self.output_ports],
            "extension_artifact_refs": [
                plain_value(item) for item in self.extension_artifact_refs
            ],
            "permission_refs": list(self.permission_refs),
            "configuration_ref": plain_value(self.configuration_ref),
            "runtime_contract": plain_value(self.runtime_contract),
            "error_ref": plain_value(self.error_ref),
            "observability_ref": plain_value(self.observability_ref),
            "cleanup_ref": plain_value(self.cleanup_ref),
            "lifecycle_stage_ids": list(self.lifecycle_stage_ids),
        }


@dataclass(frozen=True, slots=True)
class GraphEdge:
    graph_edge_id: str
    resolved_edge_id: str
    logical_edge_id: str
    source_node_id: str
    source_port_id: str
    destination_node_id: str
    destination_port_id: str
    support_node_ids: tuple[str, ...]
    edge_implementation_id: str
    edge_implementation_version: str
    mechanism: str
    payload_ref: Mapping[str, Any]
    delivery_ref: Mapping[str, Any]
    trust_ref: Mapping[str, Any]
    transfer_route_class: str
    pricing_refs: tuple[str, ...]
    observability_ref: Mapping[str, Any]
    resolution_stage: str
    terraform: Mapping[str, Any]
    sensitivity: str

    def to_contract(self) -> dict[str, Any]:
        return {
            "graph_edge_id": self.graph_edge_id,
            "resolved_edge_id": self.resolved_edge_id,
            "logical_edge_id": self.logical_edge_id,
            "source_node_id": self.source_node_id,
            "source_port_id": self.source_port_id,
            "destination_node_id": self.destination_node_id,
            "destination_port_id": self.destination_port_id,
            "support_node_ids": list(self.support_node_ids),
            "edge_implementation_id": self.edge_implementation_id,
            "edge_implementation_version": self.edge_implementation_version,
            "mechanism": self.mechanism,
            "payload_ref": plain_value(self.payload_ref),
            "delivery_ref": plain_value(self.delivery_ref),
            "trust_ref": plain_value(self.trust_ref),
            "transfer_route_class": self.transfer_route_class,
            "pricing_refs": list(self.pricing_refs),
            "observability_ref": plain_value(self.observability_ref),
            "resolution_stage": self.resolution_stage,
            "terraform": plain_value(self.terraform),
            "sensitivity": self.sensitivity,
        }


@dataclass(frozen=True, slots=True)
class GraphStage:
    stage_id: str
    ordinal: int
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    binding_ids: tuple[str, ...]

    def to_contract(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "ordinal": self.ordinal,
            "node_ids": list(self.node_ids),
            "edge_ids": list(self.edge_ids),
            "binding_ids": list(self.binding_ids),
        }


@dataclass(frozen=True, slots=True)
class ResolvedDeploymentGraph:
    graph_schema_version: str
    graph_id: str
    calculation_run_id: str
    architecture_ref: Mapping[str, str]
    profile_ref: Mapping[str, str]
    catalog_ref: Mapping[str, str]
    specification_ref: Mapping[str, str]
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    bindings: tuple[GraphBinding, ...]
    stages: tuple[GraphStage, ...]
    compatibility: Mapping[str, str]
    content_digest: str

    def to_contract(self, *, include_digest: bool = True) -> dict[str, Any]:
        contract = {
            "graph_schema_version": self.graph_schema_version,
            "graph_id": self.graph_id,
            "calculation_run_id": self.calculation_run_id,
            "architecture_ref": plain_value(self.architecture_ref),
            "profile_ref": plain_value(self.profile_ref),
            "catalog_ref": plain_value(self.catalog_ref),
            "specification_ref": plain_value(self.specification_ref),
            "nodes": [node.to_contract() for node in self.nodes],
            "edges": [edge.to_contract() for edge in self.edges],
            "bindings": [binding.to_contract() for binding in self.bindings],
            "stages": [stage.to_contract() for stage in self.stages],
            "compatibility": plain_value(self.compatibility),
        }
        if include_digest:
            contract["content_digest"] = self.content_digest
        return contract
