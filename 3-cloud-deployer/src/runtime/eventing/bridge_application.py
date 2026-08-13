"""Compose graph-owned routes, short-lived identities, and SDK publishers."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .bridge_core import (
    BridgeContractError,
    BridgeRoute,
    RouteBlockingBridgeError,
    load_routes_json,
)
from .destination_identity import (
    AZURE_TOKEN_EXCHANGE_AUDIENCE,
    AwsAssumeRoleClientFactory,
    AwsOutboundAssertionSupplier,
    AwsRoleTarget,
    AzureFederatedTarget,
    AzureManagedIdentityAssertionSupplier,
    GcpFederatedTarget,
    GoogleIdTokenAssertionSupplier,
    build_azure_credential,
    build_gcp_credentials,
    load_identity_target,
)
from .destination_publishers import (
    GCP_PUBSUB_ENDPOINT,
    AwsDestination,
    AwsDestinationPublisher,
    AzureDestination,
    AzureDestinationPublisher,
    GcpDestination,
    GcpDestinationPublisher,
    load_destination,
)


def _mapping_json(raw: str, *, code: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BridgeContractError(code) from exc
    if not isinstance(value, dict):
        raise BridgeContractError(code)
    return value


def _azure_source_client_id(raw: Mapping[str, Any], *, required: bool) -> str:
    if not required:
        if raw:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        return ""
    if set(raw) != {"managed_identity_client_id"}:
        raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
    value = raw.get("managed_identity_client_id")
    if not isinstance(value, str) or not value:
        raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
    return value


def _gcp_publisher(credentials: object) -> object:
    from google.api_core.client_options import ClientOptions
    from google.cloud import pubsub_v1

    return pubsub_v1.PublisherClient(
        credentials=credentials,
        client_options=ClientOptions(api_endpoint=GCP_PUBSUB_ENDPOINT),
        publisher_options=pubsub_v1.types.PublisherOptions(
            enable_message_ordering=True
        ),
    )


def _publisher_for_destination(
    *,
    source_provider: str,
    destination_provider: str,
    destination_raw: object,
    identity_raw: object,
    azure_source_client_id: str,
) -> object:
    destination = load_destination(destination_raw, provider=destination_provider)
    target = load_identity_target(
        identity_raw,
        source_provider=source_provider,
        destination_provider=destination_provider,
    )
    if destination_provider == "aws":
        if not isinstance(destination, AwsDestination) or not isinstance(
            target, AwsRoleTarget
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if source_provider == "azure":
            assertion = AzureManagedIdentityAssertionSupplier(
                azure_source_client_id,
                target.assertion_audience,
            )
        elif source_provider == "gcp":
            assertion = GoogleIdTokenAssertionSupplier(target.assertion_audience)
        else:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        return AwsDestinationPublisher(
            destination,
            AwsAssumeRoleClientFactory(target, assertion),
        )
    if destination_provider == "azure":
        if not isinstance(destination, AzureDestination) or not isinstance(
            target, AzureFederatedTarget
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if source_provider == "aws":
            assertion = AwsOutboundAssertionSupplier(
                AZURE_TOKEN_EXCHANGE_AUDIENCE
            )
        elif source_provider == "gcp":
            assertion = GoogleIdTokenAssertionSupplier(
                AZURE_TOKEN_EXCHANGE_AUDIENCE
            )
        else:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        return AzureDestinationPublisher(
            destination,
            build_azure_credential(target, assertion),
        )
    if destination_provider == "gcp":
        if not isinstance(destination, GcpDestination) or not isinstance(
            target, GcpFederatedTarget
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        assertion = None
        if source_provider == "azure":
            assertion = AzureManagedIdentityAssertionSupplier(
                azure_source_client_id,
                target.source_assertion_audience,
            )
        elif source_provider != "aws":
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        credentials = build_gcp_credentials(
            target,
            source_provider=source_provider,
            assertion_supplier=assertion,
        )
        return GcpDestinationPublisher(destination, _gcp_publisher(credentials))
    raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")


class BridgeApplication:
    """One source-provider bridge with one publisher per remote provider."""

    def __init__(
        self,
        source_provider: str,
        routes: tuple[BridgeRoute, ...],
        publishers: Mapping[str, object],
    ) -> None:
        self.source_provider = source_provider
        self.routes = routes
        self._publishers = dict(publishers)

    def publish(self, route: BridgeRoute, event: Mapping[str, Any]) -> object:
        if route.source_provider != self.source_provider:
            raise RouteBlockingBridgeError("ROUTE_MISMATCH")
        publisher = self._publishers.get(route.destination_provider)
        if publisher is None:
            raise RouteBlockingBridgeError("ROUTE_NOT_CONFIGURED")
        publish = getattr(publisher, "publish", None)
        if not callable(publish):
            raise RouteBlockingBridgeError("ROUTE_NOT_CONFIGURED")
        return publish(route, event)


def build_bridge_application(
    *,
    source_provider: str,
    routes_json: str,
    destinations_json: str,
    identities_json: str,
    source_identity_json: str = "{}",
) -> BridgeApplication:
    """Build the closed directed bridge configuration from Terraform JSON."""

    routes = load_routes_json(routes_json, source_provider=source_provider)
    if not routes:
        raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION")
    destinations = _mapping_json(
        destinations_json,
        code="INVALID_DESTINATION_CONFIGURATION",
    )
    identities = _mapping_json(
        identities_json,
        code="INVALID_IDENTITY_CONFIGURATION",
    )
    source_identity = _mapping_json(
        source_identity_json,
        code="INVALID_IDENTITY_CONFIGURATION",
    )
    expected = {route.destination_provider for route in routes}
    if set(destinations) != expected or set(identities) != expected:
        raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION")
    azure_client_id = _azure_source_client_id(
        source_identity,
        required=source_provider == "azure",
    )
    publishers = {
        provider: _publisher_for_destination(
            source_provider=source_provider,
            destination_provider=provider,
            destination_raw=destinations[provider],
            identity_raw=identities[provider],
            azure_source_client_id=azure_client_id,
        )
        for provider in sorted(expected)
    }
    return BridgeApplication(source_provider, routes, publishers)


__all__ = ["BridgeApplication", "build_bridge_application"]
