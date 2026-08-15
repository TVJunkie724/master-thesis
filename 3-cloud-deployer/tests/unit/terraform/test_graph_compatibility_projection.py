from types import SimpleNamespace

import pytest

from src.deployment_specification.errors import DeploymentSpecificationError
from src.terraform_inputs.compatibility_projection import provider_projection


BASE_COMPONENTS = (
    ("component.ingestion", "aws"),
    ("component.processing", "azure"),
    ("component.hot-storage", "gcp"),
    ("component.cool-storage", "aws"),
    ("component.archive-storage", "azure"),
    ("component.twin-state", "gcp"),
    ("component.visualization", "aws"),
)


def _node(index, logical_component_id, provider):
    return SimpleNamespace(
        node_id=f"node.{index}",
        node_role="architecture_component",
        logical_component_id=logical_component_id,
        provider=provider,
    )


def _graph(*extra_nodes, profile_id="five-layer-baseline"):
    nodes = [
        _node(index, logical_component_id, provider)
        for index, (logical_component_id, provider) in enumerate(BASE_COMPONENTS)
    ]
    nodes.extend(extra_nodes)
    return SimpleNamespace(nodes=nodes, profile_ref={"id": profile_id})


def test_six_layer_projection_includes_independent_event_provider():
    graph = _graph(
        _node("event", "component.eventing", "azure"),
        profile_id="six-layer-eventing",
    )

    projection = provider_projection(graph)

    assert projection["layer_1_provider"] == "aws"
    assert projection["layer_3_hot_provider"] == "google"
    assert projection["layer_5_provider"] == "aws"
    assert projection["event_layer_provider"] == "azure"


def test_duplicate_baseline_ownership_still_fails_closed():
    graph = _graph(_node("duplicate", "component.ingestion", "azure"))

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        provider_projection(graph)

    assert exc_info.value.code == "DEPLOYMENT_TERRAFORM_BINDING_INVALID"
