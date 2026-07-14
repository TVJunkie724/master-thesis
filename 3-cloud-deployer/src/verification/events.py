"""Secret-safe Server-Sent Event serialization for verification."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from src.core.observability import redact_sensitive


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive(value)
    return value


def sse_event(event: str, data: dict) -> str:
    """Serialize one allowlisted event name and recursively redacted payload."""
    if event not in {"phase", "log", "done"}:
        raise ValueError(f"Unsupported verification event: {event}")
    payload = json.dumps(_sanitize(data), separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def display_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")

