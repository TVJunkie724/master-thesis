"""Shared validation calls for cloud credential payloads."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from src.clients.deployer_client import DeployerClient
from src.clients.optimizer_client import OptimizerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.secret_redaction import redact_secret_like_text

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


async def perform_optimizer_validation(
    provider: str,
    optimizer_creds: dict,
    *,
    optimizer_client: OptimizerClient | None = None,
) -> dict:
    """Validate pricing access through the Optimizer boundary only."""
    optimizer_client = optimizer_client or OptimizerClient()
    try:
        raw = await optimizer_client.verify_permissions(provider, optimizer_creds)
        optimizer = {
            "valid": raw.get("valid", False) or raw.get("status") == "valid",
            "message": raw.get("message", "Validation complete"),
        }
    except ExternalServiceUnavailable:
        optimizer = {
            "valid": False,
            "message": "Cannot connect to Optimizer API (port 5003)",
        }
    except ExternalServiceError as exc:
        optimizer = {
            "valid": False,
            "message": f"Optimizer API error: {exc.upstream_status_code or 502}",
        }
    except Exception as exc:
        optimizer = {
            "valid": False,
            "message": f"Optimizer error: {redact_secret_like_text(str(exc))}",
        }

    return redact_validation_result(
        {
            "provider": provider,
            "valid": optimizer["valid"],
            "optimizer": optimizer,
            "deployer": None,
        },
        optimizer_creds,
    )


async def perform_dual_validation(
    provider: str,
    optimizer_creds: dict,
    deployer_creds: dict,
    *,
    optimizer_client: OptimizerClient | None = None,
    deployer_client: DeployerClient | None = None,
) -> dict:
    """Validate credentials against Optimizer and Deployer without persisting secrets."""
    optimizer_client = optimizer_client or OptimizerClient()
    deployer_client = deployer_client or DeployerClient()

    async def call_optimizer():
        try:
            result = await optimizer_client.verify_permissions(provider, optimizer_creds)
            is_valid = result.get("valid", False) or result.get("status") == "valid"
            return {
                "valid": is_valid,
                "message": result.get("message", "Validation complete"),
            }
        except ExternalServiceUnavailable:
            return {
                "valid": False,
                "message": "Cannot connect to Optimizer API (port 5003)",
            }
        except ExternalServiceError as exc:
            return {
                "valid": False,
                "message": f"Optimizer API error: {exc.upstream_status_code or 502}",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"Optimizer error: {redact_secret_like_text(str(exc))}",
            }

    async def call_deployer():
        try:
            result = await deployer_client.verify_permissions(provider, deployer_creds)
            is_valid = result.get("valid", False) or result.get("status") == "valid"
            return {
                "valid": is_valid,
                "message": result.get("message", "Validation complete"),
                "permissions": result.get("missing_permissions"),
            }
        except ExternalServiceUnavailable:
            return {
                "valid": False,
                "message": "Cannot connect to Deployer API (port 5004)",
            }
        except ExternalServiceError as exc:
            return {
                "valid": False,
                "message": f"Deployer API error: {exc.upstream_status_code or 502}",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"Deployer error: {redact_secret_like_text(str(exc))}",
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


def build_preflight_result(
    provider: str,
    validation_result: dict[str, Any],
    *,
    version_comparison=None,
) -> dict[str, Any]:
    """Normalize raw Optimizer/Deployer validation into UI-actionable preflight checks."""
    checks = [
        _build_component_check("optimizer", validation_result.get("optimizer")),
        _build_component_check("deployer", validation_result.get("deployer")),
    ]
    if version_comparison is not None and not version_comparison.matches:
        checks.insert(0, _permission_set_check(version_comparison))
    ready = all(check["status"] == "passed" for check in checks)
    return {
        "provider": provider,
        "ready": ready,
        "summary": "Cloud connection preflight passed" if ready else "Cloud connection preflight failed",
        "checks": checks,
    }


def _permission_set_check(version_comparison) -> dict[str, Any]:
    supplied = version_comparison.supplied_version or "missing"
    return {
        "component": "deployer",
        "status": "failed",
        "code": "OUTDATED_PERMISSION_SET",
        "message": (
            f"{version_comparison.provider.upper()} CloudConnection uses permission set "
            f"'{supplied}', but the active baseline is "
            f"'{version_comparison.expected_version}'."
        ),
        "action": (
            "Re-run provider bootstrap or rotate/import the CloudConnection with "
            f"permission_set_version={version_comparison.expected_version}."
        ),
        "permissions": [],
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


def _classify_preflight_failure(message: str, permissions: list[str]) -> tuple[str, str]:
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
