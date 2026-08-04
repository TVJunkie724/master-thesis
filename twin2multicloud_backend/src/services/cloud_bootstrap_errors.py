"""Stable, secret-safe guided bootstrap domain errors."""

from __future__ import annotations


class CloudBootstrapDomainError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int = 422,
        fix_suggestion: str = "Reload the bootstrap session and follow its current action.",
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.fix_suggestion = fix_suggestion
        super().__init__(message)
