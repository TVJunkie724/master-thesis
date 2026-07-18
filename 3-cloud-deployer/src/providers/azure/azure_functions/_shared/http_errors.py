"""Bounded HTTP error responses and diagnostics for Azure Function runtimes."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import azure.functions as func

from _shared.inter_cloud import redact_diagnostic


DEFAULT_INTERNAL_MESSAGE = "The request could not be completed."
MAX_DIAGNOSTIC_LENGTH = 512
MAX_PUBLIC_MESSAGE_LENGTH = 256
MAX_ERROR_CODE_LENGTH = 64

_SENSITIVE_ENV_NAME_PATTERN = re.compile(
    r"(?i)(?:authorization|credential|password|private|secret|token|"
    r"connection(?:_string)?|api[_-]?key|access[_-]?key|function[_-]?key|"
    r"client[_-]?key|client[_-]?secret|sas|signature|code)"
)
_SIGNED_QUERY_PATTERN = re.compile(
    r"(?i)([?&](?:code|sig|signature|token|key|api[_-]?key|"
    r"client[_-]?secret|access[_-]?token)=)[^&#\s\"']+"
)
_RUNTIME_PATH_PATTERN = re.compile(
    r"(?i)(?:"
    r"[a-z]:\\(?:home\\site\\wwwroot|local\\temp)(?:\\[^\s\"']*)?"
    r"|/(?:home/site/wwwroot|tmp|var/task)(?:/[^\s\"']*)?"
    r")"
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class InvalidRequestBody(ValueError):
    """Raised when an Azure HTTP request does not contain valid JSON."""


def parse_json_request(request: Any) -> Any:
    """Parse request JSON without propagating decoder or payload diagnostics."""
    try:
        return request.get_json()
    except (TypeError, ValueError):
        raise InvalidRequestBody("Request body must contain valid JSON") from None


def error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    correlation_id: str | None = None,
) -> func.HttpResponse:
    """Build the canonical bounded Azure runtime error response."""
    normalized_code = code.strip()
    if (
        not normalized_code
        or len(normalized_code) > MAX_ERROR_CODE_LENGTH
        or _ERROR_CODE_PATTERN.fullmatch(normalized_code) is None
    ):
        normalized_code = "INTERNAL_ERROR"

    normalized_message = _WHITESPACE_PATTERN.sub(" ", message).strip()
    if not normalized_message:
        normalized_message = DEFAULT_INTERNAL_MESSAGE

    error: dict[str, str] = {
        "code": normalized_code,
        "message": normalized_message[:MAX_PUBLIC_MESSAGE_LENGTH],
    }
    if correlation_id is not None:
        error["correlation_id"] = correlation_id
    return func.HttpResponse(
        json.dumps({"error": error}, separators=(",", ":")),
        status_code=status_code,
        mimetype="application/json",
    )


def redact_runtime_diagnostic(value: object) -> str:
    """Redact runtime secrets, signed URLs, and local paths from diagnostics."""
    text = str(value)
    sensitive_values = sorted(
        {
            env_value
            for env_name, env_value in os.environ.items()
            if (
                _SENSITIVE_ENV_NAME_PATTERN.search(env_name)
                and isinstance(env_value, str)
                and len(env_value) >= 6
            )
        },
        key=len,
        reverse=True,
    )
    for sensitive_value in sensitive_values:
        text = text.replace(sensitive_value, "<redacted>")

    text = redact_diagnostic(text)
    text = _SIGNED_QUERY_PATTERN.sub(r"\1<redacted>", text)
    text = _RUNTIME_PATH_PATTERN.sub("<runtime-path>", text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text[:MAX_DIAGNOSTIC_LENGTH]


def log_runtime_failure(
    component: str,
    error: BaseException,
    *,
    logger: Any = logging,
    include_diagnostic: bool = True,
) -> str:
    """Log one bounded failure reference and return its correlation ID."""
    correlation_id = str(uuid.uuid4())
    diagnostic = (
        redact_runtime_diagnostic(error)
        if include_diagnostic
        else "<suppressed>"
    )
    logger.error(
        "%s failed correlation_id=%s error_type=%s diagnostic=%s",
        component,
        correlation_id,
        type(error).__name__,
        diagnostic,
    )
    return correlation_id


def failure_response(
    *,
    component: str,
    error: BaseException,
    code: str = "INTERNAL_ERROR",
    message: str = DEFAULT_INTERNAL_MESSAGE,
    status_code: int = 500,
    logger: Any = logging,
) -> func.HttpResponse:
    """Log a redacted server failure and return its bounded public response."""
    correlation_id = log_runtime_failure(component, error, logger=logger)
    return error_response(
        code=code,
        message=message,
        status_code=status_code,
        correlation_id=correlation_id,
    )


def failure_reference(
    *,
    component: str,
    error: BaseException,
    code: str,
    logger: Any = logging,
) -> dict[str, str]:
    """Return a safe reference for one partial failure in a successful batch."""
    return {
        "status": "failed",
        "error_code": code,
        "correlation_id": log_runtime_failure(component, error, logger=logger),
    }
