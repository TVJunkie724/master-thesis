"""Provider-SDK status probes across configured layer owners."""

from __future__ import annotations

from typing import Any, Callable

from src.core.factory import create_context
from src.core.observability import redact_sensitive, redact_structure
from src.core.registry import ProviderRegistry


def _safe(value: Any) -> Any:
    return redact_structure(value)


def _component(status: str, provider: str, **details) -> dict[str, Any]:
    return {"status": status, "provider": provider, **_safe(details)}


def _initialize_provider(context, provider_name: str):
    if provider_name in context.providers:
        return context.providers[provider_name]
    credentials = context.credentials.get(provider_name, {})
    if not credentials and provider_name != "aws":
        raise ValueError(f"Credentials not configured for {provider_name}")
    provider = ProviderRegistry.get(provider_name)
    provider.initialize_clients(credentials, context.config.digital_twin_name)
    context.providers[provider_name] = provider
    return provider


def _probe(
    context,
    provider_name: str | None,
    method_name: str,
    *,
    configured: bool = True,
) -> dict[str, Any]:
    if not configured or not provider_name or provider_name == "none":
        return _component("not_configured", provider_name or "")
    try:
        provider = _initialize_provider(context, provider_name)
        method: Callable = getattr(provider, method_name)
        details = method(context)
        if details:
            return _component("deployed", provider_name, details=details)
        return _component("not_deployed", provider_name)
    except Exception as exc:
        return _component(
            "error",
            provider_name,
            message=redact_sensitive(exc),
        )


def check_sdk_managed(
    project_name: str,
    provider: str | None = None,
    *,
    context=None,
) -> dict[str, Any]:
    """Probe each component through the provider configured for its layer."""
    del provider  # Kept in the public contract for backward compatibility.
    try:
        context = context or create_context(project_name)
    except Exception as exc:
        return {
            "status": "error",
            "provider": "",
            "message": redact_sensitive(exc),
            "twin_management": _component("unknown", ""),
            "iot_devices": _component("unknown", ""),
            "visualization": _component("unknown", ""),
        }

    providers = context.config.providers
    l1 = providers.get("layer_1_provider")
    l4 = providers.get("layer_4_provider")
    l5 = providers.get("layer_5_provider")
    result = {
        "provider": "/".join(
            sorted({name for name in (l1, l4, l5) if name and name != "none"})
        ),
        "twin_management": _probe(context, l4, "info_l4"),
        "iot_devices": _probe(context, l1, "info_l1"),
        "visualization": _probe(context, l5, "info_l5"),
    }
    statuses = [component["status"] for component in result.values() if isinstance(component, dict)]
    if any(status == "error" for status in statuses):
        result["status"] = "error"
    elif all(status in {"deployed", "not_configured"} for status in statuses):
        result["status"] = "all_deployed"
    elif any(status == "deployed" for status in statuses):
        result["status"] = "partial"
    else:
        result["status"] = "not_deployed"
    return result
