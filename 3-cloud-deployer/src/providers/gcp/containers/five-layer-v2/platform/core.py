"""Provider-neutral contracts for the GCP Five-layer v2 Cloud Run runtime."""

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
MAX_EVENT_BYTES = 256 * 1024
MAX_RULES = 100
MAX_TWIN_ENTITIES = 100
MAX_JSON_SAFE_INTEGER = 9_007_199_254_740_991
MAX_HISTORY_POINTS = 1000
MAX_CURSOR_BYTES = 16 * 1024
MAX_RAW_RANGE = timedelta(hours=24)
MAX_AGGREGATE_RANGE = timedelta(days=30)
CURSOR_MAX_AGE = timedelta(minutes=15)
QUERY_PARAMETER_FIELDS = frozenset(
    {"device_id", "metric", "from", "to", "bucket_seconds", "limit", "cursor"}
)
CONDITION_PATTERN = re.compile(r"^\s*(\S+)\s*(<=|>=|==|!=|<|>)\s*(\S+)\s*$")

EVENT_TELEMETRY_RECEIVED = "telemetry.received.v1"
EVENT_TELEMETRY_PROCESSED = "telemetry.processed.v1"
EVENT_TWIN_STATE_UPSERTED = "twin.state.upserted"
EVENT_TWIN_MODEL_UPSERTED = "twin.model.upserted"
EVENT_TWIN_RELATIONSHIP_UPSERTED = "twin.relationship.upserted"
EVENT_TWIN_RELATIONSHIP_DELETED = "twin.relationship.deleted"
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
        EVENT_TWIN_MODEL_UPSERTED,
        EVENT_TWIN_RELATIONSHIP_UPSERTED,
        EVENT_TWIN_RELATIONSHIP_DELETED,
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
    """Stable, payload-free runtime contract failure."""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def required_text(value: Any, *, code: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise ContractError(code)
    return value


def finite_number(value: Any) -> int | float:
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
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def validate_canonical_event(event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event, Mapping) or set(event) != CANONICAL_EVENT_FIELDS:
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
    try:
        encoded = canonical_json(event).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("INVALID_CANONICAL_EVENT") from exc
    if len(encoded) > MAX_EVENT_BYTES:
        raise ContractError("EVENT_TOO_LARGE")
    return dict(event)


def event_body(event: Mapping[str, Any]) -> Mapping[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, Mapping) else {}


def event_id(event: Mapping[str, Any]) -> str:
    return required_text(event.get("event_id"), code="INVALID_EVENT_ID")


def partition_key(event: Mapping[str, Any]) -> str:
    body = event_body(event)
    return required_text(
        body.get("device_id") or event.get("source_id"),
        code="INVALID_PARTITION_KEY",
    )


def build_ingress_event(
    payload: Mapping[str, Any],
    *,
    deployment_id: str,
    default_metric: str = "value",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Adapt one bounded MQTT/HTTP payload to the canonical event envelope."""

    if not isinstance(payload, Mapping):
        raise ContractError("INVALID_TELEMETRY_PAYLOAD")
    current = now or datetime.now(timezone.utc)
    device_id = required_text(
        payload.get("device_id") or payload.get("iotDeviceId"),
        code="INVALID_DEVICE_ID",
    )
    metric = required_text(payload.get("metric") or default_metric, code="INVALID_METRIC")
    value = finite_number(payload.get("value", payload.get(metric)))
    occurred_at = iso_time(
        parse_time(payload.get("event_time") or payload.get("time") or iso_time(current))
    )
    identity = {
        "deployment_id": deployment_id,
        "device_id": device_id,
        "metric": metric,
        "event_time": occurred_at,
        "value": value,
    }
    generated_id = str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_json(identity)))
    source_event_id = required_text(
        payload.get("event_id") or generated_id,
        code="INVALID_EVENT_ID",
    )
    source_sequence = payload.get("source_sequence", source_event_id)
    if isinstance(source_sequence, bool) or not isinstance(source_sequence, (str, int)):
        raise ContractError("INVALID_SOURCE_SEQUENCE")
    event = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": source_event_id,
        "event_type": EVENT_TELEMETRY_RECEIVED,
        "deployment_id": required_text(deployment_id, code="INVALID_DEPLOYMENT_ID"),
        "source_id": device_id,
        "source_sequence": str(source_sequence),
        "occurred_at": occurred_at,
        "correlation_id": str(payload.get("correlation_id") or source_event_id),
        "causation_id": source_event_id,
        "producer": "component.device-ingress",
        "payload": {
            "device_id": device_id,
            "twin_id": required_text(
                payload.get("twin_id") or device_id,
                code="INVALID_TWIN_ID",
            ),
            "metric": metric,
            "value": value,
            "unit": str(payload.get("unit") or "unspecified"),
            "event_time": occurred_at,
            "projection_candidate": payload.get("projection_candidate") is True,
        },
    }
    return validate_canonical_event(event)


def derive_event(
    source: Mapping[str, Any],
    *,
    event_type: str,
    producer: str,
    payload: Mapping[str, Any] | None = None,
    identity_suffix: str = "",
) -> dict[str, Any]:
    validate_canonical_event(source)
    identity = f"{source['event_id']}:{event_type}:{producer}"
    if identity_suffix:
        identity = f"{identity}:{identity_suffix}"
    child = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, identity)),
        "event_type": event_type,
        "deployment_id": source["deployment_id"],
        "source_id": source["source_id"],
        "source_sequence": source["source_sequence"],
        "occurred_at": source["occurred_at"],
        "correlation_id": source["correlation_id"],
        "causation_id": source["event_id"],
        "producer": producer,
        "payload": dict(payload if payload is not None else source["payload"]),
    }
    return validate_canonical_event(child)


def processor_extension_request(event: Mapping[str, Any]) -> dict[str, Any]:
    validate_canonical_event(event)
    body = event_body(event)
    unit = body.get("unit")
    if unit is not None and not isinstance(unit, str):
        raise ContractError("INVALID_PROCESSOR_UNIT")
    return {
        "schema_version": "user-function-runtime-envelope.v1",
        "invocation_id": event_id(event),
        "correlation_id": event["correlation_id"],
        "occurred_at": event["occurred_at"],
        "slot_id": "processor.telemetry",
        "payload": {
            "value": finite_number(body.get("value")),
            "unit": unit or "unspecified",
        },
        "context": {
            "device_id": partition_key(event),
            "twin_id": required_text(body.get("twin_id"), code="INVALID_TWIN_ID"),
        },
    }


def build_processed_event(
    source: Mapping[str, Any], extension_response: Mapping[str, Any]
) -> dict[str, Any]:
    request = processor_extension_request(source)
    if not isinstance(extension_response, Mapping) or set(extension_response) != {
        "schema_version",
        "invocation_id",
        "correlation_id",
        "slot_id",
        "status",
        "payload",
    }:
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)
    if (
        extension_response.get("schema_version")
        != "user-function-runtime-envelope.v1"
        or extension_response.get("invocation_id") != request["invocation_id"]
        or extension_response.get("correlation_id") != request["correlation_id"]
        or extension_response.get("slot_id") != "processor.telemetry"
        or extension_response.get("status") != "success"
    ):
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)
    result = extension_response.get("payload")
    if not isinstance(result, Mapping) or set(result) != {"value", "quality"}:
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)
    if result.get("quality") not in {"accepted", "suspect"}:
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)
    body = dict(event_body(source))
    body["value"] = finite_number(result.get("value"))
    body["quality"] = result["quality"]
    return derive_event(
        source,
        event_type=EVENT_TELEMETRY_PROCESSED,
        producer="component.telemetry-processor",
        payload=body,
    )


def raw_identity_digest(deployment_id: str, event_identifier: str) -> bytes:
    identity = (
        required_text(deployment_id, code="INVALID_DEPLOYMENT_ID").encode("utf-8")
        + b"\0"
        + required_text(event_identifier, code="INVALID_EVENT_ID").encode("utf-8")
    )
    return hashlib.sha256(identity).digest()


def raw_document_id(event: Mapping[str, Any]) -> str:
    validate_canonical_event(event)
    return raw_identity_digest(str(event["deployment_id"]), event_id(event)).hex()


def timestamp_shard(
    deployment_id: str, event_identifier: str, shard_count: int
) -> int:
    if shard_count not in {1, 16}:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    digest = raw_identity_digest(deployment_id, event_identifier)
    return int.from_bytes(digest[:4], "big") % shard_count


def raw_document(
    event: Mapping[str, Any],
    *,
    stored_at: datetime,
    hot_boundary_days: int,
    shard_count: int,
) -> dict[str, Any]:
    validate_canonical_event(event)
    if event.get("event_type") != EVENT_TELEMETRY_PROCESSED:
        raise ContractError("UNEXPECTED_HOT_STORAGE_EVENT")
    if hot_boundary_days < 1:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    body = event_body(event)
    device_id = partition_key(event)
    metric = required_text(body.get("metric"), code="INVALID_METRIC")
    value = finite_number(body.get("value"))
    stored_at = stored_at.astimezone(timezone.utc)
    storage_window = stored_at.replace(
        minute=stored_at.minute - stored_at.minute % 5,
        second=0,
        microsecond=0,
    )
    bucket_start = stored_at.replace(minute=0, second=0, microsecond=0)
    payload_digest = hashlib.sha256(
        canonical_json(dict(event)).encode("utf-8")
    ).hexdigest()
    return {
        "kind": "raw",
        "device_id": device_id,
        "event_id": event_id(event),
        "metric": metric,
        "value": value,
        "event_time": iso_time(parse_time(body.get("event_time") or event["occurred_at"])),
        "stored_at": stored_at,
        "storage_window": iso_time(storage_window),
        "bucket_start": bucket_start,
        "timestamp_shard": timestamp_shard(
            str(event["deployment_id"]), event_id(event), shard_count
        ),
        "payload_digest": payload_digest,
        "payload": dict(event),
        "expires_at": stored_at + timedelta(days=hot_boundary_days, hours=48),
    }


def rollup_document(
    raw: Mapping[str, Any], current: Mapping[str, Any] | None
) -> dict[str, Any]:
    value = finite_number(raw.get("value"))
    if current is None:
        count = 0
        total: int | float = 0
        minimum = value
        maximum = value
        version = 0
    else:
        if (
            current.get("kind") != "hourly_rollup"
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
            or isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise ContractError("INVALID_ROLLUP_STATE", 503)
        total = finite_number(current.get("sum"))
        minimum = finite_number(current.get("min"))
        maximum = finite_number(current.get("max"))
    return {
        "kind": "hourly_rollup",
        "device_id": raw["device_id"],
        "metric": raw["metric"],
        "bucket_start": raw["bucket_start"],
        "timestamp_shard": raw["timestamp_shard"],
        "count": count + 1,
        "sum": finite_number(total + value),
        "min": min(minimum, value),
        "max": max(maximum, value),
        "version": version + 1,
        "expires_at": raw["expires_at"],
    }


def rollup_document_id(raw: Mapping[str, Any]) -> str:
    identity = canonical_json(
        {
            "device_id": raw.get("device_id"),
            "metric": raw.get("metric"),
            "bucket_start": iso_time(raw["bucket_start"]),
        }
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def build_twin_projection(event: Mapping[str, Any]) -> dict[str, Any] | None:
    validate_canonical_event(event)
    body = event_body(event)
    if body.get("projection_candidate") is not True:
        return None
    metric = required_text(body.get("metric"), code="INVALID_METRIC")
    return derive_event(
        event,
        event_type=EVENT_TWIN_STATE_UPSERTED,
        producer="component.historical-persistence",
        payload={
            "twin_id": required_text(body.get("twin_id"), code="INVALID_TWIN_ID"),
            "source_id": partition_key(event),
            "source_sequence": str(event["source_sequence"]),
            "observed_at": iso_time(
                parse_time(body.get("event_time") or event["occurred_at"])
            ),
            "state_patch": {metric: finite_number(body.get("value"))},
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


def build_rule_matches(
    event: Mapping[str, Any], rules: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    validate_canonical_event(event)
    if event.get("event_type") != EVENT_TELEMETRY_PROCESSED:
        raise ContractError("UNEXPECTED_RULE_EVENT")
    if len(rules) > MAX_RULES or not all(isinstance(rule, Mapping) for rule in rules):
        raise ContractError("INVALID_RULE_CONFIGURATION", 503)
    body = event_body(event)
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, rule in enumerate(rules):
        action = rule.get("action")
        rule_id = required_text(
            rule.get("rule_id") or f"rule-{index + 1}",
            code="INVALID_RULE_CONFIGURATION",
        )
        if rule_id in seen or not isinstance(action, Mapping):
            raise ContractError("INVALID_RULE_CONFIGURATION", 503)
        seen.add(rule_id)
        condition = rule.get("condition")
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
            matched = comparisons[operator]()
        except TypeError as exc:
            raise ContractError("RULE_TYPE_MISMATCH") from exc
        if matched:
            matches.append(
                derive_event(
                    event,
                    event_type=EVENT_MATCHED,
                    producer="component.rule-evaluator",
                    payload={
                        **dict(body),
                        "rule_id": rule_id,
                        "condition": condition,
                        "action": dict(action),
                    },
                    identity_suffix=rule_id,
                )
            )
    return matches


def action_id(action: Mapping[str, Any], field: str = "functionName") -> str:
    if not isinstance(action, Mapping):
        raise ContractError("INVALID_ACTION_CONFIGURATION", 503)
    return required_text(
        action.get(field),
        code="INVALID_ACTION_CONFIGURATION",
        maximum=128,
    )


def firestore_document_id(value: object, *, code: str) -> str:
    """Map an unconstrained logical ID to one Firestore-safe document ID."""

    logical_id = required_text(value, code=code)
    return hashlib.sha256(logical_id.encode("utf-8")).hexdigest()


def parse_raw_history_query(
    params: Mapping[str, Any],
) -> tuple[dict[str, Any], datetime, datetime]:
    """Validate the closed and bounded raw-history request."""

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
        limit = int(params.get("limit", str(MAX_HISTORY_POINTS)))
    except (TypeError, ValueError) as exc:
        raise ContractError("INVALID_QUERY") from exc
    if bucket_seconds not in {0, 3600} or not 1 <= limit <= MAX_HISTORY_POINTS:
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


def encode_history_cursor(
    state: Mapping[str, Any],
    *,
    hmac_key: str,
    query_digest: str,
    deployment_id: str,
    now: datetime | None = None,
) -> str:
    if not isinstance(state, Mapping) or not state:
        raise ContractError("INVALID_CURSOR")
    current = now or datetime.now(timezone.utc)
    payload = {
        "profile": PROFILE,
        "provider": "gcp",
        "deployment": required_text(deployment_id, code="INVALID_DEPLOYMENT_ID"),
        "query": query_digest,
        "expires_at": int((current + CURSOR_MAX_AGE).timestamp()),
        "state": dict(state),
    }
    encoded = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    signature = hmac.new(
        _cursor_key(hmac_key), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    value = f"{encoded}.{signature}"
    if len(value.encode("utf-8")) > MAX_CURSOR_BYTES:
        raise ContractError("INVALID_CURSOR")
    return value


def decode_history_cursor(
    value: Any,
    *,
    hmac_key: str,
    query_digest: str,
    deployment_id: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if (
        not isinstance(value, str)
        or len(value.encode("utf-8")) > MAX_CURSOR_BYTES
        or "." not in value
    ):
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
    if (
        payload.get("profile") != PROFILE
        or payload.get("provider") != "gcp"
        or payload.get("deployment") != deployment_id
        or payload.get("query") != query_digest
    ):
        raise ContractError("INVALID_CURSOR")
    current = now or datetime.now(timezone.utc)
    if int(payload.get("expires_at", 0)) < int(current.timestamp()):
        raise ContractError("CURSOR_EXPIRED")
    state = payload.get("state")
    if not isinstance(state, dict) or not state:
        raise ContractError("INVALID_CURSOR")
    return state


def normalize_history_points(
    documents: list[Mapping[str, Any]], bucket_seconds: int
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []

    def normalized_time(value: Any) -> str:
        return iso_time(value) if isinstance(value, datetime) else iso_time(parse_time(value))

    if bucket_seconds == 0:
        for item in documents:
            points.append(
                {
                    "stored_at": normalized_time(item.get("stored_at")),
                    "event_time": normalized_time(item.get("event_time")),
                    "value": finite_number(item.get("value")),
                }
            )
        return points
    if bucket_seconds != 3600:
        raise ContractError("INVALID_QUERY")
    for item in documents:
        count = item.get("count")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= MAX_JSON_SAFE_INTEGER
        ):
            raise ContractError("INVALID_HISTORY_RECORD", 503)
        total = finite_number(item.get("sum"))
        points.append(
            {
                "bucket_start": normalized_time(item.get("bucket_start")),
                "min": finite_number(item.get("min")),
                "max": finite_number(item.get("max")),
                "avg": finite_number(total / count),
                "count": count,
            }
        )
    return points


def build_match_dispatch_events(
    event: Mapping[str, Any], *, action_accepted: bool
) -> list[dict[str, Any]]:
    """Derive the closed action, workflow, and command events for one match."""

    validate_canonical_event(event)
    if event.get("event_type") != EVENT_MATCHED:
        raise ContractError("INVALID_MATCH_EVENT")
    body = event_body(event)
    action = body.get("action")
    if not isinstance(action, Mapping):
        raise ContractError("INVALID_MATCH_EVENT")
    primary_action_id = action_id(action)
    derived = [
        derive_event(
            event,
            event_type=EVENT_ACTION_OUTCOME,
            producer="component.action-dispatcher",
            payload={
                "device_id": partition_key(event),
                "rule_id": body.get("rule_id"),
                "invocation_id": event_id(event),
                "action_id": primary_action_id,
                "status": "SUCCEEDED" if action_accepted else "FAILED",
            },
        )
    ]
    if action.get("type") in {"step_function", "logic_app", "workflow"}:
        derived.append(
            derive_event(
                event,
                event_type=EVENT_NOTIFICATION_REQUESTED,
                producer="component.action-dispatcher",
                payload={
                    "device_id": partition_key(event),
                    "rule_id": body.get("rule_id"),
                    "message": str(
                        action.get("message")
                        or body.get("condition")
                        or "Rule matched"
                    ),
                    "notification_action_id": action_id(action, "functionNameB"),
                },
            )
        )
    feedback = action.get("feedback")
    if isinstance(feedback, Mapping):
        derived.append(
            derive_event(
                event,
                event_type=EVENT_DEVICE_COMMAND_REQUESTED,
                producer="component.action-dispatcher",
                payload={
                    "device_id": required_text(
                        feedback.get("device_id")
                        or feedback.get("iotDeviceId")
                        or partition_key(event),
                        code="INVALID_COMMAND_DEVICE",
                    ),
                    "rule_id": body.get("rule_id"),
                    "message": str(feedback.get("payload") or "Rule matched"),
                },
            )
        )
    return derived


def outcome_document(
    event: Mapping[str, Any], *, stored_at: datetime, hot_boundary_days: int
) -> dict[str, Any]:
    validate_canonical_event(event)
    if event.get("event_type") not in OUTCOME_EVENT_TYPES:
        raise ContractError("UNEXPECTED_OUTCOME_EVENT")
    if hot_boundary_days < 1:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    stored_at = stored_at.astimezone(timezone.utc)
    payload_digest = hashlib.sha256(
        canonical_json(dict(event)).encode("utf-8")
    ).hexdigest()
    return {
        "kind": "outcome",
        "device_id": partition_key(event),
        "event_id": event_id(event),
        "event_type": event["event_type"],
        "stored_at": stored_at,
        "payload_digest": payload_digest,
        "payload": dict(event),
        "expires_at": stored_at + timedelta(days=hot_boundary_days, hours=48),
    }


def validate_twin_projection(event: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_canonical_event(event)
    kind = validated["event_type"]
    body = event_body(validated)
    expected_fields = {
        EVENT_TWIN_STATE_UPSERTED: {
            "twin_id",
            "source_id",
            "source_sequence",
            "observed_at",
            "state_patch",
        },
        EVENT_TWIN_MODEL_UPSERTED: {
            "model_id",
            "model_version",
            "model_document",
        },
        EVENT_TWIN_RELATIONSHIP_UPSERTED: {
            "relationship_id",
            "from_twin_id",
            "to_twin_id",
            "type",
        },
        EVENT_TWIN_RELATIONSHIP_DELETED: {
            "relationship_id",
            "from_twin_id",
            "to_twin_id",
            "type",
        },
    }
    if kind not in expected_fields or set(body) != expected_fields[kind]:
        raise ContractError("INVALID_TWIN_PROJECTION")
    if kind == EVENT_TWIN_STATE_UPSERTED:
        for field in ("twin_id", "source_id", "source_sequence"):
            required_text(body.get(field), code="INVALID_TWIN_PROJECTION")
        parse_time(body.get("observed_at"))
        patch = body.get("state_patch")
        if not isinstance(patch, Mapping) or not 1 <= len(patch) <= 32:
            raise ContractError("INVALID_TWIN_PROJECTION")
        for metric, value in patch.items():
            required_text(metric, code="INVALID_TWIN_PROJECTION")
            finite_number(value)
    elif kind == EVENT_TWIN_MODEL_UPSERTED:
        required_text(body.get("model_id"), code="INVALID_TWIN_PROJECTION")
        required_text(body.get("model_version"), code="INVALID_TWIN_PROJECTION")
        if not isinstance(body.get("model_document"), Mapping):
            raise ContractError("INVALID_TWIN_PROJECTION")
    else:
        for field in (
            "relationship_id",
            "from_twin_id",
            "to_twin_id",
            "type",
        ):
            required_text(body.get(field), code="INVALID_TWIN_PROJECTION")
    return validated


def projection_is_newer(
    current: Mapping[str, Any] | None, event: Mapping[str, Any]
) -> bool:
    """Apply observed-time ordering, then a stable source-sequence tie-break."""

    validated = validate_twin_projection(event)
    if current is None:
        return True
    if current.get("last_event_id") == event_id(validated):
        return False
    body = event_body(validated)
    observed_at = (
        body.get("observed_at")
        if validated["event_type"] == EVENT_TWIN_STATE_UPSERTED
        else validated["occurred_at"]
    )
    incoming_time = parse_time(observed_at)
    try:
        current_time = parse_time(current.get("last_observed_at"))
    except ContractError:
        raise ContractError("INVALID_TWIN_MATERIALIZATION_STATE", 503) from None
    if incoming_time != current_time:
        return incoming_time > current_time
    incoming_sequence = str(
        body.get("source_sequence") or validated.get("source_sequence")
    )
    current_sequence = required_text(
        current.get("last_source_sequence"),
        code="INVALID_TWIN_MATERIALIZATION_STATE",
    )

    def sequence_key(value: str) -> tuple[int, int | str]:
        if re.fullmatch(r"[0-9]{1,16}", value):
            return (1, int(value))
        return (0, value)

    incoming_key = (sequence_key(incoming_sequence), event_id(validated))
    current_key = (
        sequence_key(current_sequence),
        required_text(
            current.get("last_event_id"),
            code="INVALID_TWIN_MATERIALIZATION_STATE",
        ),
    )
    return incoming_key > current_key


def build_seed_twin_documents(
    devices: list[Mapping[str, Any]], *, deployment_id: str
) -> dict[str, dict[str, Any]]:
    """Build the deterministic, bounded L4 content required by the PoC."""

    deployment = required_text(deployment_id, code="INVALID_DEPLOYMENT_ID")
    if len(devices) > MAX_TWIN_ENTITIES or not all(
        isinstance(device, Mapping) for device in devices
    ):
        raise ContractError("INVALID_TWIN_SEED", 503)
    normalized = list(devices) or [{"id": "poc-device-001", "properties": []}]
    device_ids: list[str] = []
    documents: dict[str, dict[str, Any]] = {
        f"models/{firestore_document_id('Twin2MultiCloudPoCDevice', code='INVALID_TWIN_SEED')}": {
            "model_id": "Twin2MultiCloudPoCDevice",
            "model_version": "1",
            "model_document": {
                "display_name": "Twin2MultiCloud PoC Device",
                "description": "Bounded Five-layer v2 inspection model",
            },
            "last_observed_at": "1970-01-01T00:00:00.000000Z",
            "last_source_sequence": "0",
            "last_event_id": "seed-model-v1",
            "seed_revision": "gcp-l4-seed.v1",
        }
    }
    for device in sorted(normalized, key=lambda item: str(item.get("id", ""))):
        device_id = required_text(device.get("id"), code="INVALID_TWIN_SEED")
        if device_id in device_ids:
            raise ContractError("INVALID_TWIN_SEED", 503)
        device_ids.append(device_id)
        current_values: dict[str, Any] = {
            "provider": "gcp",
            "deployment": deployment,
            "status": "seeded",
        }
        properties = device.get("properties", [])
        if not isinstance(properties, list) or len(properties) > 32:
            raise ContractError("INVALID_TWIN_SEED", 503)
        for property_value in properties:
            if not isinstance(property_value, Mapping):
                raise ContractError("INVALID_TWIN_SEED", 503)
            name = required_text(
                property_value.get("name"), code="INVALID_TWIN_SEED"
            )
            initial = property_value.get("initValue")
            if initial is not None:
                current_values[name] = finite_number(initial)
        twin_document_id = firestore_document_id(device_id, code="INVALID_TWIN_SEED")
        documents[f"twins/{twin_document_id}"] = {
            "twin_id": device_id,
            "model_id": "Twin2MultiCloudPoCDevice",
            "updated_at": "1970-01-01T00:00:00.000000Z",
            "last_observed_at": "1970-01-01T00:00:00.000000Z",
            "last_source_sequence": "0",
            "last_event_id": f"seed-twin-{device_id}",
            "seed_revision": "gcp-l4-seed.v1",
        }
        source_document_id = firestore_document_id(
            "bootstrap", code="INVALID_TWIN_SEED"
        )
        documents[f"twins/{twin_document_id}/sources/{source_document_id}"] = {
            "source_id": "bootstrap",
            "current_values": current_values,
            "last_observed_at": "1970-01-01T00:00:00.000000Z",
            "last_source_sequence": "0",
            "last_event_id": f"seed-source-{device_id}",
            "seed_revision": "gcp-l4-seed.v1",
        }
    if len(device_ids) >= 2:
        relationship_id = f"seed-contains-{device_ids[0]}-{device_ids[1]}"
        relationship_document_id = firestore_document_id(
            relationship_id, code="INVALID_TWIN_SEED"
        )
        documents[f"relationships/{relationship_document_id}"] = {
            "relationship_id": relationship_id,
            "from_id": device_ids[0],
            "to_id": device_ids[1],
            "type": "contains",
            "deleted": False,
            "last_observed_at": "1970-01-01T00:00:00.000000Z",
            "last_source_sequence": "0",
            "last_event_id": f"seed-relationship-{relationship_id}",
            "seed_revision": "gcp-l4-seed.v1",
        }
    return documents
