"""Request-scoped preparation of shared cross-cloud identity capabilities.

The AWS outbound identity feature is account-wide and therefore deliberately
not owned by an individual Twin's Terraform state.  A confirmed deployment may
enable it idempotently when the resolved graph contains an AWS-to-remote edge;
Twin destruction must never disable it.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.architecture_profiles import ResolvedDeploymentGraph
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

_CROSS_PROVIDER_ROUTE_CLASS = "cross_provider"
_WORKLOAD_IDENTITY_TRUST_ID = "trust.workload-identity-federation"
_SUPPORTED_AWS_OUTBOUND_DESTINATIONS = frozenset({"azure"})


@dataclass(frozen=True, slots=True)
class AwsOutboundIdentityReadiness:
    """Non-secret result passed from the SDK preplan stage to Terraform."""

    required: bool
    destination_providers: tuple[str, ...] = ()
    issuer_identifier: str = ""
    enabled_during_operation: bool = False

    def to_tfvars(self) -> dict[str, Any]:
        return {
            "aws_outbound_identity_required": self.required,
            "aws_outbound_identity_destinations": list(self.destination_providers),
            "aws_outbound_identity_issuer": self.issuer_identifier,
        }


def aws_outbound_identity_destinations(
    graph: "ResolvedDeploymentGraph | None",
) -> tuple[str, ...]:
    """Return remote providers reached by workload-identity AWS edges."""

    if graph is None:
        return ()

    providers_by_node = {node.node_id: node.provider for node in graph.nodes}
    destinations = {
        providers_by_node.get(edge.destination_node_id, "")
        for edge in graph.edges
        if providers_by_node.get(edge.source_node_id) == "aws"
        and edge.transfer_route_class == _CROSS_PROVIDER_ROUTE_CLASS
        and edge.trust_ref.get("id") == _WORKLOAD_IDENTITY_TRUST_ID
    }
    return tuple(sorted(destinations & _SUPPORTED_AWS_OUTBOUND_DESTINATIONS))


def ensure_aws_outbound_identity(
    context: "DeploymentContext",
    graph: "ResolvedDeploymentGraph | None",
) -> AwsOutboundIdentityReadiness:
    """Enable AWS outbound identity only for a confirmed remote AWS route.

    ``GetOutboundWebIdentityFederationInfo`` is used as the idempotency check.
    The account-wide enable operation is intentionally absent from every
    destruction path.
    """

    destinations = aws_outbound_identity_destinations(graph)
    if not destinations:
        return AwsOutboundIdentityReadiness(required=False)

    provider = context.providers.get("aws")
    if provider is None:
        raise ValueError(
            "AWS outbound identity is required by the deployment graph, but "
            "the AWS provider is not initialized"
        )
    iam_client = provider.clients.get("iam")
    if iam_client is None:
        raise ValueError(
            "AWS outbound identity is required by the deployment graph, but "
            "the IAM client is not initialized"
        )

    enabled_during_operation = False
    try:
        info = iam_client.get_outbound_web_identity_federation_info()
    except Exception as exc:
        if _aws_error_code(exc) != "FeatureDisabledException":
            raise
        info = {"JwtVendingEnabled": False}

    if not info.get("JwtVendingEnabled", False):
        logger.warning(
            "Enabling account-wide AWS outbound identity federation for "
            "resolved destination providers %s; Twin destroy will preserve it",
            ", ".join(destinations),
        )
        try:
            enabled = iam_client.enable_outbound_web_identity_federation()
            enabled_during_operation = True
        except Exception as exc:
            if _aws_error_code(exc) != "FeatureEnabledException":
                raise
            enabled = {}
        info = iam_client.get_outbound_web_identity_federation_info()
        if not info.get("IssuerIdentifier") and enabled.get("IssuerIdentifier"):
            info["IssuerIdentifier"] = enabled["IssuerIdentifier"]

    issuer = str(info.get("IssuerIdentifier", "")).strip()
    if not info.get("JwtVendingEnabled", False) or not issuer:
        raise RuntimeError(
            "AWS outbound identity enablement did not return a ready issuer"
        )

    return AwsOutboundIdentityReadiness(
        required=True,
        destination_providers=destinations,
        issuer_identifier=issuer,
        enabled_during_operation=enabled_during_operation,
    )


def _aws_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", {})
    if not isinstance(response, dict):
        return ""
    error = response.get("Error", {})
    return str(error.get("Code", "")) if isinstance(error, dict) else ""


__all__ = [
    "AwsOutboundIdentityReadiness",
    "aws_outbound_identity_destinations",
    "ensure_aws_outbound_identity",
]
