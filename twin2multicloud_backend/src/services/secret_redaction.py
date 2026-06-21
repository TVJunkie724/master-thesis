"""Secret redaction helpers for user-facing downstream messages."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


SECRET_FIELD_NAMES = (
    "aws_secret_access_key|secret_access_key|client_secret|private_key|"
    "session_token|access_token|refresh_token|id_token|api_key|password"
)
SECRET_JSON_FIELD_PATTERN = re.compile(rf'(?i)("({SECRET_FIELD_NAMES})"\s*:\s*")[^"]+(")')
SECRET_ASSIGNMENT_PATTERN = re.compile(rf"(?i)\b({SECRET_FIELD_NAMES})\b(\s*[=:]\s*)([^\s,;&]+)")
AUTHORIZATION_HEADER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*)(bearer\s+)?[^\s,;&]+")

BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{10,}")
GCP_PRIVATE_KEY_ID_PATTERN = re.compile(r"\"private_key_id\"\s*:\s*\"[^\"]+\"")


def redact_validation_message(message: str, credentials: dict[str, Any]) -> str:
    """Redact credential values and common secret-looking tokens from downstream text."""
    redacted = redact_secret_like_text(message)
    for secret in _credential_strings(credentials):
        if len(secret) >= 4:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redact_secret_like_text(redacted)


def redact_secret_like_text(message: str, extra_secrets: Iterable[str] | None = None) -> str:
    """Redact common secret-looking fragments from arbitrary user-facing text."""
    redacted = message
    if extra_secrets:
        for secret in extra_secrets:
            if secret and len(secret) >= 4:
                redacted = redacted.replace(secret, "[REDACTED]")

    redacted = re.sub(r"AKIA[0-9A-Z]{12,}", "[REDACTED]", redacted)
    redacted = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED]",
        redacted,
        flags=re.DOTALL,
    )
    redacted = AUTHORIZATION_HEADER_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2) or ''}[REDACTED]",
        redacted,
    )
    redacted = BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)
    redacted = GCP_PRIVATE_KEY_ID_PATTERN.sub('"private_key_id": "[REDACTED]"', redacted)
    redacted = SECRET_JSON_FIELD_PATTERN.sub(lambda match: f"{match.group(1)}[REDACTED]{match.group(3)}", redacted)
    return SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted)


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
