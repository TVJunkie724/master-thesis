"""Standalone Six-layer deployment graph compiler tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from src.architecture_profiles.graph_evidence import graph_evidence
from src.architecture_profiles.graph_resolver import (
    _topological_order,
    resolve_deployment_graph,
)
from src.deployment_specification import (
    ValidatedDeploymentManifest,
    validate_deployment_manifest,
    validate_resolved_deployment_specification,
)
from src.deployment_specification.errors import DeploymentSpecificationError
from src.deployment_specification.validator import (
    calculate_digest as calculate_specification_digest,
)
from src.providers.terraform.package_builder import (
    _aws_six_layer_storage_mover_selected,
)
from src.terraform_inputs import translate_graph_inputs


MANIFEST_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest"
    / "v4"
    / "fixtures"
    / "valid"
)
FIXTURE = "six-layer-aws-azure-eventing-small.json"
LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}


def _manifest() -> dict:
    return json.loads((MANIFEST_ROOT / FIXTURE).read_text("utf-8"))


def _resolve_offline(manifest: dict | None = None):
    """Compile canonical offline evidence without weakening deployment readiness."""

    manifest = deepcopy(manifest or _manifest())
    specification = validate_resolved_deployment_specification(
        manifest["resolved_deployment_specification"]
    )
    provider_by_slot = {
        LOGICAL_TO_SLOT[item["logical_component_id"]]: item["provider"]
        for item in manifest["resolved_twin_architecture"]["component_assignments"]
        if item["logical_component_id"] in LOGICAL_TO_SLOT
    }
    validated = ValidatedDeploymentManifest(
        manifest=MappingProxyType(manifest),
        specification=specification,
        provider_by_slot=MappingProxyType(provider_by_slot),
        manifest_version="4.0",
        architecture=MappingProxyType(manifest["resolved_twin_architecture"]),
    )
    return resolve_deployment_graph(validated)


def test_six_layer_graph_is_complete_deterministic_and_secret_free():
    first = _resolve_offline()
    second = _resolve_offline()

    assert first.to_contract() == second.to_contract()
    assert first.content_digest == second.content_digest
    assert len(first.nodes) == 8
    assert len(first.edges) == 9
    assert [stage.stage_id for stage in first.stages] == [
        "package",
        "preplan",
        "terraform",
        "postapply",
    ]
    assert all(node.package_artifacts for node in first.nodes)
    assert "secret" not in json.dumps(first.to_contract(), sort_keys=True).lower()
    evidence = graph_evidence(first)
    assert evidence["node_count"] == 8
    assert evidence["package_selection_digest"].startswith("sha256:")


def test_offline_six_layer_fixture_is_not_executable():
    manifest = _manifest()

    with pytest.raises(DeploymentSpecificationError) as raised:
        validate_deployment_manifest(manifest, manifest["providers"])

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_NOT_READY"


def test_six_layer_rds_without_eventing_selection_fails_closed():
    specification = _manifest()["resolved_deployment_specification"]
    removed_selection_ids = {
        item["selection_id"]
        for item in specification["component_selections"]
        if item["logical_component_id"] == "component.eventing"
    }
    specification["component_selections"] = [
        item
        for item in specification["component_selections"]
        if item["selection_id"] not in removed_selection_ids
    ]
    specification["bindings"] = [
        item
        for item in specification["bindings"]
        if item["destination_selection_id"] not in removed_selection_ids
    ]
    specification["digest"] = calculate_specification_digest(specification)

    with pytest.raises(DeploymentSpecificationError) as raised:
        validate_resolved_deployment_specification(specification)

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"


def test_six_layer_graph_translates_only_declared_terraform_symbols():
    graph = _resolve_offline()
    inputs = translate_graph_inputs(graph)

    assert inputs.graph_digest == graph.content_digest
    assert inputs.values["architecture_profile_id"] == "six-layer-eventing"
    assert inputs.values["architecture_profile_version"] == "1"
    assert inputs.values["layer_1_provider"] == "aws"
    assert inputs.values["layer_5_provider"] == "azure"
    assert _aws_six_layer_storage_mover_selected(graph) is False


def test_six_layer_graph_materializes_event_node_and_directed_bridges():
    graph = _resolve_offline()
    event_node = next(
        node
        for node in graph.nodes
        if node.logical_component_id == "component.eventing"
    )
    event_edges = [edge for edge in graph.edges if "eventing" in edge.logical_edge_id]

    assert graph.profile_ref["id"] == "six-layer-eventing"
    assert graph.profile_ref["version"] == "1"
    assert graph.profile_ref["digest"].startswith("sha256:")
    assert event_node.provider == "azure"
    assert event_node.deployment_component_id == "deployment.azure.eventing.v1"
    assert {edge.logical_edge_id for edge in event_edges} == {
        "edge.ingestion-to-eventing",
        "edge.eventing-to-processing",
        "edge.processing-to-eventing",
        "edge.eventing-to-ingestion",
        "edge.eventing-to-hot-storage",
    }
    assert {edge.logical_edge_id: edge.mechanism for edge in event_edges} == {
        "edge.ingestion-to-eventing": "cross_provider_adapter",
        "edge.eventing-to-processing": "provider_native_trigger",
        "edge.processing-to-eventing": "provider_native_trigger",
        "edge.eventing-to-ingestion": "cross_provider_adapter",
        "edge.eventing-to-hot-storage": "provider_native_trigger",
    }


def test_topological_order_collapses_only_allowlisted_feedback_cycle():
    nodes = (
        SimpleNamespace(
            node_id="node.ingestion",
            logical_component_id="component.ingestion",
        ),
        SimpleNamespace(
            node_id="node.processing",
            logical_component_id="component.processing",
        ),
        SimpleNamespace(
            node_id="node.storage",
            logical_component_id="component.hot-storage",
        ),
    )
    edges = (
        SimpleNamespace(
            source_node_id="node.ingestion",
            destination_node_id="node.processing",
        ),
        SimpleNamespace(
            source_node_id="node.processing",
            destination_node_id="node.ingestion",
        ),
        SimpleNamespace(
            source_node_id="node.processing",
            destination_node_id="node.storage",
        ),
    )

    assert _topological_order(
        nodes,
        edges,
        allowed_cycle_ids=frozenset({"cycle.ingestion.processing"}),
    ) == ("node.ingestion", "node.processing", "node.storage")

    with pytest.raises(DeploymentSpecificationError) as rejected:
        _topological_order(nodes, edges)
    assert rejected.value.code == "DEPLOYMENT_GRAPH_CYCLE_FORBIDDEN"
