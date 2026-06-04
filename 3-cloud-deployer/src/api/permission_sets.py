"""Versioned provider permission-set contract for deployment identities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProviderName = Literal["aws", "azure", "gcp"]
PermissionSetStatus = Literal["matched", "missing", "outdated"]

ACTIVE_PERMISSION_SET_VERSION = "thesis-demo-v1"


@dataclass(frozen=True)
class PermissionSetComparison:
    provider: ProviderName
    expected_version: str
    supplied_version: str | None
    status: PermissionSetStatus

    @property
    def matches(self) -> bool:
        return self.status == "matched"


def active_permission_set_version(provider: ProviderName) -> str:
    """Return the active deployment permission-set version for a provider."""
    if provider not in {"aws", "azure", "gcp"}:
        raise ValueError(f"Unsupported provider: {provider}")
    return ACTIVE_PERMISSION_SET_VERSION


def compare_permission_set_version(
    provider: ProviderName,
    supplied_version: str | None,
) -> PermissionSetComparison:
    """Compare request/CloudConnection metadata with the active baseline."""
    expected = active_permission_set_version(provider)
    if not supplied_version:
        status: PermissionSetStatus = "missing"
    elif supplied_version == expected:
        status = "matched"
    else:
        status = "outdated"
    return PermissionSetComparison(
        provider=provider,
        expected_version=expected,
        supplied_version=supplied_version,
        status=status,
    )
