"""Stable, bounded errors for the deployment specification boundary."""

from __future__ import annotations

import secrets


class DeploymentSpecificationError(ValueError):
    """Reject an unsafe or incompatible specification without echoing values."""

    def __init__(
        self,
        code: str,
        field: str,
        message: str,
        *,
        correlation_id: str | None = None,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        self.correlation_id = correlation_id or secrets.token_hex(16)
        super().__init__(f"{code} [{field}] ({self.correlation_id}): {message}")
