"""Secret redaction helpers for logs and client-facing diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any


REDACTED = "[REDACTED]"
_SECRET_FIELD_NAMES = (
    "aws_secret_access_key|secret_access_key|client_secret|private_key|"
    "session_token|access_token|refresh_token|id_token|api_key|password"
)  # nosec B105
_SECRET_JSON_FIELD_PATTERN = re.compile(
    rf'(?i)("({_SECRET_FIELD_NAMES})"\s*:\s*")[^"]+(")'
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    rf"(?i)\b({_SECRET_FIELD_NAMES})\b(\s*[=:]\s*)([^\s,;&]+)"
)
_AUTHORIZATION_HEADER_PATTERN = re.compile(
    r"(?i)(authorization\s*:\s*)(bearer\s+)?[^\s,;&]+"
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{10,}")
_GCP_PRIVATE_KEY_ID_PATTERN = re.compile(
    r'"private_key_id"\s*:\s*"[^"]+"'
)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    flags=re.DOTALL,
)


def redact_secret_like_text(
    value: Any,
    *,
    extra_secrets: Iterable[str] | None = None,
) -> str:
    """Redact known secret shapes and explicit credential values."""

    redacted = str(value)
    if extra_secrets:
        for secret in extra_secrets:
            if secret and len(secret) >= 4:
                redacted = redacted.replace(secret, REDACTED)

    redacted = re.sub(r"AKIA[0-9A-Z]{12,}", REDACTED, redacted)
    redacted = _PRIVATE_KEY_PATTERN.sub(REDACTED, redacted)
    redacted = _AUTHORIZATION_HEADER_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2) or ''}{REDACTED}",
        redacted,
    )
    redacted = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", redacted)
    redacted = _GCP_PRIVATE_KEY_ID_PATTERN.sub(
        f'"private_key_id": "{REDACTED}"', redacted
    )
    redacted = _SECRET_JSON_FIELD_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED}{match.group(3)}",
        redacted,
    )
    return _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        redacted,
    )


def credential_strings(value: Any) -> tuple[str, ...]:
    """Flatten credential payload values for exact-value redaction."""

    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            values.extend(credential_strings(nested))
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            values.extend(credential_strings(nested))
    return tuple(values)
