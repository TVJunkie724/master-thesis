"""Provider identifier contract between Management API, Optimizer, and Deployer."""

from __future__ import annotations

from typing import Optional

CANONICAL_PROVIDERS = frozenset({"aws", "azure", "gcp"})
PROVIDER_ALIASES = {
    "aws": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "google": "gcp",
}


def normalize_provider_id(value: str) -> str:
    """Return the Management/Optimizer canonical provider id."""
    normalized = PROVIDER_ALIASES.get(value.strip().lower())
    if not normalized:
        raise ValueError(f"Unsupported provider: {value}")
    return normalized


def normalize_optional_provider_id(value: Optional[str]) -> Optional[str]:
    """Normalize an optional provider id without turning empty values into providers."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return normalize_provider_id(stripped)


def provider_id_for_deployer_project(value: Optional[str]) -> Optional[str]:
    """Return the provider id expected inside Deployer project config files."""
    normalized = normalize_optional_provider_id(value)
    if normalized == "gcp":
        return "google"
    return normalized


def provider_id_for_deployer_api(value: Optional[str]) -> str:
    """Return the provider id expected by Deployer API query/path parameters."""
    return normalize_optional_provider_id(value) or "aws"


def is_gcp_provider(value: Optional[str]) -> bool:
    """Return true for every accepted GCP spelling."""
    return normalize_optional_provider_id(value) == "gcp"
