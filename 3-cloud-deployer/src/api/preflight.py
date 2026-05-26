"""Provider preflight normalization for deployment credential checks."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderName = Literal["aws", "azure", "gcp"]
PreflightStatus = Literal["passed", "failed", "warning", "skipped"]


class ProviderPreflightCheck(BaseModel):
    name: str = Field(..., description="Stable check name")
    status: PreflightStatus = Field(..., description="Normalized check status")
    code: str = Field(..., description="Machine-readable result code")
    message: str = Field(..., description="Secret-safe human-readable result")
    action: str = Field(..., description="Actionable next step")
    permissions: list[str] = Field(default_factory=list, description="Missing provider permissions/actions")
    apis: list[str] = Field(default_factory=list, description="Missing provider APIs")
    details: dict[str, Any] = Field(default_factory=dict, description="Secret-safe structured detail")


class ProviderPreflightResponse(BaseModel):
    provider: ProviderName
    ready: bool
    status: Literal["passed", "failed"]
    summary: str
    checks: list[ProviderPreflightCheck]


SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "credentials",
    "credential",
    "gcp_credentials_file",
    "aws_access_key_id",
    "aws_secret_access_key",
    "azure_client_secret",
)
REDACTION = "[REDACTED]"


def build_provider_preflight(
    provider: ProviderName,
    check_result: dict[str, Any],
    credential_payload: dict[str, Any] | None = None,
) -> ProviderPreflightResponse:
    """Convert provider-specific checker output into a stable preflight contract."""
    safe_result = redact_provider_result(check_result, credential_payload or {})
    checks = {
        "aws": _aws_checks,
        "azure": _azure_checks,
        "gcp": _gcp_checks,
    }[provider](safe_result)

    ready = bool(checks) and all(check.status in {"passed", "warning", "skipped"} for check in checks)
    return ProviderPreflightResponse(
        provider=provider,
        ready=ready,
        status="passed" if ready else "failed",
        summary=f"{provider.upper()} deployment preflight {'passed' if ready else 'failed'}",
        checks=checks,
    )


def redact_provider_result(result: Any, credential_payload: dict[str, Any]) -> Any:
    """Redact sensitive keys and known credential values from checker output."""
    sensitive_values = _collect_sensitive_values(credential_payload)
    return _redact_value(result, sensitive_values)


def _aws_checks(result: dict[str, Any]) -> list[ProviderPreflightCheck]:
    status = result.get("status")
    checks: list[ProviderPreflightCheck] = []

    if status == "valid":
        return [_passed("credentials", "AWS_READY", result.get("message") or "AWS credentials are ready.")]

    checks.extend(_region_checks(result.get("region_validation"), "aws_region"))

    account_status = _safe_dict(result.get("account_status"))
    if account_status.get("status") == "suspended":
        checks.append(_failed(
            "account_status",
            "ACCOUNT_NOT_ACTIVE",
            result.get("message") or "AWS account is not active.",
            "Reactivate the AWS account or choose another account before deployment.",
            details={"state": account_status.get("state")},
        ))

    missing_check = result.get("missing_check_permission")
    if missing_check:
        checks.append(_failed(
            "self_check_permissions",
            "SELF_CHECK_PERMISSION_MISSING",
            result.get("message") or "AWS credentials cannot inspect their own policies.",
            "Grant the listed self-check permission or use the bootstrap policy, then rerun preflight.",
            permissions=[str(missing_check)],
        ))

    missing_permissions = _aws_missing_permissions(result)
    if missing_permissions:
        checks.append(_failed(
            "deployment_permissions",
            "MISSING_PERMISSIONS",
            result.get("message") or "AWS deployment permissions are missing.",
            "Grant the listed AWS permissions to the deployment identity, then rerun preflight.",
            permissions=missing_permissions,
        ))

    if not checks:
        checks.append(_generic_failure(result, "aws"))
    return checks


def _azure_checks(result: dict[str, Any]) -> list[ProviderPreflightCheck]:
    status = result.get("status")
    checks: list[ProviderPreflightCheck] = []

    checks.extend(_region_checks(result.get("region_validation"), "azure_region"))

    expiration = _safe_dict(result.get("sp_credential_expiration"))
    if expiration.get("status") == "expired":
        checks.append(_failed(
            "credential_expiration",
            "CREDENTIAL_EXPIRED",
            expiration.get("message") or result.get("message") or "Azure client secret is expired.",
            "Rotate the Azure client secret and update the CloudConnection.",
        ))
    elif expiration.get("status") == "expiring_soon":
        checks.append(ProviderPreflightCheck(
            name="credential_expiration",
            status="warning",
            code="CREDENTIAL_EXPIRING_SOON",
            message=expiration.get("message") or "Azure client secret expires soon.",
            action="Rotate the Azure client secret soon to avoid deployment interruption.",
            details={"days_until_expiration": expiration.get("days_until_expiration")},
        ))

    if status == "valid":
        checks.insert(0, _passed("credentials", "AZURE_READY", result.get("message") or "Azure credentials are ready."))
        return checks

    message = str(result.get("message") or "")
    if "subscription" in message.lower() and "enabled" in message.lower():
        checks.append(_failed(
            "subscription_state",
            "SUBSCRIPTION_NOT_ENABLED",
            message,
            "Enable the Azure subscription or choose another subscription before deployment.",
        ))

    if status == "check_failed" or result.get("can_list_roles") is False and "role assignments" in message.lower():
        checks.append(_failed(
            "role_assignment_check",
            "ROLE_ASSIGNMENT_CHECK_UNAVAILABLE",
            message or "Azure role assignments cannot be inspected.",
            "Grant Reader or equivalent role-assignment read access at subscription scope, then rerun preflight.",
        ))

    missing_actions = _azure_missing_actions(result)
    if missing_actions:
        checks.append(_failed(
            "deployment_permissions",
            "MISSING_PERMISSIONS",
            message or "Azure deployment permissions are missing.",
            "Grant the listed Azure actions via the custom deployer role or required built-in roles.",
            permissions=missing_actions,
        ))

    if not checks:
        checks.append(_generic_failure(result, "azure"))
    return checks


def _gcp_checks(result: dict[str, Any]) -> list[ProviderPreflightCheck]:
    status = result.get("status")
    checks: list[ProviderPreflightCheck] = []

    if status == "valid":
        return [_passed("credentials", "GCP_READY", result.get("message") or "GCP credentials are ready.")]

    checks.extend(_region_checks(result.get("region_validation"), "gcp_region"))

    project_access = _safe_dict(result.get("project_access"))
    if project_access.get("status") == "access_denied":
        checks.append(_failed(
            "project_access",
            "PROJECT_ACCESS_DENIED",
            result.get("message") or project_access.get("error") or "GCP project access denied.",
            "Grant project access to the service account or choose the correct project.",
        ))
    elif project_access.get("status") == "not_found":
        checks.append(_failed(
            "project_access",
            "PROJECT_NOT_FOUND",
            result.get("message") or project_access.get("error") or "GCP project not found.",
            "Verify the GCP project ID and service account project scope.",
        ))
    elif project_access.get("status") == "accessible" and project_access.get("state") not in {None, "ACTIVE"}:
        checks.append(_failed(
            "project_state",
            "PROJECT_NOT_ACTIVE",
            result.get("message") or f"GCP project is {project_access.get('state')}.",
            "Use an ACTIVE GCP project before deployment.",
            details={"state": project_access.get("state")},
        ))

    billing_status = _safe_dict(result.get("billing_status"))
    if billing_status.get("status") == "checked" and billing_status.get("billing_enabled") is False:
        checks.append(_failed(
            "billing",
            "BILLING_NOT_ENABLED",
            result.get("message") or "GCP billing is not enabled.",
            "Enable billing for the GCP project, then rerun preflight.",
        ))

    api_status = _safe_dict(result.get("api_status"))
    missing_apis = _gcp_missing_apis(api_status)
    if missing_apis:
        checks.append(_failed(
            "enabled_apis",
            "MISSING_APIS",
            result.get("message") or "Required GCP APIs are not enabled.",
            "Enable the listed GCP APIs, then rerun preflight.",
            apis=missing_apis,
        ))

    if status == "sdk_missing":
        checks.append(_failed(
            "service_dependencies",
            "SDK_MISSING",
            result.get("message") or "GCP SDK dependency is missing in the Deployer runtime.",
            "Install the missing Deployer dependency or rebuild the Deployer image.",
        ))

    if not checks:
        checks.append(_generic_failure(result, "gcp"))
    return checks


def _region_checks(region_validation: Any, default_name: str) -> list[ProviderPreflightCheck]:
    validation = _safe_dict(region_validation)
    checks = []
    for name, result in validation.items() or [(default_name, validation)]:
        result_dict = _safe_dict(result)
        if result_dict and result_dict.get("valid") is False and not result_dict.get("skipped"):
            checks.append(_failed(
                name,
                "REGION_NOT_SUPPORTED",
                result_dict.get("error") or f"Region check failed for {name}.",
                "Choose a supported region for this provider and deployment layer.",
                details={"region": result_dict.get("region")},
            ))
    return checks


def _aws_missing_permissions(result: dict[str, Any]) -> list[str]:
    missing = set()
    by_service = _safe_dict(result.get("by_service"))
    for service_result in by_service.values():
        for permission in _safe_dict(service_result).get("missing", []) or []:
            missing.add(str(permission))
    return sorted(missing)


def _azure_missing_actions(result: dict[str, Any]) -> list[str]:
    missing = set()
    by_layer = _safe_dict(result.get("by_layer"))
    for layer_result in by_layer.values():
        for action in _safe_dict(layer_result).get("missing_actions", []) or []:
            missing.add(str(action))
    return sorted(missing)


def _gcp_missing_apis(api_status: dict[str, Any]) -> list[str]:
    missing = set()
    by_layer = _safe_dict(api_status.get("by_layer"))
    for layer_result in by_layer.values():
        for api in _safe_dict(layer_result).get("missing_apis", []) or []:
            missing.add(str(api))
    return sorted(missing)


def _passed(name: str, code: str, message: str) -> ProviderPreflightCheck:
    return ProviderPreflightCheck(
        name=name,
        status="passed",
        code=code,
        message=message,
        action="No action required.",
    )


def _failed(
    name: str,
    code: str,
    message: str,
    action: str,
    *,
    permissions: list[str] | None = None,
    apis: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> ProviderPreflightCheck:
    return ProviderPreflightCheck(
        name=name,
        status="failed",
        code=code,
        message=message,
        action=action,
        permissions=permissions or [],
        apis=apis or [],
        details=details or {},
    )


def _generic_failure(result: dict[str, Any], provider: str) -> ProviderPreflightCheck:
    return _failed(
        "provider_validation",
        "VALIDATION_FAILED",
        result.get("message") or f"{provider.upper()} credential validation failed.",
        "Review the provider validation message and update the deployment identity before deployment.",
    )


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _collect_sensitive_values(value: Any, parent_key: str = "") -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if isinstance(item, str) and (_is_sensitive_key(key_text) or _is_sensitive_key(parent_key)):
                _add_sensitive_value(item, values)
                values.update(_collect_json_sensitive_values(item))
            values.update(_collect_sensitive_values(item, key_text))
    elif isinstance(value, list):
        for item in value:
            values.update(_collect_sensitive_values(item, parent_key))
    elif isinstance(value, str) and _is_sensitive_key(parent_key):
        _add_sensitive_value(value, values)
        values.update(_collect_json_sensitive_values(value))
    return values


def _collect_json_sensitive_values(raw: str) -> set[str]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return set()
    return _collect_sensitive_values(parsed)


def _redact_value(value: Any, sensitive_values: set[str], parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {key: _redact_value(item, sensitive_values, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, sensitive_values, parent_key) for item in value]
    if isinstance(value, str):
        if _is_sensitive_key(parent_key):
            return REDACTION
        return _redact_string(value, sensitive_values)
    return value


def _redact_string(value: str, sensitive_values: set[str]) -> str:
    redacted = value
    for sensitive_value in sorted(sensitive_values, key=len, reverse=True):
        redacted = redacted.replace(sensitive_value, REDACTION)
    return redacted


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _add_sensitive_value(value: str, values: set[str]) -> None:
    if len(value) >= 8:
        values.add(value)
