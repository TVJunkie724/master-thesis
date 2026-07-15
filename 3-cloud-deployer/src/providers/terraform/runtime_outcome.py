"""Typed outcome aggregation for SDK-owned post-deployment resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TypeVar

from src.api.deployment_trace import sanitize_deployment_message
from src.core.deployment_errors import DeploymentBoundaryError


@dataclass(frozen=True)
class RuntimeFailure:
    """One sanitized SDK-owned resource failure."""

    operation: str
    resource: str
    error_type: str
    detail: str


class ProviderRuntimeError(DeploymentBoundaryError):
    """Raised when post-deployment provider resources are incomplete."""

    def __init__(self, provider: str, failures: tuple[RuntimeFailure, ...]) -> None:
        self.provider = provider
        self.failures = failures
        visible = failures[:5]
        summary = "; ".join(
            f"{failure.operation}/{failure.resource}: {failure.detail}"
            for failure in visible
        )
        if len(failures) > len(visible):
            summary += f"; and {len(failures) - len(visible)} more failures"
        super().__init__(f"{provider} post-deployment incomplete: {summary}")


_Result = TypeVar("_Result")


class RuntimeRun:
    """Collect independent SDK resource failures without hiding partial work."""

    def __init__(self, provider: str, operation: str, logger: logging.Logger) -> None:
        self.provider = provider
        self.operation = operation
        self.logger = logger
        self._failures: list[RuntimeFailure] = []

    @property
    def failures(self) -> tuple[RuntimeFailure, ...]:
        return tuple(self._failures)

    def attempt(
        self,
        resource: str,
        action: Callable[[], _Result],
        *,
        default: _Result | None = None,
    ) -> _Result | None:
        try:
            return action()
        except Exception as exc:
            detail = sanitize_deployment_message(str(exc) or exc.__class__.__name__)
            failure = RuntimeFailure(
                operation=self.operation,
                resource=sanitize_deployment_message(str(resource)),
                error_type=exc.__class__.__name__,
                detail=detail,
            )
            self._failures.append(failure)
            self.logger.error(
                "%s failed for %s (%s): %s",
                failure.operation,
                failure.resource,
                failure.error_type,
                failure.detail,
            )
            return default

    def raise_if_failed(self) -> None:
        if self._failures:
            raise ProviderRuntimeError(self.provider, self.failures)
