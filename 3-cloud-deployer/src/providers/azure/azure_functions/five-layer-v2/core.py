"""Provider-neutral contracts used by the Azure Five-layer v2 Function App."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
import re
from typing import Any, Mapping
import uuid


PROFILE = "five-layer-baseline@2"
MAX_EVENT_BYTES = 96 * 1024
MAX_SOURCE_ID_BYTES = 128
MAX_POINTS = 1000
MAX_RAW_RANGE = timedelta(hours=24)
MAX_AGGREGATE_RANGE = timedelta(days=30)
CURSOR_MAX_AGE = timedelta(minutes=15)
MAX_JSON_SAFE_INTEGER = 9_007_199_254_740_991
MAX_RULES = 100
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
OUTCOME_EVENT_TYPES = frozenset(
    {EVENT_ACTION_OUTCOME, EVENT_WORKFLOW_OUTCOME, EVENT_COMMAND_OUTCOME}
)
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
CONDITION_PATTERN = re.compile(r"^\s*(\S+)\s*(<=|>=|==|!=|<|>)\s*(\S+)\s*$")


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


def finite_number(value: Any) -> int | float:
    """Return one JSON-safe finite telemetry number and reject booleans."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("INVALID_NUMERIC_VALUE")
    if isinstance(value, int):
        if abs(value) > MAX_JSON_SAFE_INTEGER:
            raise ContractError("INVALID_NUMERIC_VALUE")
        return value
    if not math.isfinite(value):
        raise ContractError("INVALID_NUMERIC_VALUE")
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
        "source_sequence",
        "correlation_id",
        "causation_id",
        "producer",
    ):
        required_text(event.get(field), code="INVALID_CANONICAL_EVENT")
    required_text(
        event.get("source_id"),
        code="INVALID_CANONICAL_EVENT",
        maximum=MAX_SOURCE_ID_BYTES,
    )
    parse_time(event.get("occurred_at"))
    if not isinstance(event.get("payload"), Mapping):
        raise ContractError("INVALID_CANONICAL_EVENT")
    if len(canonical_json(event).encode("utf-8")) > MAX_EVENT_BYTES:
        raise ContractError("EVENT_TOO_LARGE")
    return dict(event)


def event_body(event: Mapping[str, Any]) -> Mapping[str, Any]:
    body = event.get("payload")
    return body if isinstance(body, Mapping) else {}


def event_id(event: Mapping[str, Any]) -> str:
    return required_text(event.get("event_id"), code="INVALID_EVENT_ID")


