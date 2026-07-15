"""Typed, redacted outcome handling for destructive provider cleanup."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from collections.abc import Callable
from typing import TypeVar

from src.api.deployment_trace import sanitize_deployment_message

@dataclass(frozen=True)
class CleanupFailure:
    """One sanitized provider cleanup failure."""

    step: str
    resource: str
    error_type: str
    detail: str


class ProviderCleanupError(RuntimeError):
    """Raised when a provider reports one or more incomplete cleanup steps."""

    def __init__(self, provider: str, failures: tuple[CleanupFailure, ...]) -> None:
        self.provider = provider
        self.failures = failures
        visible = failures[:5]
        summary = "; ".join(
            f"{failure.step}/{failure.resource}: {failure.detail}"
            for failure in visible
        )
        if len(failures) > len(visible):
            summary += f"; and {len(failures) - len(visible)} more failures"
        super().__init__(f"{provider} cleanup incomplete: {summary}")


_Result = TypeVar("_Result")


class CleanupRun:
    """Execute independent cleanup operations and aggregate explicit failures."""

    def __init__(self, provider: str, provider_logger: logging.Logger) -> None:
        self.provider = provider
        self.logger = provider_logger
        self._failures: list[CleanupFailure] = []

    @property
    def failures(self) -> tuple[CleanupFailure, ...]:
        return tuple(self._failures)

    def attempt(
        self,
        step: str,
        resource: str,
        operation: Callable[[], _Result],
        *,
        default: _Result | None = None,
    ) -> _Result | None:
        """Run one operation, recording a redacted failure without stopping siblings."""
        try:
            return operation()
        except Exception as exc:
            self.record(step, resource, exc)
            return default

    def record(self, step: str, resource: str, exc: Exception) -> None:
        detail = sanitize_deployment_message(str(exc) or exc.__class__.__name__)
        failure = CleanupFailure(
            step=step,
            resource=sanitize_deployment_message(str(resource)),
            error_type=exc.__class__.__name__,
            detail=detail,
        )
        self._failures.append(failure)
        self.logger.warning(
            "%s cleanup failed for %s (%s): %s",
            failure.step,
            failure.resource,
            failure.error_type,
            failure.detail,
        )

    def raise_if_failed(self) -> None:
        if self._failures:
            raise ProviderCleanupError(self.provider, self.failures)
