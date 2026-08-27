"""Shared validation calls for cloud credential payloads."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.clients.deployer_client import DeployerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable

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
logger = logging.getLogger(__name__)


async def perform_deployer_validation(
    provider: str,
    deployer_creds: dict,
    *,
    deployer_client: DeployerClient | None = None,
) -> dict:
    """Validate admin credentials at the sole cloud-mutating service boundary."""
    deployer_client = deployer_client or DeployerClient()
    try:
        result = await deployer_client.verify_permissions(provider, deployer_creds)
        deployer_result = {
            "valid": (
                bool(result.get("valid"))
                or bool(result.get("ready"))
                or result.get("status") in {"valid", "passed"}
            ),
            "message": result.get("summary")
            or result.get("message", "Validation complete"),
            "checks": result.get("checks") or [],
            "permissions": result.get("missing_permissions") or [],
        }
    except ExternalServiceUnavailable:
        deployer_result = {
            "valid": False,
            "message": "Cannot connect to Deployer API (port 5004)",
        }
    except ExternalServiceError as exc:
        deployer_result = {
            "valid": False,
            "message": f"Deployer API error: {exc.upstream_status_code or 502}",
        }
    except Exception as exc:  # noqa: BLE001 - external adapter boundary
        logger.error(
            "Unexpected Deployer credential validation failure for %s (%s)",
            provider,
            type(exc).__name__,
        )
        deployer_result = {
            "valid": False,
            "message": "Deployer validation failed unexpectedly",
        }

    result = {
        "provider": provider,
        "valid": deployer_result.get("valid", False),
        "deployer": deployer_result,
    }
    return redact_validation_result(result, deployer_creds)


def redact_validation_result(
    result: dict[str, Any], *credential_payloads: dict[str, Any]
) -> dict[str, Any]:
    """Return a copy of a validation result with credential values removed."""
    sensitive_values = _collect_sensitive_values(*credential_payloads)
    return _redact_value(result, sensitive_values)


def build_preflight_result(
    provider: str,
    validation_result: dict[str, Any],
) -> dict[str, Any]:
    """Normalize Deployer validation into UI-actionable preflight checks."""
    checks = []
    deployer = validation_result.get("deployer")
    detailed = deployer.get("checks") if isinstance(deployer, dict) else None
    if isinstance(detailed, list) and detailed:
        checks.extend(
            _build_deployer_check(item)
            for item in detailed[:32]
            if isinstance(item, dict)
        )
    else:
        checks.append(_build_component_check("deployer", deployer))
    ready = all(check["status"] == "passed" for check in checks)
    return {
        "provider": provider,
        "ready": ready,
        "summary": "Cloud connection preflight passed"
        if ready
        else "Cloud connection preflight failed",
        "checks": checks,
    }


def _build_deployer_check(raw: dict[str, Any]) -> dict[str, Any]:
    status = str(raw.get("status") or "failed")
    permissions = raw.get("permissions") or []
    apis = raw.get("apis") or []
    return {
        "component": f"deployer.{(raw.get('name') or 'provider')!s}",
        "status": "passed" if status in {"passed", "warning", "skipped"} else "failed",
        "code": str(raw.get("code") or "VALIDATION_FAILED"),
        "message": str(raw.get("message") or "Provider validation failed."),
        "action": str(raw.get("action") or "Review provider access and retry."),
        "permissions": [
            str(item) for item in [*permissions, *apis] if str(item).strip()
        ],
    }


def _build_component_check(component: str, raw_result: Any) -> dict[str, Any]:
    result = raw_result if isinstance(raw_result, dict) else {}
    valid = bool(result.get("valid"))
    message = str(result.get("message") or "Validation did not return a message")
    permissions = result.get("permissions") or []
    if not isinstance(permissions, list):
        permissions = []

    if valid:
        return {
            "component": component,
            "status": "passed",
            "code": "OK",
            "message": message,
            "action": "No action required.",
            "permissions": [],
        }

    code, action = _classify_preflight_failure(message, permissions)
    return {
        "component": component,
        "status": "failed",
        "code": code,
        "message": message,
        "action": action,
        "permissions": permissions,
    }


def _classify_preflight_failure(
    message: str, permissions: list[str]
) -> tuple[str, str]:
    normalized = message.lower()
    if permissions:
        return (
            "MISSING_PERMISSIONS",
            "Grant the listed provider permissions to the deployment identity, then run preflight again.",
        )
    if "cannot connect" in normalized:
        return (
            "DOWNSTREAM_SERVICE_UNAVAILABLE",
            "Start the dependent local service or check the configured service URL.",
        )
    if "api error" in normalized:
        return (
            "DOWNSTREAM_API_ERROR",
            "Check the downstream service response and retry after the service is healthy.",
        )
    if "billing" in normalized:
        return (
            "BILLING_NOT_READY",
            "Enable or link billing for the selected cloud scope, then run preflight again.",
        )
    if "region" in normalized:
        return (
            "REGION_NOT_SUPPORTED",
            "Choose a supported region for this provider and deployment layer.",
        )
    return (
        "VALIDATION_FAILED",
        "Review the provider-specific validation message and update the CloudConnection before deployment.",
    )


def _collect_sensitive_values(*credential_payloads: dict[str, Any]) -> set[str]:
    sensitive_values: set[str] = set()
    for payload in credential_payloads:
        _collect_from_mapping(payload, sensitive_values)
    return sensitive_values


def _collect_from_mapping(
    value: Any, sensitive_values: set[str], parent_key: str = ""
) -> None:
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