def build_ingress_event(
    payload: Mapping[str, Any],
    *,
    deployment_id: str,
    default_metric: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Adapt the existing provider simulator payload to the canonical v2 edge."""

    if not isinstance(payload, Mapping):
        raise ContractError("INVALID_TELEMETRY_PAYLOAD")
    current = now or datetime.now(timezone.utc)
    device_id = required_text(
        payload.get("device_id") or payload.get("iotDeviceId"),
        code="INVALID_DEVICE_ID",
    )
    metric = required_text(
        payload.get("metric") or default_metric,
        code="INVALID_METRIC",
    )
    raw_value = payload.get("value") if "value" in payload else payload.get(metric)
    value = finite_number(raw_value)
    event_time_value = (
        payload.get("event_time") or payload.get("time") or iso_time(current)
    )
    event_time = iso_time(parse_time(event_time_value))
    identity_source = {
        "deployment_id": deployment_id,
        "device_id": device_id,
        "metric": metric,
        "event_time": event_time,
        "value": value,
        "trace_id": payload.get("trace_id"),
    }
    generated_id = str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_json(identity_source)))
    source_event_id = required_text(
        payload.get("event_id") or generated_id,
        code="INVALID_EVENT_ID",
    )
    source_sequence = payload.get("source_sequence")
    if source_sequence is None:
        source_sequence = source_event_id
    elif isinstance(source_sequence, bool) or not isinstance(
        source_sequence, (str, int)
    ):
        raise ContractError("INVALID_SOURCE_SEQUENCE")
    twin_id = required_text(
        payload.get("twin_id") or device_id,
        code="INVALID_TWIN_ID",
    )
    event = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": source_event_id,
        "event_type": EVENT_TELEMETRY_RECEIVED,
        "deployment_id": required_text(
            deployment_id,
            code="INVALID_DEPLOYMENT_ID",
        ),
        "source_id": device_id,
        "source_sequence": str(source_sequence),
        "occurred_at": event_time,
        "correlation_id": str(payload.get("correlation_id") or source_event_id),
        "causation_id": source_event_id,
        "producer": "component.device-ingress",
        "payload": {
            "device_id": device_id,
            "twin_id": twin_id,
            "metric": metric,
            "value": value,
            "unit": str(payload.get("unit") or "unspecified"),
            "event_time": event_time,
            "projection_candidate": payload.get("projection_candidate") is True,
        },
    }
    return validate_canonical_event(event)


def build_processed_event(
    source: Mapping[str, Any], extension_output: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge one validated processor-extension result into telemetry."""

    validate_canonical_event(source)
    if source.get("event_type") != EVENT_TELEMETRY_RECEIVED:
        raise ContractError("UNEXPECTED_PROCESSOR_EVENT")
    if not isinstance(extension_output, Mapping):
        raise ContractError("INVALID_PROCESSOR_RESULT")
    quality = extension_output.get("quality")
    if quality not in {"accepted", "suspect"} or set(extension_output) != {
        "value",
        "quality",
    }:
        raise ContractError("INVALID_PROCESSOR_RESULT")
    payload = dict(event_body(source))
    payload["value"] = finite_number(extension_output.get("value"))
    payload["quality"] = quality
    return derive_event(
        source,
        event_type=EVENT_TELEMETRY_PROCESSED,
        producer="component.telemetry-processor",
        payload=payload,
    )


def raw_document(
    event: Mapping[str, Any],
    *,
    stored_at: datetime,
    hot_boundary_days: int,
    source_expiry_grace_hours: int = 48,
    storage_task_count: int = 1,
) -> dict[str, Any]:
    """Create the canonical Cosmos raw item for one processed event."""

    validate_canonical_event(event)
    if event.get("event_type") != EVENT_TELEMETRY_PROCESSED:
        raise ContractError("UNEXPECTED_HOT_STORAGE_EVENT")
    if (
        hot_boundary_days < 1
        or source_expiry_grace_hours < 0
        or storage_task_count < 1
    ):
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    body = event_body(event)
    device_id = partition_key(event)
    metric = required_text(body.get("metric"), code="INVALID_METRIC")
    value = finite_number(body.get("value"))
    event_time = iso_time(parse_time(body.get("event_time") or event["occurred_at"]))
    stored_at_text = iso_time(stored_at)
    window = stored_at.replace(
        minute=stored_at.minute - stored_at.minute % 5,
        second=0,
        microsecond=0,
    )
    bucket = stored_at.replace(minute=0, second=0, microsecond=0)
    payload_json = canonical_json(dict(event))
    storage_task = int.from_bytes(
        hashlib.sha256(device_id.encode("utf-8")).digest()[:8],
        byteorder="big",
    ) % storage_task_count
    return {
        "id": f"raw-{event_id(event)}",
        "kind": "raw",
        "device_id": device_id,
        "event_id": event_id(event),
        "metric": metric,
        "value": value,
        "event_time": event_time,
        "stored_at": stored_at_text,
        "storage_window": iso_time(window),
        "storage_task": storage_task,
        "bucket_start": iso_time(bucket),
        "payload_digest": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": dict(event),
        "ttl": hot_boundary_days * 86400 + source_expiry_grace_hours * 3600,
    }


def rollup_id(raw: Mapping[str, Any]) -> str:
    identity = canonical_json(
        {
            "device_id": raw.get("device_id"),
            "metric": raw.get("metric"),
            "bucket_start": raw.get("bucket_start"),
        }
    )
    return f"rollup-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def next_rollup_document(
    raw: Mapping[str, Any], current: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Return the compare-and-swap successor for one hourly rollup."""

    value = finite_number(raw.get("value"))
    expected_id = rollup_id(raw)
    if current is None:
        count = 0
        total: int | float = 0
        minimum = value
        maximum = value
        version = 0
    else:
        if (
            current.get("id") != expected_id
            or current.get("kind") != "hourly_rollup"
            or current.get("device_id") != raw.get("device_id")
            or current.get("metric") != raw.get("metric")
            or current.get("bucket_start") != raw.get("bucket_start")
        ):
            raise ContractError("INVALID_ROLLUP_STATE", 503)
        count = current.get("count")
        version = current.get("version")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or count >= MAX_JSON_SAFE_INTEGER
            or isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise ContractError("INVALID_ROLLUP_STATE", 503)
        total = finite_number(current.get("sum"))
        minimum = finite_number(current.get("min"))
        maximum = finite_number(current.get("max"))
    next_total = finite_number(total + value)
    return {
        "id": expected_id,
        "kind": "hourly_rollup",
        "device_id": raw["device_id"],
        "metric": raw["metric"],
        "bucket_start": raw["bucket_start"],
        "count": count + 1,
        "sum": next_total,
        "min": min(minimum, value),
        "max": max(maximum, value),
        "version": version + 1,
        "ttl": raw["ttl"],
    }


def build_twin_projection(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Create the sparse L3-to-L4 event only for an explicit candidate."""

    validate_canonical_event(event)
    if event.get("event_type") != EVENT_TELEMETRY_PROCESSED:
        raise ContractError("UNEXPECTED_TWIN_PROJECTION_SOURCE")
    body = event_body(event)
    if body.get("projection_candidate") is not True:
        return None
    metric = required_text(body.get("metric"), code="INVALID_METRIC")
    value = finite_number(body.get("value"))
    return derive_event(
        event,
        event_type=EVENT_TWIN_STATE_UPSERTED,
        producer="component.historical-persistence",
        payload={
            "twin_id": required_text(body.get("twin_id"), code="INVALID_TWIN_ID"),
            "source_id": partition_key(event),
            "source_sequence": str(event.get("source_sequence")),
            "observed_at": iso_time(
                parse_time(body.get("event_time") or event.get("occurred_at"))
            ),
            "state_patch": {metric: value},
        },
    )


def _condition_operand(token: str, body: Mapping[str, Any]) -> Any:
    typed = re.fullmatch(r"(DOUBLE|INTEGER|STRING|BOOLEAN)\((.*)\)", token)
    if typed:
        kind, raw = typed.groups()
        try:
            if kind == "DOUBLE":
                return finite_number(float(raw))
            if kind == "INTEGER":
                return finite_number(int(raw))
        except ValueError as exc:
            raise ContractError("INVALID_RULE_CONFIGURATION", 503) from exc
        if kind == "BOOLEAN" and raw.lower() in {"true", "false"}:
            return raw.lower() == "true"
        if kind == "STRING":
            return raw
        raise ContractError("INVALID_RULE_CONFIGURATION", 503)
    field = token.rsplit(".", 1)[-1]
    if body.get("metric") == field and "value" in body:
        return body["value"]
    if field not in body:
        raise ContractError("RULE_OPERAND_NOT_FOUND")
    return body[field]


def _condition_matches(condition: Any, body: Mapping[str, Any]) -> bool:
    if not isinstance(condition, str):
        raise ContractError("INVALID_RULE_CONFIGURATION", 503)
    match = CONDITION_PATTERN.fullmatch(condition)
    if not match:
        raise ContractError("INVALID_RULE_CONFIGURATION", 503)
    left, operator, right = match.groups()
    lhs = _condition_operand(left, body)
    rhs = _condition_operand(right, body)
    comparisons = {
        "<": lambda: lhs < rhs,
        ">": lambda: lhs > rhs,
        "<=": lambda: lhs <= rhs,
        ">=": lambda: lhs >= rhs,
        "==": lambda: lhs == rhs,
        "!=": lambda: lhs != rhs,
    }
    try:
        return bool(comparisons[operator]())
    except TypeError as exc:
        raise ContractError("RULE_TYPE_MISMATCH") from exc


def build_rule_matches(
    event: Mapping[str, Any], rules: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Return deterministic match events for the bounded configured rule set."""

    validate_canonical_event(event)
    if event.get("event_type") != EVENT_TELEMETRY_PROCESSED:
        raise ContractError("UNEXPECTED_RULE_EVENT")
    if len(rules) > MAX_RULES or not all(isinstance(rule, Mapping) for rule in rules):
        raise ContractError("INVALID_RULE_CONFIGURATION", 503)
    body = event_body(event)
    matches = []
    rule_ids = set()
    for index, rule in enumerate(rules):
        action = rule.get("action")
        if not isinstance(action, Mapping):
            raise ContractError("INVALID_RULE_CONFIGURATION", 503)
        rule_id = required_text(
            rule.get("rule_id") or f"rule-{index + 1}",
            code="INVALID_RULE_CONFIGURATION",
        )
        if rule_id in rule_ids:
            raise ContractError("INVALID_RULE_CONFIGURATION", 503)
        rule_ids.add(rule_id)
        if not _condition_matches(rule.get("condition"), body):
            continue
        matches.append(
            derive_event(
                event,
                event_type=EVENT_MATCHED,
                producer="component.rule-evaluator",
                payload={
                    **dict(body),
                    "rule_id": rule_id,
                    "condition": str(rule["condition"]),
                    "action": dict(action),
                },
                identity_suffix=rule_id,
            )
        )
    return matches


def outcome_document(
    event: Mapping[str, Any],
    *,
    stored_at: datetime,
    hot_boundary_days: int,
    storage_task_count: int = 1,
) -> dict[str, Any]:
    """Create one idempotent non-rollup hot record for a terminal outcome."""

    validate_canonical_event(event)
    if event.get("event_type") not in OUTCOME_EVENT_TYPES:
        raise ContractError("UNEXPECTED_OUTCOME_EVENT")
    if hot_boundary_days < 1 or storage_task_count < 1:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    payload_json = canonical_json(dict(event))
    identity = event_id(event)
    device_id = partition_key(event)
    window = stored_at.replace(
        minute=stored_at.minute - stored_at.minute % 5,
        second=0,
        microsecond=0,
    )
    storage_task = int.from_bytes(
        hashlib.sha256(device_id.encode("utf-8")).digest()[:8],
        byteorder="big",
    ) % storage_task_count
    return {
        "id": f"outcome-{identity}",
        "kind": "outcome",
        "device_id": device_id,
        "event_id": identity,
        "event_type": event["event_type"],
        "stored_at": iso_time(stored_at),
        "storage_window": iso_time(window),
        "storage_task": storage_task,
        "payload_digest": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": dict(event),
        "ttl": hot_boundary_days * 86400 + 48 * 3600,
    }


def decode_message_body(body: bytes | str) -> dict[str, Any]:
    """Decode one Event Hubs or Service Bus body and validate it."""

    return validate_canonical_event(decode_json_object(body))


def decode_json_object(body: bytes | str) -> dict[str, Any]:
    """Decode one bounded UTF-8 JSON object without assuming an event schema."""

    if not isinstance(body, (bytes, str)):
        raise ContractError("INVALID_UTF8_JSON")
    raw = body if isinstance(body, bytes) else body.encode("utf-8")
    if len(raw) > MAX_EVENT_BYTES:
        raise ContractError("EVENT_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ContractError("INVALID_UTF8_JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("INVALID_CANONICAL_EVENT")
    return value


def partition_key(event: Mapping[str, Any]) -> str:
    payload = event.get("payload")
    body = payload if isinstance(payload, Mapping) else {}
    return required_text(
        event.get("source_id") or body.get("device_id"),
        code="INVALID_PARTITION_KEY",
        maximum=MAX_SOURCE_ID_BYTES,
    )


def derive_event(
    source: Mapping[str, Any],
    *,
    event_type: str,
    producer: str,
    payload: Mapping[str, Any] | None = None,
    identity_suffix: str = "",
) -> dict[str, Any]:
    """Create an idempotent child event from one canonical source event."""

    validate_canonical_event(source)
    source_id = str(source["event_id"])
    identity = f"{source_id}:{event_type}:{producer}"
    if identity_suffix:
        identity = f"{identity}:{identity_suffix}"
    child_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
    child = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": child_id,
        "event_type": event_type,
        "deployment_id": source["deployment_id"],
        "source_id": source["source_id"],
        "source_sequence": source["source_sequence"],
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
                    "stored_at": iso_time(parse_time(item.get("stored_at"))),
                    "event_time": iso_time(parse_time(item.get("event_time"))),
                    "value": finite_number(item.get("value")),
                }
            )
        return points
    for item in documents:
        count = item.get("count")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
            or count > MAX_JSON_SAFE_INTEGER
        ):
            raise ContractError("INVALID_HISTORY_RECORD", 503)
        total = finite_number(item.get("sum"))
        average = finite_number(total / count)
        points.append(
            {
                "bucket_start": iso_time(parse_time(item.get("bucket_start"))),
                "min": finite_number(item.get("min")),
                "max": finite_number(item.get("max")),
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
    "MAX_SOURCE_ID_BYTES",
    "PROFILE",
    "build_ingress_event",
    "build_processed_event",
    "build_rule_matches",
    "build_twin_projection",
    "canonical_json",
    "cosmos_raw_history_statement",
    "decode_cursor",
    "decode_json_object",
    "decode_message_body",
    "derive_event",
    "encode_cursor",
    "event_body",
    "event_id",
    "finite_number",
    "iso_time",
    "next_rollup_document",
    "normalize_history_points",
    "outcome_document",
    "parse_raw_history_query",
    "partition_key",
    "raw_document",
    "raw_history_query_digest",
    "rollup_id",
    "validate_canonical_event",
]
