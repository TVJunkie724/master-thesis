"""Provider-state helpers for the canonical Cloud Connection contract."""

from typing import Any

from src.services.provider_contract import normalize_provider_id


def check_provider_configured(config: Any, provider: str) -> bool:
    """Return whether a provider has a bound deployment Cloud Connection."""
    field_name = f"{normalize_provider_id(provider)}_cloud_connection_id"
    return getattr(config, field_name, None) is not None


def get_configured_providers(config: Any) -> list[str]:
    """Return canonical uppercase provider IDs with deployment access."""
    return [
        provider.upper()
        for provider in ("aws", "azure", "gcp")
        if check_provider_configured(config, provider)
    ]
