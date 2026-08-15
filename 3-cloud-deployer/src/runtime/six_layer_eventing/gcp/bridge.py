"""GCP Pub/Sub push and StreamingPull source adapter for the Phase 8 bridge."""

from __future__ import annotations

import base64
import json
from typing import Any, Callable, Mapping, MutableMapping

from ..bridge_core import (
    BatchResult,
    BridgeContractError,
    BridgeRoute,
    RouteCircuitBreaker,
    SourceRecord,
    deliver_batch,
    load_routes_json,
)


def _event(encoded: object) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
    if not isinstance(value, dict):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    return value


def decode_push(body: Mapping[str, Any]) -> SourceRecord:
    """Decode one authenticated Pub/Sub push envelope."""

    message = body.get("message")
    if not isinstance(message, Mapping):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    message_id = message.get("messageId") or message.get("message_id")
    if not isinstance(message_id, str) or not message_id:
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    try:
        attempt_count = min(6, int(body.get("deliveryAttempt", 1)))
    except (TypeError, ValueError) as exc:
        raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
    return SourceRecord(
        record_id=message_id,
        event=_event(message.get("data")),
        attempt_count=attempt_count,
    )


def decode_streaming_pull(message: object) -> SourceRecord:
    """Decode one Pub/Sub subscriber message without acknowledging it."""

    message_id = getattr(message, "message_id", None)
    data = getattr(message, "data", None)
    delivery_attempt = getattr(message, "delivery_attempt", 1)
    if not isinstance(message_id, str) or not message_id or not isinstance(data, bytes):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    try:
        value = json.loads(data)
        attempt_count = min(6, int(delivery_attempt or 1))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
    if not isinstance(value, dict):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    return SourceRecord(
        record_id=message_id,
        event=value,
        attempt_count=attempt_count,
    )


def handle_push(
    body: Mapping[str, Any],
    *,
    routes_json: str,
    publish: Callable[[BridgeRoute, Mapping[str, Any]], object],
    write_dlq: Callable[[Mapping[str, Any]], bool],
    circuit_breakers: MutableMapping[str, RouteCircuitBreaker] | None = None,
) -> BatchResult:
    """Deliver one push message; HTTP 2xx is allowed only when acknowledged."""

    return deliver_batch(
        (decode_push(body),),
        load_routes_json(routes_json, source_provider="gcp"),
        publish=publish,
        write_dlq=write_dlq,
        circuit_breakers=circuit_breakers,
    )


def handle_streaming_pull(
    message: object,
    *,
    routes_json: str,
    publish: Callable[[BridgeRoute, Mapping[str, Any]], object],
    write_dlq: Callable[[Mapping[str, Any]], bool],
    circuit_breakers: MutableMapping[str, RouteCircuitBreaker] | None = None,
) -> BatchResult:
    """Deliver one pull message; its wrapper performs the returned ack/nack."""

    return deliver_batch(
        (decode_streaming_pull(message),),
        load_routes_json(routes_json, source_provider="gcp"),
        publish=publish,
        write_dlq=write_dlq,
        circuit_breakers=circuit_breakers,
    )


__all__ = [
    "decode_push",
    "decode_streaming_pull",
    "handle_push",
    "handle_streaming_pull",
]

