"""Provider-neutral contracts used by the Azure Five-layer v2 Function App."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Mapping
import uuid


PROFILE = "five-layer-baseline@2"
MAX_EVENT_BYTES = 256 * 1024
MAX_POINTS = 1000
MAX_RAW_RANGE = timedelta(hours=24)
MAX_AGGREGATE_RANGE = timedelta(days=30)
CURSOR_MAX_AGE = timedelta(minutes=15)
QUERY_PARAMETER_FIELDS = frozenset(
    {"device_id", "metric", "from", "to", "bucket_seconds", "limit", "cursor"}
)
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

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


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


def iso_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def parse_raw_history_query(
    params: Mapping[str, Any],
) -> tuple[dict[str, Any], datetime, datetime]:
    """Validate the bounded provider-neutral raw-history query contract."""

    if not isinstance(params, Mapping) or set(params) - QUERY_PARAMETER_FIELDS:
        raise ContractError("INVALID_QUERY")
    device_id = required_text(params.get("device_id"), code="INVALID_DEVICE_ID")
    metric = required_text(params.get("metric"), code="INVALID_METRIC")
    start = parse_time(params.get("from"))
    end = parse_time(params.get("to"))
    if start >= end:
        raise ContractError("INVALID_TIME_RANGE")
    try:
        bucket_seconds = int(params.get("bucket_seconds", "0"))
        limit = int(params.get("limit", str(MAX_POINTS)))
    except (TypeError, ValueError) as exc:
        raise ContractError("INVALID_QUERY") from exc
    if bucket_seconds not in (0, 3600) or not 1 <= limit <= MAX_POINTS:
        raise ContractError("INVALID_QUERY")
    maximum_range = MAX_RAW_RANGE if bucket_seconds == 0 else MAX_AGGREGATE_RANGE
    if end - start > maximum_range:
        raise ContractError("QUERY_RANGE_EXCEEDED")
    cursor = params.get("cursor")
    if cursor not in (None, "") and not isinstance(cursor, str):
        raise ContractError("INVALID_CURSOR")
    return (
        {
            "device_id": device_id,
            "metric": metric,
            "bucket_seconds": bucket_seconds,
            "limit": limit,
            "cursor": cursor,
        },
        start,
        end,
    )


def raw_history_query_digest(
    query: Mapping[str, Any], start: datetime, end: datetime
) -> str:
    value = {
        **query,
        "cursor": None,
        "from": iso_time(start),
        "to": iso_time(end),
    }
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _cursor_key(value: str) -> bytes:
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
        raise ContractError("READER_NOT_PROVISIONED", 503)
    return value.encode("utf-8")


def encode_cursor(
    continuation_token: str,
    *,
    hmac_key: str,
    query_digest: str,
    now: datetime | None = None,
) -> str:
    """Bind one opaque Cosmos continuation token to query and expiry."""

    if not isinstance(continuation_token, str) or not continuation_token:
        raise ContractError("INVALID_CURSOR")
    current = now or datetime.now(timezone.utc)
    payload = {
        "profile": PROFILE,
        "query": query_digest,
        "expires_at": int((current + CURSOR_MAX_AGE).timestamp()),
        "continuation_token": continuation_token,
    }
    encoded = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    signature = hmac.new(
        _cursor_key(hmac_key), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"


def decode_cursor(
    value: Any,
    *,
    hmac_key: str,
    query_digest: str,
    now: datetime | None = None,
) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 32768 or "." not in value:
        raise ContractError("INVALID_CURSOR")
    encoded, signature = value.split(".", 1)
    expected = hmac.new(
        _cursor_key(hmac_key), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ContractError("INVALID_CURSOR")
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("INVALID_CURSOR") from exc
    if not isinstance(payload, Mapping):
        raise ContractError("INVALID_CURSOR")
    if payload.get("profile") != PROFILE or payload.get("query") != query_digest:
        raise ContractError("INVALID_CURSOR")
    current = now or datetime.now(timezone.utc)
    if int(payload.get("expires_at", 0)) < int(current.timestamp()):
        raise ContractError("CURSOR_EXPIRED")
    token = payload.get("continuation_token")
    if not isinstance(token, str) or not token:
        raise ContractError("INVALID_CURSOR")
    return token


def cosmos_raw_history_statement(bucket_seconds: int) -> str:
    if bucket_seconds == 0:
        return (
            "SELECT c.stored_at, c.event_time, c.value FROM c "
            "WHERE c.device_id = @device_id AND c.kind = 'raw' "
            "AND c.metric = @metric AND c.stored_at >= @from "
            "AND c.stored_at <= @to ORDER BY c.stored_at ASC"
        )
    if bucket_seconds == 3600:
        return (
            "SELECT c.bucket_start, c.min, c.max, c.sum, c.count FROM c "
            "WHERE c.device_id = @device_id AND c.kind = 'hourly_rollup' "
            "AND c.metric = @metric AND c.bucket_start >= @from "
            "AND c.bucket_start <= @to ORDER BY c.bucket_start ASC"
        )
    raise ContractError("INVALID_QUERY")


def normalize_history_points(
    documents: list[Mapping[str, Any]], bucket_seconds: int
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if bucket_seconds == 0:
        for item in documents:
            points.append(
                {
                    "stored_at": item.get("stored_at"),
                    "event_time": item.get("event_time"),
                    "value": item.get("value"),
                }
            )
        return points
    for item in documents:
        count = item.get("count")
        total = item.get("sum")
        average = total / count if isinstance(count, (int, float)) and count else 0
        points.append(
            {
                "bucket_start": item.get("bucket_start"),
                "min": item.get("min"),
                "max": item.get("max"),
                "avg": average,
                "count": count,
            }
        )
    return points


__all__ = [
    "CANONICAL_EVENT_FIELDS",
    "ContractError",
    "DOMAIN_EVENT_TYPES",
    "EVENT_TELEMETRY_PROCESSED",
    "MAX_EVENT_BYTES",
    "MAX_POINTS",
    "PROFILE",
    "canonical_json",
    "cosmos_raw_history_statement",
    "decode_cursor",
    "decode_message_body",
    "derive_event",
    "encode_cursor",
    "iso_time",
    "normalize_history_points",
    "parse_raw_history_query",
    "partition_key",
    "raw_history_query_digest",
    "validate_canonical_event",
]
