"""Operation-scoped observability helpers for deployment flows."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import logging
import re
from time import perf_counter
from typing import Iterator
from uuid import uuid4


SECRET_KEY_PATTERN = re.compile(
    r"(?i)"
    r"(\b(?:aws_access_key_id|aws_secret_access_key|azure_client_secret|"
    r"client_secret|private_key|private_key_id|token|access_token|refresh_token|"
    r"password|secret|api_key|access_key|sharedaccesskey)\b)"
    r"([\"']?\s*[:=]\s*[\"']?)"
    r"([^\"',\s}\]]+)"
)
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)
AUTH_HEADER_PATTERN = re.compile(r"(?i)\b(authorization\s*[:=]\s*bearer\s+)([^\s,}]+)")
CONNECTION_STRING_SECRET_PATTERN = re.compile(r"(?i)\b(SharedAccessKey=)([^;,\s]+)")
UPLOAD_PATH_PATTERN = re.compile(r"(/[^\s:]+/upload/[^\s:]+)")
APP_UPLOAD_PATH_PATTERN = re.compile(r"(/app/upload/[^\s:]+)")
WORKSPACE_PATH_PATTERN = re.compile(r"(/[^\s:]+/twin2multicloud-deployer-workspaces/[^\s:]+)")


@dataclass(frozen=True)
class OperationContext:
    """Metadata that ties logs and client events to one deploy/destroy request."""

    operation: str
    project_name: str
    provider: str
    operation_id: str

    @classmethod
    def create(
        cls,
        *,
        operation: str,
        project_name: str,
        provider: str,
        operation_id: str | None = None,
    ) -> "OperationContext":
        return cls(
            operation=operation,
            project_name=project_name,
            provider=provider,
            operation_id=operation_id or uuid4().hex,
        )

    def with_provider(self, provider: str) -> "OperationContext":
        """Return a copy with the canonical provider value."""
        return replace(self, provider=provider)

    def log_extra(self, *, phase: str | None = None, **extra) -> dict:
        """Return structured logging metadata for standard logging `extra`."""
        metadata = {
            "operation_id": self.operation_id,
            "operation": self.operation,
            "project_name": self.project_name,
            "provider": self.provider,
        }
        if phase:
            metadata["phase"] = phase
        metadata.update(extra)
        return metadata


def redact_sensitive(value) -> str:
    """Redact paths and common secret fragments from a value converted to text."""
    text = str(value)
    text = PRIVATE_KEY_PATTERN.sub("<redacted-private-key>", text)
    text = AUTH_HEADER_PATTERN.sub(r"\1<redacted>", text)
    text = CONNECTION_STRING_SECRET_PATTERN.sub(r"\1<redacted>", text)
    text = SECRET_KEY_PATTERN.sub(r"\1\2<redacted>", text)
    text = UPLOAD_PATH_PATTERN.sub("<project-path>", text)
    text = APP_UPLOAD_PATH_PATTERN.sub("<project-path>", text)
    text = WORKSPACE_PATH_PATTERN.sub("<workspace-path>", text)
    return text


@contextmanager
def operation_step(
    logger: logging.Logger,
    operation_context: OperationContext,
    phase: str,
) -> Iterator[None]:
    """Log start/success/failure with duration for a deployment phase."""
    started_at = perf_counter()
    logger.info(
        "Deployment phase started: %s",
        phase,
        extra=operation_context.log_extra(phase=phase),
    )
    try:
        yield
    except Exception as exc:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.error(
            "Deployment phase failed: %s (%sms): %s",
            phase,
            duration_ms,
            redact_sensitive(exc),
            extra=operation_context.log_extra(
                phase=phase,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
            ),
        )
        raise
    else:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Deployment phase completed: %s (%sms)",
            phase,
            duration_ms,
            extra=operation_context.log_extra(phase=phase, duration_ms=duration_ms),
        )
