"""Bounded Azure L5 raw-history verification for the active thesis PoC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from src.providers.azure.provider import AzureProvider


APP_SERVICE_API_VERSION = "2025-05-01"
FUNCTION_NAME = "six-layer-raw-history-reader"
KEY_NAME = "twin2multicloud-evaluation-reader"


def _management_token(provider: "AzureProvider") -> str:
    try:
        return provider.credential.get_token(
            "https://management.azure.com/.default"
        ).token
    except Exception as exc:
        raise RuntimeError("Azure management token was not created") from exc


def _function_url(
    provider: "AzureProvider", function_app_name: str, suffix: str
) -> str:
    return (
        "https://management.azure.com/subscriptions/"
        f"{provider.subscription_id}/resourceGroups/{provider.naming.resource_group()}"
        f"/providers/Microsoft.Web/sites/{function_app_name}"
        f"/functions/{FUNCTION_NAME}/{suffix}"
    )


def _require_status(response, allowed: tuple[int, ...], operation: str) -> None:
    if response.status_code not in allowed:
        raise RuntimeError(f"{operation} returned HTTP {response.status_code}")


def _reader_key(provider: "AzureProvider", function_app_name: str) -> str:
    """Create once or reuse the single evaluation-scoped Function key."""

    headers = {
        "Authorization": f"Bearer {_management_token(provider)}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        _function_url(provider, function_app_name, "listkeys")
        + f"?api-version={APP_SERVICE_API_VERSION}",
        headers=headers,
        timeout=30,
    )
    _require_status(response, (200,), "Azure Function key lookup")
    properties = response.json().get("properties", {})
    existing = properties.get(KEY_NAME) if isinstance(properties, dict) else None
    if isinstance(existing, str) and existing:
        return existing

    value = secrets.token_urlsafe(32)
    response = requests.put(
        _function_url(provider, function_app_name, f"keys/{KEY_NAME}")
        + f"?api-version={APP_SERVICE_API_VERSION}",
        headers=headers,
        json={"name": KEY_NAME, "value": value},
        timeout=30,
    )
    _require_status(response, (200, 201), "Azure Function key creation")
    return value


def verify_raw_history_reader(
    provider: "AzureProvider",
    *,
    endpoint: str,
    function_app_name: str,
    device_id: str,
    metric: str,
) -> None:
    """Verify both bounded query modes without provisioning a dashboard."""

    if not all((endpoint, function_app_name, device_id, metric)):
        raise ValueError("Azure raw-history verification inputs must be non-empty")
    key = _reader_key(provider, function_app_name)
    now = datetime.now(timezone.utc)
    for bucket, start in (
        (0, now - timedelta(hours=24)),
        (3600, now - timedelta(days=30)),
    ):
        response = requests.get(
            endpoint,
            headers={"x-functions-key": key},
            params={
                "device_id": device_id,
                "metric": metric,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": now.isoformat().replace("+00:00", "Z"),
                "bucket_seconds": str(bucket),
                "limit": "1",
            },
            timeout=30,
        )
        _require_status(response, (200,), "Azure raw-history query probe")
        if response.json().get("schema_version") != "raw-history-query.v1":
            raise RuntimeError(
                "Azure raw-history query probe returned an invalid contract"
            )
