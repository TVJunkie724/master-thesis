"""Stable, bounded errors for the deployment specification boundary."""

from __future__ import annotations


class DeploymentSpecificationError(ValueError):
    """Reject an unsafe or incompatible specification without echoing values."""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code} [{field}]: {message}")
