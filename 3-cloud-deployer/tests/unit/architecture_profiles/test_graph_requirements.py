"""Contract tests for graph-derived deployment requirements."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from src.architecture_profiles.graph_resolver import resolve_deployment_graph
from src.architecture_profiles.requirements import (
    IDENTITY_EXCHANGE_BY_PAIR,
    resolve_graph_requirements,
)
from src.deployment_specification import (
    ValidatedDeploymentManifest,
    validate_resolved_deployment_specification,
)

MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest"
    / "v4"
    / "fixtures"
    / "valid"
    / "six-layer-aws-azure-eventing-small.json"
)
LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}


def _canonical_graph():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    specification = validate_resolved_deployment_specification(
        manifest["resolved_deployment_specification"]
    )
    provider_by_slot = {
        LOGICAL_TO_SLOT[item["logical_component_id"]]: item["provider"]
        for item in manifest["resolved_twin_architecture"]["component_assignments"]
        if item["logical_component_id"] in LOGICAL_TO_SLOT
    }
    validated = ValidatedDeploymentManifest(
        manifest=MappingProxyType(deepcopy(manifest)),
        specification=specification,
        provider_by_slot=MappingProxyType(provider_by_slot),
        manifest_version="4.0",
        architecture=MappingProxyType(manifest["resolved_twin_architecture"]),
    )
    return resolve_deployment_graph(validated)


def _node(
    node_id: str,
    provider: str,
    *,
    resource_types: tuple[str, ...] = (),
    logical_component_id: str = "component.eventing",
):
    return SimpleNamespace(
        node_id=node_id,
        node_role="architecture_component",
        provider=provider,
        region={"aws": "eu-central-1", "azure": "westeurope", "gcp": "europe-west1"}[
            provider
        ],
        logical_component_id=logical_component_id,
        service_id=f"{provider}.eventing.v1",
        terraform={
            "resource_addresses": tuple(
                f"{resource_type}.selected" for resource_type in resource_types
            )
        },
        permission_refs=(f"credential.{provider}.administrator",),
        observability_ref={"id": "observability.eventing", "version": "1"},
    )


def _edge(source: str, destination: str):
    return SimpleNamespace(
        graph_edge_id="graph.edge.eventing",
        logical_edge_id="edge.ingestion-to-eventing",
        source_node_id=source,
        destination_node_id=destination,
        transfer_route_class="cross_provider",
        observability_ref={"id": "observability.eventing", "version": "1"},
    )


def test_canonical_graph_embeds_deterministic_digest_bound_requirements():
    first = _canonical_graph()
    second = _canonical_graph()

    assert first.requirements == second.requirements
    assert first.requirements_digest == second.requirements_digest
    assert first.requirements_digest.startswith("sha256:")
    assert first.to_contract()["requirements_digest"] == first.requirements_digest
    assert {requirement.provider for requirement in first.requirements} == {
        "aws",
        "azure",
    }
    assert all(
        requirement.source_node_ids or requirement.source_edge_ids
        for requirement in first.requirements
    )


def test_eventing_node_owns_azure_requirements_instead_of_legacy_layer_keys():
    graph = _canonical_graph()
    event_node = next(
        node
        for node in graph.nodes
        if node.logical_component_id == "component.eventing"
    )
    owned = [
        requirement
        for requirement in graph.requirements
        if event_node.node_id in requirement.source_node_ids
    ]

    assert event_node.provider == "azure"
    assert owned
    assert {requirement.provider for requirement in owned} == {"azure"}
    assert any(
        requirement.capability_id == "Microsoft.EventHub" for requirement in owned
    )
    assert "layer_" not in json.dumps(
        [requirement.to_contract() for requirement in graph.requirements]
    )


@pytest.mark.parametrize(
    ("source", "destination", "exchange"),
    [(*pair, exchange) for pair, exchange in sorted(IDENTITY_EXCHANGE_BY_PAIR.items())],
)
def test_every_directed_provider_pair_derives_exact_workload_identity(
    source,
    destination,
    exchange,
):
    requirements = resolve_graph_requirements(
        (_node("source", source), _node("destination", destination)),
        (_edge("source", "destination"),),
    )

    identity = next(
        requirement
        for requirement in requirements
        if requirement.requirement_type == "workload_identity"
    )
    assert identity.provider == source
    assert identity.capability_id == exchange
    assert identity.source_edge_ids == ("graph.edge.eventing",)


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_provider_local_graph_has_no_remote_identity_requirement(provider):
    requirements = resolve_graph_requirements(
        (_node("source", provider), _node("destination", provider)),
        (),
    )

    assert not any(
        requirement.requirement_type == "workload_identity"
        for requirement in requirements
    )
    assert {
        requirement.provider
        for requirement in requirements
        if requirement.requirement_type == "provider_scope"
    } == {provider}


def test_gcp_apis_are_selected_from_exact_graph_resource_types():
    requirements = resolve_graph_requirements(
        (
            _node(
                "eventing",
                "gcp",
                resource_types=(
                    "google_cloud_run_v2_service",
                    "google_pubsub_topic",
                ),
            ),
        ),
        (),
    )
    apis = {
        requirement.capability_id
        for requirement in requirements
        if requirement.requirement_type == "api"
    }

    assert apis == {
        "cloudresourcemanager.googleapis.com",
        "logging.googleapis.com",
        "monitoring.googleapis.com",
        "pubsub.googleapis.com",
        "run.googleapis.com",
        "serviceusage.googleapis.com",
    }
    assert "container.googleapis.com" not in apis


@pytest.mark.parametrize("source", ["aws", "azure"])
def test_inbound_gcp_route_derives_token_exchange_apis(source):
    requirements = resolve_graph_requirements(
        (_node("source", source), _node("destination", "gcp")),
        (_edge("source", "destination"),),
    )

    inbound_apis = {
        requirement.capability_id: requirement
        for requirement in requirements
        if requirement.provider == "gcp"
        and requirement.requirement_type == "api"
        and requirement.capability_id
        in {"iamcredentials.googleapis.com", "sts.googleapis.com"}
    }

    assert set(inbound_apis) == {
        "iamcredentials.googleapis.com",
        "sts.googleapis.com",
    }
    assert all(
        requirement.source_edge_ids == ("graph.edge.eventing",)
        for requirement in inbound_apis.values()
    )


def test_aws_to_azure_adds_only_the_reviewed_shared_account_capability():
    requirements = resolve_graph_requirements(
        (_node("aws", "aws"), _node("azure", "azure")),
        (_edge("aws", "azure"),),
    )
    account_capabilities = [
        requirement
        for requirement in requirements
        if requirement.requirement_type == "account_capability"
    ]

    assert [item.capability_id for item in account_capabilities] == [
        "aws.outbound-identity-federation"
    ]
    assert account_capabilities[0].preparation_mode == "confirmed_account"
