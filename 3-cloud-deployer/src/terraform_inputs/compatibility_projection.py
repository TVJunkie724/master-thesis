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
    "component.eventing": "event_layer_provider",
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
                "Graph contains duplicate architecture provider ownership",
            )
        values[key] = "google" if node.provider == "gcp" else node.provider
    expected_keys = {
        key
        for logical_component_id, key in KEY_BY_COMPONENT.items()
        if logical_component_id != "component.eventing"
        or graph.profile_ref.get("id") == "six-layer-eventing"
    }
    if set(values) != expected_keys:
        raise DeploymentSpecificationError(
            "DEPLOYMENT_TERRAFORM_BINDING_INVALID",
            "nodes",
            "Graph provider projection is incomplete",
        )
    return values
