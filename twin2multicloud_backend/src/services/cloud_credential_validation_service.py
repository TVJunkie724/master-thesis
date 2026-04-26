"""Shared validation calls for cloud credential payloads."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from src.config import settings

_SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "credentials",
    "credential",
    "service_account_json",
    "gcp_credentials_file",
    "aws_access_key_id",
    "aws_secret_access_key",
    "azure_client_secret",
)
_REDACTION = "[REDACTED]"


async def perform_dual_validation(
    provider: str,
    optimizer_creds: dict,
    deployer_creds: dict,
) -> dict:
    """Validate credentials against Optimizer and Deployer without persisting secrets."""

    async def call_optimizer():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OPTIMIZER_URL}/permissions/verify/{provider}",
                    json=optimizer_creds,
                    timeout=30.0,
                )
                if response.status_code == 200:
                    result = response.json()
                    is_valid = result.get("valid", False) or result.get("status") == "valid"
                    return {
                        "valid": is_valid,
                        "message": result.get("message", "Validation complete"),
                    }
                return {
                    "valid": False,
                    "message": f"Optimizer API error: {response.status_code}",
                }
        except httpx.ConnectError:
            return {
                "valid": False,
                "message": "Cannot connect to Optimizer API (port 5003)",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"Optimizer error: {exc}",
            }

    async def call_deployer():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                    json=deployer_creds,
                    timeout=30.0,
                )
                if response.status_code == 200:
                    result = response.json()
                    is_valid = result.get("valid", False) or result.get("status") == "valid"
                    return {
                        "valid": is_valid,
                        "message": result.get("message", "Validation complete"),
                        "permissions": result.get("missing_permissions"),
                    }
                return {
                    "valid": False,
                    "message": f"Deployer API error: {response.status_code}",
                }
        except httpx.ConnectError:
            return {
                "valid": False,
                "message": "Cannot connect to Deployer API (port 5004)",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"Deployer error: {exc}",
            }

    optimizer_result, deployer_result = await asyncio.gather(call_optimizer(), call_deployer())

    result = {
        "provider": provider,
        "valid": optimizer_result.get("valid", False) and deployer_result.get("valid", False),
        "optimizer": optimizer_result,
        "deployer": deployer_result,
    }
    return redact_validation_result(result, optimizer_creds, deployer_creds)


def redact_validation_result(result: dict[str, Any], *credential_payloads: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a validation result with credential values removed."""
    sensitive_values = _collect_sensitive_values(*credential_payloads)
    return _redact_value(result, sensitive_values)


def _collect_sensitive_values(*credential_payloads: dict[str, Any]) -> set[str]:
    sensitive_values: set[str] = set()
    for payload in credential_payloads:
        _collect_from_mapping(payload, sensitive_values)
    return sensitive_values


def _collect_from_mapping(value: Any, sensitive_values: set[str], parent_key: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            is_sensitive = _is_sensitive_key(key_text) or _is_sensitive_key(parent_key)
            if is_sensitive and isinstance(item, str):
                _add_sensitive_value(item, sensitive_values)
                _collect_json_secrets(item, sensitive_values)
            _collect_from_mapping(item, sensitive_values, key_text)
        return

    if isinstance(value, list):
        for item in value:
            _collect_from_mapping(item, sensitive_values, parent_key)
        return

    if _is_sensitive_key(parent_key) and isinstance(value, str):
        _add_sensitive_value(value, sensitive_values)
        _collect_json_secrets(value, sensitive_values)


def _collect_json_secrets(raw: str, sensitive_values: set[str]) -> None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    _collect_from_mapping(parsed, sensitive_values)


def _redact_value(value: Any, sensitive_values: set[str], parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_value(item, sensitive_values, str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, sensitive_values, parent_key) for item in value]
    if isinstance(value, str):
        if _is_sensitive_key(parent_key):
            return _REDACTION
        return _redact_string(value, sensitive_values)
    return value


def _redact_string(value: str, sensitive_values: set[str]) -> str:
    redacted = value
    for sensitive_value in sorted(sensitive_values, key=len, reverse=True):
        if sensitive_value:
            redacted = redacted.replace(sensitive_value, _REDACTION)
    return redacted


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _add_sensitive_value(value: str, sensitive_values: set[str]) -> None:
    if len(value) >= 8:
        sensitive_values.add(value)
