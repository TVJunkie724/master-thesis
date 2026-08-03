"""Deterministic deployment graph stage planning."""

from __future__ import annotations

from .graph_models import GraphBinding, GraphEdge, GraphNode, GraphStage


STAGES = ("package", "preplan", "terraform", "postapply")


def plan_stages(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    bindings: tuple[GraphBinding, ...],
    topological_node_ids: tuple[str, ...],
) -> tuple[GraphStage, ...]:
    edge_ids = tuple(edge.graph_edge_id for edge in edges)
    return (
        GraphStage(
            stage_id="package",
            ordinal=1,
            node_ids=tuple(node.node_id for node in nodes),
            edge_ids=(),
            binding_ids=tuple(
                binding.binding_id
                for binding in bindings
                if binding.resolution_stage == "package"
            ),
        ),
        GraphStage(
            stage_id="preplan",
            ordinal=2,
            node_ids=topological_node_ids,
            edge_ids=edge_ids,
            binding_ids=tuple(
                binding.binding_id
                for binding in bindings
                if binding.resolution_stage == "preplan"
            ),
        ),
        GraphStage(
            stage_id="terraform",
            ordinal=3,
            node_ids=topological_node_ids,
            edge_ids=edge_ids,
            binding_ids=tuple(
                binding.binding_id
                for binding in bindings
                if binding.resolution_stage == "terraform"
            ),
        ),
        GraphStage(
            stage_id="postapply",
            ordinal=4,
            node_ids=topological_node_ids,
            edge_ids=edge_ids,
            binding_ids=(),
        ),
    )
