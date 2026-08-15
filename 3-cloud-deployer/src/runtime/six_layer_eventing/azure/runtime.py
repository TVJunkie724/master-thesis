"""Azure Functions wrapper for source-owned Phase 8 event bridge routes."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping

from ..bridge_application import BridgeApplication, build_bridge_application
from ..bridge_core import (
    BridgeContractError,
    BridgeRoute,
    RetryableBridgeError,
    RouteCircuitBreaker,
)
from ..destination_publishers import AzureDestination, load_destination
from .bridge import handle_event_hub_batch, handle_service_bus_message


_APPLICATION: BridgeApplication | None = None
_FAILURE_WRITER: "AzureFailureWriter | None" = None
_CIRCUITS: dict[str, RouteCircuitBreaker] = {}


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class AzureFailureWriter:
    """Write safe failures to a dead-letter Event Hub or Service Bus queue."""

    def __init__(
        self,
        routes: tuple[BridgeRoute, ...],
        destination: AzureDestination,
        credential: object,
        *,
        event_hub_factory: object | None = None,
        event_data_factory: object | None = None,
        service_bus_factory: object | None = None,
        service_bus_message_factory: object | None = None,
    ) -> None:
        channels = {route.route_id: route.channel_class for route in routes}
        if (
            not channels
            or ("telemetry" in channels.values() and not destination.telemetry_namespace)
            or ("control" in channels.values() and not destination.control_namespace)
        ):
            raise BridgeContractError("INVALID_FAILURE_DESTINATION_CONFIGURATION")
        if event_hub_factory is None or event_data_factory is None:
            from azure.eventhub import EventData, EventHubProducerClient

            event_hub_factory = EventHubProducerClient
            event_data_factory = EventData
        if service_bus_factory is None or service_bus_message_factory is None:
            from azure.servicebus import ServiceBusClient, ServiceBusMessage

            service_bus_factory = ServiceBusClient
            service_bus_message_factory = ServiceBusMessage
        self._channels = channels
        self._destination = destination
        self._credential = credential
        self._event_hub_factory = event_hub_factory
        self._event_data_factory = event_data_factory
        self._service_bus_factory = service_bus_factory
        self._service_bus_message_factory = service_bus_message_factory

    def __call__(self, failure: Mapping[str, Any]) -> bool:
        route_id = str(failure.get("route_id", ""))
        channel = self._channels.get(route_id)
        if channel not in {"telemetry", "control"}:
            raise BridgeContractError("INVALID_FAILURE_DESTINATION_CONFIGURATION")
        data = _canonical_bytes(failure)
        digest = hashlib.sha256(data).hexdigest()
        envelope = failure.get("canonical_envelope")
        source_id = envelope.get("source_id") if isinstance(envelope, Mapping) else None
        key = source_id if isinstance(source_id, str) and source_id else "invalid"
        safe_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
        if channel == "telemetry":
            producer = self._event_hub_factory(
                fully_qualified_namespace=self._destination.telemetry_namespace,
                eventhub_name=self._destination.telemetry_entity,
                credential=self._credential,
                buffered_mode=False,
            )
            with producer:
                producer.send_batch(
                    [self._event_data_factory(data)],
                    partition_key=safe_key,
                    timeout=30,
                )
            return True
        client = self._service_bus_factory(
            fully_qualified_namespace=self._destination.control_namespace,
            credential=self._credential,
        )
        with client:
            sender = client.get_queue_sender(
                queue_name=self._destination.control_entity
            )
            with sender:
                sender.send_messages(
                    self._service_bus_message_factory(
                        data,
                        message_id=digest,
                        session_id=safe_key,
                    )
                )
        return True


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or len(value.encode("utf-8")) > 128 * 1024:
        raise BridgeContractError("INVALID_BRIDGE_RUNTIME_CONFIGURATION")
    return value


def _application() -> BridgeApplication:
    global _APPLICATION
    if _APPLICATION is None:
        _APPLICATION = build_bridge_application(
            source_provider="azure",
            routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
            destinations_json=_required_environment("BRIDGE_DESTINATIONS_JSON"),
            identities_json=_required_environment("BRIDGE_IDENTITIES_JSON"),
            source_identity_json=_required_environment("BRIDGE_SOURCE_IDENTITY_JSON"),
        )
    return _APPLICATION


def _failure_writer(app: BridgeApplication) -> AzureFailureWriter:
    global _FAILURE_WRITER
    if _FAILURE_WRITER is None:
        from azure.identity import ManagedIdentityCredential

        source_identity = json.loads(
            _required_environment("BRIDGE_SOURCE_IDENTITY_JSON")
        )
        client_id = source_identity.get("managed_identity_client_id")
        if not isinstance(client_id, str) or not client_id:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        destination = load_destination(
            json.loads(_required_environment("BRIDGE_FAILURE_DESTINATION_JSON")),
            provider="azure",
        )
        if not isinstance(destination, AzureDestination):
            raise BridgeContractError("INVALID_FAILURE_DESTINATION_CONFIGURATION")
        _FAILURE_WRITER = AzureFailureWriter(
            app.routes,
            destination,
            ManagedIdentityCredential(client_id=client_id),
        )
    return _FAILURE_WRITER


def _require_acknowledged(result: object) -> None:
    acknowledged = getattr(result, "acknowledged_record_ids", ())
    retry = getattr(result, "retry_record_ids", ())
    blocked = getattr(result, "blocked_record_ids", ())
    if not acknowledged or retry or blocked:
        raise RetryableBridgeError("SOURCE_NOT_ACKNOWLEDGED")


def event_hub_batch(messages: list[object], *, attempt_count: int = 1) -> None:
    """Let Functions checkpoint a batch only after all records are accepted."""

    app = _application()
    result = handle_event_hub_batch(
        messages,
        attempt_count=attempt_count,
        routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
        publish=app.publish,
        write_dlq=_failure_writer(app),
        circuit_breakers=_CIRCUITS,
    )
    _require_acknowledged(result)


def service_bus_message(message: object) -> None:
    """Let Functions complete one message only after target or safe DLQ acceptance."""

    app = _application()
    result = handle_service_bus_message(
        message,
        routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
        publish=app.publish,
        write_dlq=_failure_writer(app),
        circuit_breakers=_CIRCUITS,
    )
    _require_acknowledged(result)


__all__ = ["AzureFailureWriter", "event_hub_batch", "service_bus_message"]

