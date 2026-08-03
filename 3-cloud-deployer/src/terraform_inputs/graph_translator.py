"""Translate only catalog-owned graph bindings to Terraform inputs."""

from __future__ import annotations

import re
from pathlib import Path

from src.architecture_profiles import ResolvedDeploymentGraph
from src.deployment_specification.errors import DeploymentSpecificationError

from .compatibility_projection import provider_projection
from .models import TerraformInputSet, TerraformScalar


VARIABLE_PATTERN = re.compile(r'variable\s+"([a-zA-Z0-9_]+)"')
OUTPUT_PATTERN = re.compile(r'output\s+"([a-zA-Z0-9_]+)"')
RESOURCE_PATTERN = re.compile(r'resource\s+"([a-zA-Z0-9_]+)"\s+"([a-zA-Z0-9_]+)"')


def translate_graph_inputs(
    graph: ResolvedDeploymentGraph,
    *,
    terraform_root: Path | None = None,
) -> TerraformInputSet:
    values: dict[str, TerraformScalar] = {}
    input_by_destination = {
        (node.node_id, str(item["input_id"])): item
        for node in graph.nodes
        for item in node.terraform["input_bindings"]
    }
    if len(input_by_destination) != sum(
        len(node.terraform["input_bindings"]) for node in graph.nodes
    ):
        raise DeploymentSpecificationError(
            "DEPLOYMENT_GRAPH_BINDING_DUPLICATE",
            "graph.nodes.terraform.input_bindings",
            "Graph Terraform input ownership is duplicated",
        )
    for node in graph.nodes:
        declared_ids = {
            str(item["input_id"]) for item in node.terraform["input_bindings"]
        }
        if declared_ids != set(node.terraform["allowed_input_variable_ids"]):
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"nodes.{node.node_id}.terraform.input_bindings",
                "Terraform input declarations differ from their allowlist",
            )
    for binding in graph.bindings:
        if binding.binding_kind != "deployment_dimension":
            continue
        declaration = input_by_destination.get(
            (binding.destination_node_id, binding.destination_input_id)
        )
        if declaration is None or binding.value is None:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"bindings.{binding.binding_id}",
                "Graph dimension does not resolve to one catalog variable",
            )
        variable = str(declaration["terraform_variable"])
        if not isinstance(binding.value, (str, int, bool)):
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"bindings.{binding.binding_id}",
                "Graph dimension has an unsupported Terraform type",
            )
        expected_type = (
            "boolean"
            if isinstance(binding.value, bool)
            else "integer"
            if isinstance(binding.value, int)
            else "string"
        )
        if binding.value_type != expected_type or (
            binding.sensitivity == "secret"
        ) != bool(declaration.get("sensitive")):
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"bindings.{binding.binding_id}",
                "Graph dimension type or sensitivity differs from its catalog input",
            )
        previous = values.setdefault(variable, binding.value)
        if previous != binding.value:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_GRAPH_BINDING_DUPLICATE",
                f"bindings.{binding.binding_id}",
                "Terraform variable has contradictory graph bindings",
            )
    values.update(provider_projection(graph))
    _verify_symbols(
        graph,
        values,
        terraform_root or Path(__file__).resolve().parents[1] / "terraform",
    )
    return TerraformInputSet.create(
        values,
        graph_digest=graph.content_digest,
        specification_digest=graph.specification_ref["digest"],
    )


def _verify_symbols(
    graph: ResolvedDeploymentGraph,
    values: dict[str, TerraformScalar],
    terraform_root: Path,
) -> None:
    sources = [
        path.read_text(encoding="utf-8")
        for path in sorted(terraform_root.rglob("*.tf"))
    ]
    declared_variables = {
        match for source in sources for match in VARIABLE_PATTERN.findall(source)
    }
    declared_outputs = {
        match for source in sources for match in OUTPUT_PATTERN.findall(source)
    }
    declared_resources = {
        f"{resource_type}.{resource_name}"
        for source in sources
        for resource_type, resource_name in RESOURCE_PATTERN.findall(source)
    }
    unknown_variables = sorted(set(values) - declared_variables)
    if unknown_variables:
        raise DeploymentSpecificationError(
            "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
            "terraform.variables",
            "Graph references an undeclared Terraform variable",
        )
    for node in graph.nodes:
        unknown_resources = (
            set(node.terraform["resource_addresses"]) - declared_resources
        )
        if unknown_resources:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"nodes.{node.node_id}.terraform.resource_addresses",
                "Graph references an undeclared Terraform resource",
            )
        for output in node.terraform["outputs"]:
            if output["terraform_output"] not in declared_outputs:
                raise DeploymentSpecificationError(
                    "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                    f"nodes.{node.node_id}.terraform.outputs",
                    "Graph references an undeclared Terraform output",
                )
    output_ids_by_node = {
        node.node_id: {str(item["output_id"]) for item in node.terraform["outputs"]}
        for node in graph.nodes
    }
    for edge in graph.edges:
        source_output_id = str(edge.terraform["source_output_id"])
        if source_output_id not in output_ids_by_node[edge.source_node_id]:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"edges.{edge.graph_edge_id}.terraform.source_output_id",
                "Graph edge source output is not declared by its source node",
            )
        destination_node = next(
            node for node in graph.nodes if node.node_id == edge.destination_node_id
        )
        if str(edge.terraform["destination_input_id"]) not in {
            str(item["port_id"]) for item in destination_node.input_ports
        }:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"edges.{edge.graph_edge_id}.terraform.destination_input_id",
                "Graph edge destination input is not declared by its destination node",
            )
