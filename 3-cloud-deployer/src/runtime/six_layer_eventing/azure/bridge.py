"""Azure Event Hubs and Service Bus source adapter for the Phase 8 bridge."""

from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping, MutableMapping

from ..bridge_core import (
    BatchResult,
    BridgeContractError,
    BridgeRoute,
    RouteCircuitBreaker,
    SourceRecord,
    deliver_batch,
    load_routes_json,
)


def _body(value: object) -> bytes:
    getter = getattr(value, "get_body", None)
    body = getter() if callable(getter) else value
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, bytes):
        return body
    if isinstance(body, Iterable):
        chunks = list(body)
        if all(isinstance(chunk, bytes) for chunk in chunks):
            return b"".join(chunks)
    raise BridgeContractError("INVALID_SOURCE_RECORD")


def _event(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
    if not isinstance(value, dict):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    return value


def decode_event_hub_records(
    messages: Iterable[object],
    *,
    attempt_count: int = 1,
) -> tuple[SourceRecord, ...]:
    """Decode a bounded Event Hubs trigger batch.

    Event Hubs owns the five retries and final failure destination, so the
    source event does not expose a portable delivery count to Python.
    """

    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or attempt_count < 1
        or attempt_count > 6
    ):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    decoded: list[SourceRecord] = []
    for index, message in enumerate(messages):
        sequence = getattr(message, "sequence_number", None)
        record_id = str(sequence if sequence is not None else index)
        decoded.append(
            SourceRecord(
                record_id=record_id,
                event=_event(_body(message)),
                attempt_count=attempt_count,
            )
        )
    if not decoded:
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    return tuple(decoded)


def decode_service_bus_record(message: object) -> SourceRecord:
    """Decode one session-enabled Service Bus message."""

    message_id = getattr(message, "message_id", None)
    delivery_count = getattr(message, "delivery_count", 0)
    try:
        prior_failed_deliveries = int(delivery_count or 0)
        attempt_count = min(6, prior_failed_deliveries + 1)
    except (TypeError, ValueError) as exc:
        raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
    if prior_failed_deliveries < 0:
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    if not isinstance(message_id, str) or not message_id:
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    return SourceRecord(
        record_id=message_id,
        event=_event(_body(message)),
        attempt_count=attempt_count,
    )


def handle_event_hub_batch(
    messages: Iterable[object],
    *,
    attempt_count: int = 1,
    routes_json: str,
    publish: Callable[[BridgeRoute, Mapping[str, Any]], object],
    write_dlq: Callable[[Mapping[str, Any]], bool],
    circuit_breakers: MutableMapping[str, RouteCircuitBreaker] | None = None,
) -> BatchResult:
    """Deliver one Event Hubs batch; the wrapper checkpoints only on success."""

    return deliver_batch(
        decode_event_hub_records(messages, attempt_count=attempt_count),
        load_routes_json(routes_json, source_provider="azure"),
        publish=publish,
        write_dlq=write_dlq,
        circuit_breakers=circuit_breakers,
    )


def handle_service_bus_message(
    message: object,
    *,
    routes_json: str,
    publish: Callable[[BridgeRoute, Mapping[str, Any]], object],
    write_dlq: Callable[[Mapping[str, Any]], bool],
    circuit_breakers: MutableMapping[str, RouteCircuitBreaker] | None = None,
) -> BatchResult:
    """Deliver one Service Bus message for explicit complete/abandon/dead-letter."""

    return deliver_batch(
        (decode_service_bus_record(message),),
        load_routes_json(routes_json, source_provider="azure"),
        publish=publish,
        write_dlq=write_dlq,
        circuit_breakers=circuit_breakers,
    )


__all__ = [
    "decode_event_hub_records",
    "decode_service_bus_record",
    "handle_event_hub_batch",
    "handle_service_bus_message",
]

