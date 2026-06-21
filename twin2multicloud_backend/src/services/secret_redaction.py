"""Secret redaction helpers for user-facing downstream messages."""

from __future__ import annotations

import re
from typing import Any


def redact_validation_message(message: str, credentials: dict[str, Any]) -> str:
    """Redact credential values and common secret-looking tokens from downstream text."""
    redacted = message
    for secret in _credential_strings(credentials):
        if len(secret) >= 4:
            redacted = redacted.replace(secret, "[REDACTED]")

    redacted = re.sub(r"AKIA[0-9A-Z]{12,}", "[REDACTED]", redacted)
    redacted = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED]",
        redacted,
        flags=re.DOTALL,
    )
    return redacted


def redact_validation_payload(payload: Any, credentials: dict[str, Any]) -> Any:
    """Recursively redact downstream payload fragments that may be shown to users."""
    if isinstance(payload, str):
        return redact_validation_message(payload, credentials)
    if isinstance(payload, list):
        return [redact_validation_payload(item, credentials) for item in payload]
    if isinstance(payload, dict):
        return {key: redact_validation_payload(value, credentials) for key, value in payload.items()}
    return payload


def _credential_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result = []
        for child in value.values():
            result.extend(_credential_strings(child))
        return result
    if isinstance(value, (list, tuple, set)):
        result = []
        for child in value:
            result.extend(_credential_strings(child))
        return result
    return []
