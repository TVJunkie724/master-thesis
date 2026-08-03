"""Closed-world graph binding resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.deployment_specification.errors import DeploymentSpecificationError

from .graph_models import GraphBinding, GraphNode


def _error(code: str, field: str, message: str) -> DeploymentSpecificationError:
    return DeploymentSpecificationError(code, field, message)


def resolve_node_bindings(
    node: GraphNode,
    component: Mapping[str, Any],
    specification_components: Sequence[Mapping[str, Any]],
    extension_bindings: Sequence[Mapping[str, Any]],
) -> tuple[GraphBinding, ...]:
    """Resolve catalog configuration, dimensions, and extension artifacts."""

    bindings: list[GraphBinding] = [
        GraphBinding(
            binding_id=f"binding.configuration.{node.assignment_id}",
            binding_kind="platform_configuration",
            source_id=str(component["configuration_schema_ref"]["id"]),
            destination_node_id=node.node_id,
            destination_input_id="configuration",
            value_type="json_document",
            sensitivity="internal",
            resolution_stage="preplan",
            validator_id="validator.catalog-configuration.v1",
            transformer_id="transformer.identity.v1",
            compatibility_version="1",
        )
    ]
    input_bindings = {
        item["terraform_variable"]: item
        for item in component["terraform_binding"]["input_bindings"]
    }
    for specification_component in specification_components:
        for dimension in specification_component["dimensions"]:
            terraform_target = dimension.get("terraform_target")
            if terraform_target is None:
                continue
            declaration = input_bindings.get(terraform_target)
            if declaration is None:
                raise _error(
                    "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                    (
                        f"nodes.{node.node_id}.deployment_dimensions."
                        f"{dimension['dimension_id']}"
                    ),
                    "Deployment dimension is not allowlisted by its catalog owner",
                )
            value = dimension["value"]
            value_type = (
                "boolean"
                if isinstance(value, bool)
                else "integer"
                if isinstance(value, int)
                else "string"
            )
            bindings.append(
                GraphBinding(
                    binding_id=(
                        f"binding.dimension.{node.assignment_id}."
                        f"{dimension['dimension_id']}"
                    ),
                    binding_kind="deployment_dimension",
                    source_id=str(dimension["dimension_id"]),
                    destination_node_id=node.node_id,
                    destination_input_id=str(declaration["input_id"]),
                    value_type=value_type,
                    sensitivity=(
                        "secret" if declaration.get("sensitive") else "internal"
                    ),
                    resolution_stage="preplan",
                    validator_id="validator.deployment-dimension.v1",
                    transformer_id="transformer.terraform-value.v1",
                    compatibility_version="1",
                    value=value,
                )
            )

    allowed_slots = {
        (item["id"], item["version"]) for item in component["extension_slot_refs"]
    }
    for extension in extension_bindings:
        if extension.get("logical_component_id") != node.logical_component_id:
            continue
        slot = (extension.get("slot_id"), extension.get("slot_version"))
        if slot not in allowed_slots:
            raise _error(
                "DEPLOYMENT_GRAPH_BINDING_INCOMPATIBLE",
                f"nodes.{node.node_id}.extension_artifact_refs",
                "Extension artifact targets an undeclared catalog slot",
            )
        bindings.append(
            GraphBinding(
                binding_id=(
                    f"binding.extension.{node.assignment_id}.{extension['artifact_id']}"
                ),
                binding_kind="extension_artifact",
                source_id=str(extension["artifact_id"]),
                destination_node_id=node.node_id,
                destination_input_id=str(extension["slot_id"]),
                value_type="artifact_reference",
                sensitivity="internal",
                resolution_stage="package",
                validator_id="validator.extension-artifact.v1",
                transformer_id="transformer.identity.v1",
                compatibility_version=str(extension["validation_contract_version"]),
            )
        )
    return tuple(bindings)
