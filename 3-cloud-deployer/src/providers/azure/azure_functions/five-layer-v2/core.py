"""Provider-neutral contracts used by the Azure Five-layer v2 Function App."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping
import uuid


PROFILE = "five-layer-baseline@2"
MAX_EVENT_BYTES = 256 * 1024
EVENT_TELEMETRY_RECEIVED = "telemetry.received.v1"
EVENT_TELEMETRY_PROCESSED = "telemetry.processed.v1"
EVENT_TWIN_STATE_UPSERTED = "twin.state.upserted"
EVENT_MATCHED = "event.matched.v1"
EVENT_NOTIFICATION_REQUESTED = "notification.requested.v1"
EVENT_DEVICE_COMMAND_REQUESTED = "device.command.requested.v1"
EVENT_ACTION_OUTCOME = "extension.action.outcome.v1"
EVENT_WORKFLOW_OUTCOME = "notification.workflow.outcome.v1"
EVENT_COMMAND_OUTCOME = "device.command.outcome.v1"
DOMAIN_EVENT_TYPES = frozenset(
    {
        EVENT_TELEMETRY_RECEIVED,
        EVENT_TELEMETRY_PROCESSED,
        EVENT_TWIN_STATE_UPSERTED,
        EVENT_MATCHED,
        EVENT_NOTIFICATION_REQUESTED,
        EVENT_DEVICE_COMMAND_REQUESTED,
        EVENT_ACTION_OUTCOME,
        EVENT_WORKFLOW_OUTCOME,
        EVENT_COMMAND_OUTCOME,
    }
)
CANONICAL_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "event_id",
        "event_type",
        "deployment_id",
        "source_id",
        "source_sequence",
        "occurred_at",
        "correlation_id",
        "causation_id",
        "producer",
        "payload",
    }
)


class ContractError(ValueError):
    """Stable payload-free contract failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def required_text(value: Any, *, code: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise ContractError(code)
    return value


def parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ContractError("INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        raise ContractError("INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


def validate_canonical_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact immutable domain envelope without provider fields."""

    if set(event) != CANONICAL_EVENT_FIELDS:
        raise ContractError("INVALID_CANONICAL_EVENT")
    if event.get("schema_version") != "canonical-domain-event.v1":
        raise ContractError("UNSUPPORTED_EVENT_SCHEMA")
    if event.get("event_type") not in DOMAIN_EVENT_TYPES:
        raise ContractError("UNKNOWN_DOMAIN_EVENT")
    for field in (
        "event_id",
        "deployment_id",
        "source_id",
        "source_sequence",
        "correlation_id",
        "causation_id",
        "producer",
    ):
        required_text(event.get(field), code="INVALID_CANONICAL_EVENT")
    parse_time(event.get("occurred_at"))
    if not isinstance(event.get("payload"), Mapping):
        raise ContractError("INVALID_CANONICAL_EVENT")
    if len(canonical_json(event).encode("utf-8")) > MAX_EVENT_BYTES:
        raise ContractError("EVENT_TOO_LARGE")
    return dict(event)


def decode_message_body(body: bytes | str) -> dict[str, Any]:
    """Decode one Event Hubs or Service Bus body and validate it."""

    try:
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ContractError("INVALID_UTF8_JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("INVALID_CANONICAL_EVENT")
    return validate_canonical_event(value)


def partition_key(event: Mapping[str, Any]) -> str:
    payload = event.get("payload")
    body = payload if isinstance(payload, Mapping) else {}
    return required_text(
        body.get("device_id") or event.get("source_id"),
        code="INVALID_PARTITION_KEY",
    )


def derive_event(
    source: Mapping[str, Any],
    *,
    event_type: str,
    producer: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an idempotent child event from one canonical source event."""

    validate_canonical_event(source)
    source_id = str(source["event_id"])
    child_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{event_type}:{producer}")
    )
    child = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": child_id,
        "event_type": event_type,
        "deployment_id": source["deployment_id"],
        "source_id": source["source_id"],
        "source_sequence": source_id,
        "occurred_at": source["occurred_at"],
        "correlation_id": source["correlation_id"],
        "causation_id": source_id,
        "producer": producer,
        "payload": dict(payload if payload is not None else source["payload"]),
    }
    return validate_canonical_event(child)


__all__ = [
    "CANONICAL_EVENT_FIELDS",
    "ContractError",
    "DOMAIN_EVENT_TYPES",
    "EVENT_TELEMETRY_PROCESSED",
    "MAX_EVENT_BYTES",
    "PROFILE",
    "canonical_json",
    "decode_message_body",
    "derive_event",
    "partition_key",
    "validate_canonical_event",
]
