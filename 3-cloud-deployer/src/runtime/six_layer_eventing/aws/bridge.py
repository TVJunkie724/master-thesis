"""AWS Kinesis and SQS FIFO source adapter for the Phase 8 bridge."""

from __future__ import annotations

import base64
import json
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from ..bridge_core import (
    BridgeContractError,
    BridgeRoute,
    RouteCircuitBreaker,
    SourceRecord,
    deliver_batch,
    load_routes_json,
)


def _json_object(raw: bytes | str, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise BridgeContractError(code) from exc
    if not isinstance(value, dict):
        raise BridgeContractError(code)
    return value


def _sqs_event(body: str) -> dict[str, Any]:
    value = _json_object(body, code="INVALID_SOURCE_RECORD")
    # SNS subscriptions wrap the event unless raw-message delivery is enabled.
    if value.get("Type") == "Notification" and isinstance(value.get("Message"), str):
        return _json_object(value["Message"], code="INVALID_SOURCE_RECORD")
    return value


def decode_records(event: Mapping[str, Any]) -> tuple[SourceRecord, ...]:
    """Decode one homogeneous Lambda broker batch without logging payloads."""

    raw_records = event.get("Records")
    if not isinstance(raw_records, list) or not raw_records:
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    decoded: list[SourceRecord] = []
    source_kind = ""
    for value in raw_records:
        if not isinstance(value, Mapping):
            raise BridgeContractError("INVALID_SOURCE_RECORD")
        source = str(value.get("eventSource") or value.get("EventSource") or "")
        if source_kind and source != source_kind:
            raise BridgeContractError("INVALID_SOURCE_RECORD")
        source_kind = source
        if source == "aws:kinesis":
            kinesis = value.get("kinesis")
            encoded = kinesis.get("data") if isinstance(kinesis, Mapping) else None
            if not isinstance(encoded, str):
                raise BridgeContractError("INVALID_SOURCE_RECORD")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as exc:
                raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
            payload = _json_object(raw, code="INVALID_SOURCE_RECORD")
            attempt_count = 1
            first_failure_at = None
            record_id = value.get("eventID")
        elif source == "aws:sqs":
            body = value.get("body")
            attributes = value.get("attributes")
            if not isinstance(body, str) or not isinstance(attributes, Mapping):
                raise BridgeContractError("INVALID_SOURCE_RECORD")
            try:
                attempt_count = min(
                    6,
                    int(str(attributes.get("ApproximateReceiveCount", "1"))),
                )
            except ValueError as exc:
                raise BridgeContractError("INVALID_SOURCE_RECORD") from exc
            payload = _sqs_event(body)
            first_failure_at = None
            record_id = value.get("messageId")
        else:
            raise BridgeContractError("INVALID_SOURCE_RECORD")
        if not isinstance(record_id, str) or not record_id:
            raise BridgeContractError("INVALID_SOURCE_RECORD")
        decoded.append(
            SourceRecord(
                record_id=record_id,
                event=payload,
                attempt_count=attempt_count,
                first_failure_at=first_failure_at,
            )
        )
    return tuple(decoded)


def handle_batch(
    event: Mapping[str, Any],
    *,
    routes_json: str,
    publish: Callable[[BridgeRoute, Mapping[str, Any]], object],
    write_dlq: Callable[[Mapping[str, Any]], bool],
    circuit_breakers: MutableMapping[str, RouteCircuitBreaker] | None = None,
) -> dict[str, Sequence[dict[str, str]]]:
    """Return the AWS partial-batch response after destination acceptance."""

    routes = load_routes_json(routes_json, source_provider="aws")
    records = decode_records(event)
    result = deliver_batch(
        records,
        routes,
        publish=publish,
        write_dlq=write_dlq,
        circuit_breakers=circuit_breakers,
    )
    failed = set(result.retry_record_ids) | set(result.blocked_record_ids)
    return {
        "batchItemFailures": [
            {"itemIdentifier": record.record_id}
            for record in records
            if record.record_id in failed
        ]
    }


__all__ = ["decode_records", "handle_batch"]

