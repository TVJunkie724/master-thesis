"""Platform-owned runtime boundary embedded into extension packages."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
import signal
import sys
import threading
import time
import uuid

from process import process


_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SECRET_KEY = re.compile(
    r"(?:^|[_-])(?:secret|password|token|credential|private[_-]?key|"
    r"access[_-]?key|api[_-]?key|client[_-]?secret|connection[_-]?string)"
    r"(?:$|[_-])",
    re.IGNORECASE,
)
_SECRET_VALUES = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{24,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\."),
    re.compile(
        r"\b(?:password|token|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]{4,}",
        re.IGNORECASE,
    ),
)
_CONFIG = json.loads(
    (Path(__file__).resolve().parent / "_extension_config.json").read_text(
        encoding="utf-8"
    )
)


class _InvocationTimedOut(BaseException):
    pass


def invoke(envelope):
    base = _base(envelope)
    try:
        _validate_input(envelope)
        result = _invoke_with_timeout(
            dict(envelope["payload"]),
            dict(_CONFIG["configuration"]),
            dict(envelope["context"]),
        )
        if not isinstance(result, dict):
            return _rejected(base)
        _validate_schema(_CONFIG["output_schema"], result)
        response = {**base, "status": "success", "payload": result}
        if (
            _contains_secret(response)
            or len(_canonical(response)) > _CONFIG["response_bytes"]
        ):
            return _rejected(base)
        return response
    except (KeyError, TypeError, ValueError):
        return _rejected(base)
    except _InvocationTimedOut:
        return {
            **base,
            "status": "failed",
            "code": "PLATFORM_EXTENSION_TIMEOUT",
            "message": "The extension exceeded its duration limit.",
            "retryable": False,
        }
    except Exception:
        return {
            **base,
            "status": "failed",
            "code": "PLATFORM_EXTENSION_FAILED",
            "message": "The extension could not be completed.",
            "retryable": False,
        }


def _invoke_with_timeout(payload, configuration, context):
    timeout_seconds = float(_CONFIG["timeout_seconds"])
    if timeout_seconds <= 0:
        raise _InvocationTimedOut
    if threading.current_thread() is not threading.main_thread():
        return _invoke_with_trace_timeout(
            payload,
            configuration,
            context,
            timeout_seconds,
        )

    def _timeout(_signum, _frame):
        raise _InvocationTimedOut

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return process(payload, configuration, context)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _invoke_with_trace_timeout(
    payload,
    configuration,
    context,
    timeout_seconds,
):
    deadline = time.monotonic() + timeout_seconds
    previous_trace = sys.gettrace()

    def _trace(_frame, _event, _argument):
        if time.monotonic() >= deadline:
            raise _InvocationTimedOut
        return _trace

    sys.settrace(_trace)
    try:
        result = process(payload, configuration, context)
        if time.monotonic() >= deadline:
            raise _InvocationTimedOut
        return result
    finally:
        sys.settrace(previous_trace)


def _base(envelope):
    if not isinstance(envelope, dict):
        envelope = {}
    invocation_id = envelope.get("invocation_id")
    correlation_id = envelope.get("correlation_id")
    slot_id = envelope.get("slot_id")
    return {
        "schema_version": "user-function-runtime-envelope.v1",
        "invocation_id": invocation_id if _safe(invocation_id) else _CONFIG["fallback_id"],
        "correlation_id": (
            correlation_id if _safe(correlation_id) else _CONFIG["fallback_id"]
        ),
        "slot_id": slot_id if _safe(slot_id) else _CONFIG["slot_id"],
    }


def _validate_input(envelope):
    if not isinstance(envelope, dict):
        raise ValueError("invalid envelope")
    if set(envelope) != {
        "schema_version",
        "invocation_id",
        "correlation_id",
        "occurred_at",
        "slot_id",
        "payload",
        "context",
    }:
        raise ValueError("invalid fields")
    if envelope["schema_version"] != "user-function-runtime-envelope.v1":
        raise ValueError("invalid version")
    if envelope["slot_id"] != _CONFIG["slot_id"]:
        raise ValueError("invalid slot")
    if not _uuid(envelope["invocation_id"]) or not _safe(envelope["correlation_id"]):
        raise ValueError("invalid identity")
    _date_time(envelope["occurred_at"])
    if not isinstance(envelope["payload"], dict) or not isinstance(
        envelope["context"], dict
    ):
        raise ValueError("invalid body")
    if set(envelope["context"]) != {"twin_id", "device_id"}:
        raise ValueError("invalid context")
    if not all(_safe(value) for value in envelope["context"].values()):
        raise ValueError("invalid context identity")
    _validate_schema(_CONFIG["input_schema"], envelope["payload"])
    if _contains_secret(envelope):
        raise ValueError("secret material")


def _safe(value):
    return isinstance(value, str) and _SAFE_ID.fullmatch(value) is not None


def _uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError):
        return False


def _date_time(value):
    if not isinstance(value, str):
        raise ValueError("invalid date-time")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("invalid date-time")


def _contains_secret(value):
    if isinstance(value, dict):
        return any(
            _SECRET_KEY.search(str(key)) is not None or _contains_secret(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) is not None for pattern in _SECRET_VALUES)
    return False


def _validate_schema(schema, value):
    if not isinstance(value, dict):
        raise ValueError("invalid schema value")
    properties = schema["properties"]
    if set(value) - set(properties) or set(schema["required"]) - set(value):
        raise ValueError("invalid schema fields")
    for name, child in value.items():
        field = properties[name]
        expected = field["type"]
        if expected == "string":
            valid = isinstance(child, str)
        elif expected == "integer":
            valid = isinstance(child, int) and not isinstance(child, bool)
        elif expected == "number":
            valid = isinstance(child, (int, float)) and not isinstance(child, bool)
        elif expected == "boolean":
            valid = isinstance(child, bool)
        elif expected == "object":
            valid = isinstance(child, dict)
        elif expected == "array":
            valid = isinstance(child, list)
        else:
            valid = False
        if not valid:
            raise ValueError("invalid schema type")
        if "enum" in field and child not in field["enum"]:
            raise ValueError("invalid enum")
        if isinstance(child, str):
            if len(child) < field.get("minLength", 0):
                raise ValueError("string too short")
            if len(child) > field.get("maxLength", len(child)):
                raise ValueError("string too long")
            if "pattern" in field and re.fullmatch(field["pattern"], child) is None:
                raise ValueError("invalid pattern")
        if isinstance(child, (int, float)) and not isinstance(child, bool):
            if child < field.get("minimum", child):
                raise ValueError("number too small")
            if child > field.get("maximum", child):
                raise ValueError("number too large")


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _rejected(base):
    return {
        **base,
        "status": "rejected",
        "code": "DOMAIN_OUTPUT_INVALID",
        "message": "The extension input or result is invalid.",
    }
