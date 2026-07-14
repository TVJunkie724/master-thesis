"""Secret-safe Server-Sent Event serialization for verification."""

from __future__ import annotations

from datetime import datetime
import json
from src.core.observability import redact_structure


def sse_event(event: str, data: dict) -> str:
    """Serialize one allowlisted event name and recursively redacted payload."""
    if event not in {"phase", "log", "done"}:
        raise ValueError(f"Unsupported verification event: {event}")
    payload = json.dumps(redact_structure(data), separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def display_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")
