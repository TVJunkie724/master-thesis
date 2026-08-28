"""Small, payload-free diagnostic checkpoint contract for live PoC traces."""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, Mapping


CHECKPOINT_PREFIX = "T2MC_CHECKPOINT "
CHECKPOINT_STAGES = frozenset(
    {
        "l1_accepted",
        "event_layer_durable",
        "l2_started",
        "l2_completed",
        "l3_hot_persisted",
        "l4_queryable",
        "l5_queryable",
        "command_issued",
        "event_layer_command_durable",
        "l1_command_published",
        "outcome_event_durable",
        "outcome_persisted",
        "outcome_queryable",
    }
)
_TRACE_ID = re.compile(r"^(?:TRACE|VERIFY)-[A-Z0-9]{8,48}$")
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,159}$")
_ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "trace_id",
        "stage",
        "provider",
        "component",
        "status",
        "observed_at",
        "event_id",
        "event_type",
        "error_code",
    }
)


def parse_checkpoint_message(value: object) -> dict[str, Any] | None:
    """Extract one valid checkpoint from plain or provider-wrapped log text."""
    message = _message_text(value)
    marker = message.find(CHECKPOINT_PREFIX)
    if marker < 0:
        return None
    raw = message[marker + len(CHECKPOINT_PREFIX) :].strip()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return _validate_checkpoint(payload)


def _message_text(value: object) -> str:
    if isinstance(value, Mapping):
        candidate = value.get("message") or value.get("msg")
        return candidate if isinstance(candidate, str) else json.dumps(value)
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    if stripped.startswith("{"):
        try:
            wrapped = json.loads(stripped)
        except json.JSONDecodeError:
            return value
        if isinstance(wrapped, Mapping):
            candidate = wrapped.get("message") or wrapped.get("msg")
            if isinstance(candidate, str):
                return candidate
    return value


def _validate_checkpoint(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or not set(value).issubset(_ALLOWED_KEYS):
        return None
    required = {
        "schema_version",
        "trace_id",
        "stage",
        "provider",
        "component",
        "status",
        "observed_at",
    }
    if not required.issubset(value):
        return None
    if value.get("schema_version") != "diagnostic-checkpoint.v1":
        return None
    if not isinstance(value.get("trace_id"), str) or not _TRACE_ID.fullmatch(
        value["trace_id"]
    ):
        return None
    if value.get("stage") not in CHECKPOINT_STAGES:
        return None
    if value.get("provider") not in {"aws", "azure", "gcp"}:
        return None
    if value.get("status") not in {"passed", "failed"}:
        return None
    try:
        parsed = datetime.fromisoformat(str(value["observed_at"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    for key in ("component", "event_id", "event_type", "error_code"):
        candidate = value.get(key)
        if candidate is not None and (
            not isinstance(candidate, str) or not _SAFE_TEXT.fullmatch(candidate)
        ):
            return None
    return dict(value)


__all__ = ["CHECKPOINT_PREFIX", "CHECKPOINT_STAGES", "parse_checkpoint_message"]
