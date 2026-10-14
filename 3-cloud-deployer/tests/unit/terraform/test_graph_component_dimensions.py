"""Resolved graph dimension projection tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tfvars_generator import (
    ConfigurationError,
    _project_graph_component_dimensions,
)


def _graph(*dimensions):
    return SimpleNamespace(
        nodes=tuple(
            SimpleNamespace(deployment_dimensions=tuple(items)) for items in dimensions
        )
    )


def test_projects_sorted_scalar_dimensions_and_deduplicates_shared_components():
    shared = {
        "dimension_id": "dimension.azure.event-hubs.throughput_unit_hours",
        "value": 8030,
    }
    graph = _graph(
        (shared, {"dimension_id": "dimension.azure.flex.enabled", "value": True}),
        (shared,),
    )

    assert _project_graph_component_dimensions(graph) == {
        "dimension.azure.event-hubs.throughput_unit_hours": "8030",
        "dimension.azure.flex.enabled": "true",
    }


def test_rejects_conflicting_duplicate_dimension_values():
    graph = _graph(
        ({"dimension_id": "dimension.shared", "value": 1},),
        ({"dimension_id": "dimension.shared", "value": 2},),
    )

    with pytest.raises(ConfigurationError, match="contradict"):
        _project_graph_component_dimensions(graph)


def test_leaves_component_scoped_historical_dimensions_on_existing_bindings():
    graph = _graph(
        ({"dimension_id": "azure.blob.tier", "value": "Archive"},),
        ({"dimension_id": "azure.blob.tier", "value": "Cool"},),
    )

    assert _project_graph_component_dimensions(graph) == {}
