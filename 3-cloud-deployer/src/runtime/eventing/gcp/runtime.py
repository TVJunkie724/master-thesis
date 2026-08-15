"""GCP Pub/Sub wrapper for source-owned Phase 8 event bridge routes."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Mapping

from ..bridge_application import BridgeApplication, build_bridge_application
from ..bridge_core import BridgeContractError, RouteCircuitBreaker
from ..destination_publishers import GCP_PUBSUB_ENDPOINT
from .bridge import handle_push, handle_streaming_pull


_TOPIC = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/topics/[A-Za-z][A-Za-z0-9._~+%-]{2,254}$"
)
_APPLICATION: BridgeApplication | None = None
_FAILURE_WRITER: "GcpFailureWriter | None" = None
_CIRCUITS: dict[str, RouteCircuitBreaker] = {}


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class GcpFailureWriter:
    """Publish the bounded failure record to the source Pub/Sub DLQ topic."""

    def __init__(self, topic: str, publisher: object) -> None:
        if not _TOPIC.fullmatch(topic):
            raise BridgeContractError("INVALID_FAILURE_DESTINATION_CONFIGURATION")
        self._topic = topic
        self._publisher = publisher

    def __call__(self, failure: Mapping[str, Any]) -> bool:
        envelope = failure.get("canonical_envelope")
        source_id = envelope.get("source_id") if isinstance(envelope, Mapping) else None
        key = source_id if isinstance(source_id, str) and source_id else "invalid"
        future = self._publisher.publish(
            self._topic,
            _canonical_bytes(failure),
            ordering_key=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        )
        message_id = future.result(timeout=30)
        return isinstance(message_id, str) and bool(message_id)


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or len(value.encode("utf-8")) > 128 * 1024:
        raise BridgeContractError("INVALID_BRIDGE_RUNTIME_CONFIGURATION")
    return value


def _application() -> BridgeApplication:
    global _APPLICATION
    if _APPLICATION is None:
        _APPLICATION = build_bridge_application(
            source_provider="gcp",
            routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
            destinations_json=_required_environment("BRIDGE_DESTINATIONS_JSON"),
            identities_json=_required_environment("BRIDGE_IDENTITIES_JSON"),
        )
    return _APPLICATION


def _failure_writer() -> GcpFailureWriter:
    global _FAILURE_WRITER
    if _FAILURE_WRITER is None:
        from google.api_core.client_options import ClientOptions
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient(
            client_options=ClientOptions(api_endpoint=GCP_PUBSUB_ENDPOINT),
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=True
            ),
        )
        _FAILURE_WRITER = GcpFailureWriter(
            _required_environment("BRIDGE_FAILURE_TOPIC"),
            publisher,
        )
    return _FAILURE_WRITER


def push_request(request: object) -> tuple[str, int]:
    """Return HTTP 2xx only after destination or safe DLQ acceptance."""

    get_json = getattr(request, "get_json", None)
    body = get_json(silent=True) if callable(get_json) else None
    if not isinstance(body, Mapping):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    app = _application()
    result = handle_push(
        body,
        routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
        publish=app.publish,
        write_dlq=_failure_writer(),
        circuit_breakers=_CIRCUITS,
    )
    if result.acknowledged_record_ids:
        return "", 204
    return "", 503


def streaming_pull_callback(message: object) -> None:
    """Ack one pull message only after destination or safe DLQ acceptance."""

    app = _application()
    result = handle_streaming_pull(
        message,
        routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
        publish=app.publish,
        write_dlq=_failure_writer(),
        circuit_breakers=_CIRCUITS,
    )
    if result.acknowledged_record_ids:
        message.ack()
    else:
        message.nack()


__all__ = ["GcpFailureWriter", "push_request", "streaming_pull_callback"]
