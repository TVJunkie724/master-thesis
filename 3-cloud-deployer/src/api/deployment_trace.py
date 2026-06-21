"""Sanitization helpers for deployment stream events."""

import re
from enum import Enum
from typing import Any

from src.terraform_output_policy import TerraformOutputVisibility, classify_terraform_output


REDACTED_VALUE = "[REDACTED]"
GENERIC_REDACTED_MESSAGE = "Sensitive deployment detail redacted. Check logs."


class DeploymentErrorCategory(str, Enum):
    """User-safe deployment error categories."""

    validation = "validation"
    packaging = "packaging"
    terraform = "terraform"
    provider_sdk = "provider_sdk"
    cleanup = "cleanup"
    permission = "permission"
    timeout = "timeout"
    internal = "internal"


_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "connection_string",
    "password",
    "secret",
    "token",
)

_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(\b[\w.-]*(?:api[_-]?key|connection[_-]?string|password|secret|token)[\w.-]*\b"
    r"\s*[:=]\s*[\"']?)([^\"',\s}]+)([\"']?)"
)


def _contains_secret_marker(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in _SECRET_MARKERS)


def sanitize_deployment_message(message: str) -> str:
    """Redact secret-like deployment log or error messages."""
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED_VALUE}{match.group(3)}",
        message,
    )
    if _contains_secret_marker(sanitized):
        return GENERIC_REDACTED_MESSAGE
    return sanitized


def classify_deployment_error(error: str) -> DeploymentErrorCategory:
    """Classify deployment errors for Management API and Flutter handling."""
    normalized = error.lower()
    permission_markers = ("permission", "forbidden", "unauthorized", "denied", "credential")
    if any(marker in normalized for marker in permission_markers):
        return DeploymentErrorCategory.permission
    if any(marker in normalized for marker in ("timeout", "timed out")):
        return DeploymentErrorCategory.timeout
    if any(marker in normalized for marker in ("validation", "invalid", "schema")):
        return DeploymentErrorCategory.validation
    if any(marker in normalized for marker in ("package", "packaging", "bundle", "zip")):
        return DeploymentErrorCategory.packaging
    if "terraform" in normalized:
        return DeploymentErrorCategory.terraform
    if "cleanup" in normalized:
        return DeploymentErrorCategory.cleanup
    if any(marker in normalized for marker in ("provider", "sdk", "boto3", "azure", "gcp", "aws")):
        return DeploymentErrorCategory.provider_sdk
    return DeploymentErrorCategory.internal


def sanitize_terraform_outputs(outputs: dict[str, Any] | None) -> dict[str, Any] | None:
    """Redact secret-classified Terraform outputs while preserving shape."""
    if outputs is None:
        return None

    sanitized: dict[str, Any] = {}
    for name, value in outputs.items():
        policy = classify_terraform_output(name)
        sanitized[name] = (
            REDACTED_VALUE
            if policy.visibility == TerraformOutputVisibility.REDACTED
            else value
        )
    return sanitized
