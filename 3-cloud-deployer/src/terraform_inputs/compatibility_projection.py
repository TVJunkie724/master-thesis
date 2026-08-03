"""Baseline provider projection derived only from resolved graph nodes."""

from __future__ import annotations

from src.architecture_profiles import ResolvedDeploymentGraph
from src.deployment_specification.errors import DeploymentSpecificationError


KEY_BY_COMPONENT = {
    "component.ingestion": "layer_1_provider",
    "component.processing": "layer_2_provider",
    "component.hot-storage": "layer_3_hot_provider",
    "component.cool-storage": "layer_3_cold_provider",
    "component.archive-storage": "layer_3_archive_provider",
    "component.twin-state": "layer_4_provider",
    "component.visualization": "layer_5_provider",
}


def provider_projection(graph: ResolvedDeploymentGraph) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in graph.nodes:
        if node.node_role != "architecture_component":
            continue
        key = KEY_BY_COMPONENT.get(node.logical_component_id)
        if key is None:
            continue
        if key in values:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
                f"nodes.{node.node_id}",
                "Graph contains duplicate baseline provider ownership",
            )
        values[key] = "google" if node.provider == "gcp" else node.provider
    if set(values) != set(KEY_BY_COMPONENT.values()):
        raise DeploymentSpecificationError(
            "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
            "nodes",
            "Graph provider projection is incomplete",
        )
    return values
