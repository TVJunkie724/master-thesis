"""DeploymentManifest v3 and deterministic graph compiler tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from src.architecture_profiles.contracts import (
    calculate_digest,
    calculate_resolution_id,
)
from src.architecture_profiles.graph_evidence import graph_evidence
from src.architecture_profiles.graph_resolver import resolve_deployment_graph
from src.deployment_specification import (
    ValidatedDeploymentManifest,
    validate_deployment_manifest,
    validate_resolved_deployment_specification,
)
from src.deployment_specification.errors import DeploymentSpecificationError
from src.terraform_inputs import translate_graph_inputs


MANIFEST_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest"
    / "v3"
    / "fixtures"
    / "valid"
)
MANIFEST_V4_ROOT = MANIFEST_ROOT.parents[2] / "v4" / "fixtures" / "valid"
LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}


def _manifest(name: str = "all-aws.json") -> dict:
    return json.loads((MANIFEST_ROOT / name).read_text("utf-8"))


def _resolve(manifest: dict):
    validated = validate_deployment_manifest(
        manifest,
        manifest["providers"],
    )
    return resolve_deployment_graph(validated)


def _resolve_offline_v4(name: str):
    """Compile canonical offline evidence without weakening deployment readiness."""

    manifest = json.loads((MANIFEST_V4_ROOT / name).read_text("utf-8"))
    specification = validate_resolved_deployment_specification(
        manifest["resolved_deployment_specification"]
    )
    provider_by_slot = {
        LOGICAL_TO_SLOT[item["logical_component_id"]]: item["provider"]
        for item in manifest["resolved_twin_architecture"]["component_assignments"]
    }
    validated = ValidatedDeploymentManifest(
        manifest=MappingProxyType(manifest),
        specification=specification,
        provider_by_slot=MappingProxyType(provider_by_slot),
        manifest_version="4.0",
        architecture=MappingProxyType(manifest["resolved_twin_architecture"]),
    )
    return resolve_deployment_graph(validated)


@pytest.mark.parametrize(
    "fixture",
    ("all-aws.json", "all-azure.json", "mixed-providers.json"),
)
def test_baseline_graph_is_complete_deterministic_and_secret_free(fixture):
    manifest = _manifest(fixture)

    first = _resolve(manifest)
    second = _resolve(deepcopy(manifest))

    expected_node_count = 8 if fixture == "mixed-providers.json" else 7
    assert len(first.nodes) == expected_node_count
    assert len(first.edges) == 6
    assert [stage.stage_id for stage in first.stages] == [
        "package",
        "preplan",
        "terraform",
        "postapply",
    ]
    assert first.to_contract() == second.to_contract()
    assert first.content_digest == second.content_digest
    assert len(first.bindings) >= 13
    assert {binding.binding_kind for binding in first.bindings} <= {
        "deployment_dimension",
        "platform_configuration",
        "extension_artifact",
        "component_output",
    }
    serialized = json.dumps(first.to_contract(), sort_keys=True).lower()
    assert "client_secret" not in serialized
    evidence = graph_evidence(first)
    assert evidence["node_count"] == expected_node_count
    assert evidence["calculation_run_id"] == first.calculation_run_id
    assert evidence["package_selection_digest"].startswith("sha256:")
    assert all(node.package_artifacts for node in first.nodes)
    assert all(
        artifact["source_digest"].startswith("sha256:")
        for node in first.nodes
        for artifact in node.package_artifacts
    )


def test_mixed_graph_materializes_catalog_owned_edge_support():
    graph = _resolve(_manifest("mixed-providers.json"))

    support = [node for node in graph.nodes if node.node_role == "edge_support"]
    edge = next(
        item
        for item in graph.edges
        if item.logical_edge_id == "edge.ingestion-to-processing"
    )

    assert len(support) == 1
    assert support[0].deployment_component_id == ("deployment.azure.cross-cloud-glue")
    assert support[0].node_id in edge.support_node_ids
    assert {artifact["id"] for artifact in support[0].package_artifacts} >= {
        "artifact.azure.glue-ingestion",
        "artifact.azure.glue-hot-writer",
        "artifact.azure.glue-cold-writer",
        "artifact.azure.glue-archive-writer",
    }


def test_l4_to_l5_is_a_typed_catalog_edge():
    graph = _resolve(_manifest("all-aws.json"))

    edge = next(
        item
        for item in graph.edges
        if item.logical_edge_id == "edge.twin-state-to-visualization"
    )

    assert edge.mechanism == "typed_synchronous_api"
    assert edge.payload_ref["id"] == "twin-query-result.v1"
    assert edge.terraform["source_output_id"]
    assert edge.terraform["destination_input_id"]


def test_graph_terraform_inputs_are_allowlisted_and_symbol_checked():
    graph = _resolve(_manifest("all-azure.json"))

    inputs = translate_graph_inputs(graph)

    assert inputs.graph_digest == graph.content_digest
    assert inputs.values["layer_1_provider"] == "azure"
    assert inputs.values["layer_5_provider"] == "azure"
    assert inputs.values["architecture_profile_id"] == "five-layer-baseline"
    assert inputs.values["architecture_profile_version"] == "1"
    assert "azure_iot_hub_sku" in inputs.values
    assert "unknown_variable" not in inputs.values


def test_manifest_provider_projection_tamper_is_rejected():
    manifest = _manifest()
    manifest["providers"]["layer_2_provider"] = "azure"

    with pytest.raises(DeploymentSpecificationError) as raised:
        validate_deployment_manifest(manifest, manifest["providers"])

    assert raised.value.code == "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH"


def test_unknown_edge_fails_before_graph_materialization():
    manifest = _manifest()
    architecture = manifest["resolved_twin_architecture"]
    architecture["resolved_edges"][0]["edge_implementation_id"] = (
        "edge-implementation.unknown"
    )
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    architecture["content_digest"] = calculate_digest(architecture)
    manifest["resolved_twin_architecture_digest"] = architecture["content_digest"]

    with pytest.raises(DeploymentSpecificationError) as raised:
        _resolve(manifest)

    assert raised.value.code == "DEPLOYMENT_GRAPH_EDGE_UNRESOLVED"


def test_duplicate_destination_binding_fails_closed():
    manifest = _manifest()
    architecture = manifest["resolved_twin_architecture"]
    duplicate = deepcopy(architecture["resolved_edges"][0])
    duplicate["resolved_edge_id"] = "resolved.duplicate"
    architecture["resolved_edges"].append(duplicate)
    architecture["content_digest"] = calculate_digest(architecture)
    manifest["resolved_twin_architecture_digest"] = architecture["content_digest"]

    with pytest.raises(DeploymentSpecificationError) as raised:
        _resolve(manifest)

    assert raised.value.code == "DEPLOYMENT_GRAPH_BINDING_DUPLICATE"


def test_invalid_v3_never_falls_back_to_historical_v2():
    manifest = _manifest()
    del manifest["resolved_twin_architecture"]

    with pytest.raises(DeploymentSpecificationError) as raised:
        validate_deployment_manifest(manifest, manifest["providers"])

    assert raised.value.code == "DEPLOYMENT_MANIFEST_INVALID"


@pytest.mark.parametrize(
    "fixture",
    (
        "single-cloud-aws-small.json",
        "two-cloud-azure-l3l5-gcp-l4-medium.json",
        "three-cloud-mixed-large.json",
    ),
)
def test_v4_graph_compiles_every_representative_cloud_shape(fixture):
    graph = _resolve_offline_v4(fixture)

    assert len(graph.nodes) == 7
    assert len(graph.edges) == 6
    assert {node.node_role for node in graph.nodes} == {"architecture_component"}
    assert all(node.deployment_dimensions for node in graph.nodes)
    assert "edge.hot-storage-to-visualization" in {
        edge.logical_edge_id for edge in graph.edges
    }
    assert "edge.twin-state-to-visualization" not in {
        edge.logical_edge_id for edge in graph.edges
    }


def test_v4_offline_contract_fixture_is_not_executable():
    manifest = json.loads(
        (MANIFEST_V4_ROOT / "single-cloud-aws-small.json").read_text("utf-8")
    )

    with pytest.raises(DeploymentSpecificationError) as raised:
        validate_deployment_manifest(manifest, manifest["providers"])

    assert raised.value.code == "DEPLOYMENT_SPECIFICATION_NOT_READY"


def test_v4_single_cloud_aws_graph_translates_to_declared_terraform_symbols():
    graph = _resolve_offline_v4("single-cloud-aws-small.json")

    inputs = translate_graph_inputs(graph)

    assert inputs.graph_digest == graph.content_digest
    assert inputs.values["architecture_profile_id"] == "five-layer-baseline"
    assert inputs.values["architecture_profile_version"] == "2"
    assert inputs.values["layer_1_provider"] == "aws"
    assert inputs.values["layer_5_provider"] == "aws"
