"""Contract tests for request-scoped cross-cloud identity preparation."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.providers.terraform.cross_cloud_identity import (
    aws_outbound_identity_destinations,
    ensure_aws_outbound_identity,
)
from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy


class AwsApiError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def _node(node_id: str, provider: str):
    return SimpleNamespace(node_id=node_id, provider=provider)


def _edge(source: str, destination: str, *, route="cross_provider"):
    return SimpleNamespace(
        source_node_id=source,
        destination_node_id=destination,
        transfer_route_class=route,
        trust_ref={"id": "trust.workload-identity-federation"},
    )


def _graph(*, nodes, edges):
    return SimpleNamespace(nodes=tuple(nodes), edges=tuple(edges))


def _context(iam=None):
    providers = {}
    if iam is not None:
        providers["aws"] = SimpleNamespace(clients={"iam": iam})
    return SimpleNamespace(providers=providers)


def test_only_azure_outbound_destination_is_derived_from_graph():
    graph = _graph(
        nodes=[
            _node("aws-hot", "aws"),
            _node("azure-twin", "azure"),
            _node("gcp-cool", "gcp"),
            _node("aws-local", "aws"),
        ],
        edges=[
            _edge("aws-hot", "azure-twin"),
            _edge("aws-hot", "gcp-cool"),
            _edge("aws-hot", "aws-local", route="same_provider_same_region"),
        ],
    )

    assert aws_outbound_identity_destinations(graph) == ("azure",)


def test_aws_to_gcp_uses_gcp_wif_without_aws_outbound_enablement():
    graph = _graph(
        nodes=[_node("aws", "aws"), _node("gcp", "gcp")],
        edges=[_edge("aws", "gcp")],
    )

    assert aws_outbound_identity_destinations(graph) == ()
    assert ensure_aws_outbound_identity(_context(), graph).required is False


@pytest.mark.parametrize("graph", [None, _graph(nodes=[], edges=[])])
def test_no_remote_aws_route_is_a_noop(graph):
    readiness = ensure_aws_outbound_identity(_context(), graph)

    assert readiness.required is False
    assert readiness.to_tfvars() == {
        "aws_outbound_identity_required": False,
        "aws_outbound_identity_destinations": [],
        "aws_outbound_identity_issuer": "",
    }


def test_ready_account_feature_is_reused_without_mutation():
    iam = MagicMock()
    iam.get_outbound_web_identity_federation_info.return_value = {
        "JwtVendingEnabled": True,
        "IssuerIdentifier": "https://issuer.example.aws",
    }
    graph = _graph(
        nodes=[_node("aws", "aws"), _node("azure", "azure")],
        edges=[_edge("aws", "azure")],
    )

    readiness = ensure_aws_outbound_identity(_context(iam), graph)

    assert readiness.required is True
    assert readiness.enabled_during_operation is False
    assert readiness.issuer_identifier == "https://issuer.example.aws"
    iam.enable_outbound_web_identity_federation.assert_not_called()


def test_disabled_account_feature_is_enabled_once_and_rechecked():
    iam = MagicMock()
    iam.get_outbound_web_identity_federation_info.side_effect = [
        AwsApiError("FeatureDisabledException"),
        {
            "JwtVendingEnabled": True,
            "IssuerIdentifier": "https://issuer.example.aws",
        },
    ]
    iam.enable_outbound_web_identity_federation.return_value = {
        "IssuerIdentifier": "https://issuer.example.aws"
    }
    graph = _graph(
        nodes=[_node("aws", "aws"), _node("azure", "azure")],
        edges=[_edge("aws", "azure")],
    )

    readiness = ensure_aws_outbound_identity(_context(iam), graph)

    assert readiness.enabled_during_operation is True
    assert readiness.destination_providers == ("azure",)
    iam.enable_outbound_web_identity_federation.assert_called_once_with()
    assert iam.get_outbound_web_identity_federation_info.call_count == 2


def test_required_route_fails_closed_without_initialized_aws_provider():
    graph = _graph(
        nodes=[_node("aws", "aws"), _node("azure", "azure")],
        edges=[_edge("aws", "azure")],
    )

    with pytest.raises(ValueError, match="AWS provider is not initialized"):
        ensure_aws_outbound_identity(_context(), graph)


def test_incomplete_enablement_result_fails_closed():
    iam = MagicMock()
    iam.get_outbound_web_identity_federation_info.return_value = {
        "JwtVendingEnabled": False
    }
    iam.enable_outbound_web_identity_federation.return_value = {}
    graph = _graph(
        nodes=[_node("aws", "aws"), _node("azure", "azure")],
        edges=[_edge("aws", "azure")],
    )

    with pytest.raises(RuntimeError, match="did not return a ready issuer"):
        ensure_aws_outbound_identity(_context(iam), graph)


def test_preplan_identity_result_is_merged_into_generated_tfvars(tmp_path):
    terraform_dir = tmp_path / "terraform-source"
    terraform_dir.mkdir()
    project_path = tmp_path / "project"
    project_path.mkdir()
    strategy = TerraformDeployerStrategy(str(terraform_dir), str(project_path))
    strategy._preplan_tfvars = {
        "aws_outbound_identity_required": True,
        "aws_outbound_identity_destinations": ["azure"],
        "aws_outbound_identity_issuer": "https://issuer.example.aws",
    }

    def write_base(_project_path, tfvars_path):
        from pathlib import Path

        Path(tfvars_path).write_text('{"digital_twin_name":"factory"}')

    with patch(
        "src.providers.terraform.deployer_strategy.generate_tfvars",
        side_effect=write_base,
    ):
        strategy._generate_tfvars()

    generated = json.loads(strategy.tfvars_path.read_text())
    assert generated["digital_twin_name"] == "factory"
    assert generated["aws_outbound_identity_required"] is True
    assert generated["aws_outbound_identity_destinations"] == ["azure"]
    assert generated["aws_outbound_identity_issuer"] == ("https://issuer.example.aws")
