"""Tests for graph-owned directed cross-cloud route projection."""

from types import SimpleNamespace

import pytest

from src.providers.terraform.cross_cloud_routes import (
    IDENTITY_EXCHANGE_BY_PAIR,
    cross_cloud_route_tfvars,
    resolve_cross_cloud_routes,
)


def _node(node_id: str, provider: str):
    return SimpleNamespace(node_id=node_id, provider=provider)


def _edge(
    route_id: str,
    source: str,
    destination: str,
    *,
    logical_edge_id: str = "edge.processing-to-hot-storage",
    route_class: str = "cross_provider",
):
    return SimpleNamespace(
        graph_edge_id=route_id,
        logical_edge_id=logical_edge_id,
        source_node_id=source,
        destination_node_id=destination,
        transfer_route_class=route_class,
        payload_ref={"id": "canonical-domain-event.v1", "version": "1"},
        trust_ref={"id": "trust.workload-identity-federation", "version": "1"},
    )


@pytest.mark.parametrize(
    ("source", "destination", "exchange"),
    [(*pair, exchange) for pair, exchange in sorted(IDENTITY_EXCHANGE_BY_PAIR.items())],
)
def test_every_directed_provider_pair_has_one_exact_identity_exchange(
    source,
    destination,
    exchange,
):
    graph = SimpleNamespace(
        nodes=(
            _node("source", source),
            _node("destination", destination),
        ),
        edges=(_edge("route", "source", "destination"),),
    )

    route = resolve_cross_cloud_routes(graph)[0]

    assert route.source_provider == source
    assert route.destination_provider == destination
    assert route.identity_exchange == exchange
    assert route.execution_kind == "source_event_forwarder"


@pytest.mark.parametrize(
    "logical_edge_id",
    ["edge.hot-to-cool-storage", "edge.cool-to-archive-storage"],
)
def test_storage_routes_select_finite_source_owned_job(logical_edge_id):
    graph = SimpleNamespace(
        nodes=(_node("aws", "aws"), _node("azure", "azure")),
        edges=(
            _edge(
                "storage-route",
                "aws",
                "azure",
                logical_edge_id=logical_edge_id,
            ),
        ),
    )

    route = resolve_cross_cloud_routes(graph)[0]

    assert route.execution_kind == "finite_storage_job"


def test_single_cloud_edges_create_no_remote_route_or_egress_input():
    graph = SimpleNamespace(
        nodes=(_node("source", "aws"), _node("destination", "aws")),
        edges=(
            _edge(
                "local",
                "source",
                "destination",
                route_class="same_provider_same_region",
            ),
        ),
    )

    assert resolve_cross_cloud_routes(graph) == ()
    assert cross_cloud_route_tfvars(graph) == {"resolved_cross_cloud_routes": []}


def test_routes_are_deterministic_and_do_not_contain_credentials_or_endpoints():
    graph = SimpleNamespace(
        nodes=(
            _node("aws", "aws"),
            _node("azure", "azure"),
            _node("gcp", "gcp"),
        ),
        edges=(
            _edge("route-z", "aws", "gcp"),
            _edge("route-a", "azure", "aws"),
        ),
    )

    tfvars = cross_cloud_route_tfvars(graph)["resolved_cross_cloud_routes"]

    assert [route["route_id"] for route in tfvars] == ["route-a", "route-z"]
    forbidden_keys = {"credential", "secret", "endpoint", "token", "url"}
    assert all(forbidden_keys.isdisjoint(route) for route in tfvars)


def test_unknown_provider_pair_fails_closed():
    graph = SimpleNamespace(
        nodes=(_node("aws", "aws"), _node("other", "other")),
        edges=(_edge("route", "aws", "other"),),
    )

    with pytest.raises(ValueError, match="no approved directed identity exchange"):
        resolve_cross_cloud_routes(graph)
