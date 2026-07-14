"""Fail-closed observability adapter for legacy provider cleanup implementations."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import re

from src.api.deployment_trace import sanitize_deployment_message

_FAILURE_PATTERN = re.compile(
    r"\b(error|failed|failure|timeout|not found|could not|unable to)\b",
    re.IGNORECASE,
)


class ProviderCleanupError(RuntimeError):
    """Raised when a provider reports one or more incomplete cleanup steps."""


class _CleanupLogGuard(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.failures: list[str] = []

    def filter(self, record: logging.LogRecord) -> bool:
        original = record.getMessage()
        if record.levelno >= logging.WARNING and _FAILURE_PATTERN.search(original):
            self.failures.append(sanitize_deployment_message(original))
        record.msg = sanitize_deployment_message(original)
        record.args = ()
        return True

@contextmanager
def enforce_cleanup_outcome(provider_logger: logging.Logger, provider: str):
    """Redact provider logs and convert swallowed cleanup failures to an error."""
    guard = _CleanupLogGuard()
    provider_logger.addFilter(guard)
    try:
        yield
    finally:
        provider_logger.removeFilter(guard)

    if guard.failures:
        unique_failures = list(dict.fromkeys(guard.failures))
        summary = "; ".join(unique_failures[:5])
        if len(unique_failures) > 5:
            summary += f"; and {len(unique_failures) - 5} more failures"
        raise ProviderCleanupError(f"{provider} cleanup incomplete: {summary}")
