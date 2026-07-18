"""Typed deployment error mapping and safe client payloads."""

from __future__ import annotations

from enum import Enum
from typing import Any

from src.core.observability import OperationContext, redact_sensitive
from src.deployment_specification.errors import DeploymentSpecificationError
from src.terraform_runner import TerraformError


class DeploymentErrorCode(str, Enum):
    validation_error = "VALIDATION_ERROR"
    deployment_error = "DEPLOYMENT_ERROR"
    destruction_error = "DESTRUCTION_ERROR"
    terraform_error = "TERRAFORM_ERROR"
    workspace_sync_error = "WORKSPACE_SYNC_ERROR"
    unexpected_error = "UNEXPECTED_ERROR"


class DeploymentBoundaryError(Exception):
    """Base error for failures that cross the deployer boundary."""

    def __init__(
        self,
        message: str,
        *,
        code: DeploymentErrorCode = DeploymentErrorCode.deployment_error,
        status_code: int = 500,
    ):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class WorkspaceSyncError(DeploymentBoundaryError):
    """Raised when durable runtime outputs cannot be synced safely."""

    def __init__(self, message: str):
        super().__init__(
            message,
            code=DeploymentErrorCode.workspace_sync_error,
            status_code=500,
        )


def classify_deployment_error(error: Exception, operation: str) -> tuple[DeploymentErrorCode, int]:
    """Return a stable error code and HTTP status for a deployment exception."""
    if isinstance(error, DeploymentBoundaryError):
        return error.code, error.status_code
    if isinstance(error, ValueError):
        return DeploymentErrorCode.validation_error, 400
    if isinstance(error, TerraformError):
        return DeploymentErrorCode.terraform_error, 500
    if operation == "destroy":
        return DeploymentErrorCode.destruction_error, 500
    if operation == "deploy":
        return DeploymentErrorCode.deployment_error, 500
    return DeploymentErrorCode.unexpected_error, 500


def client_error_payload(
    error: Exception,
    operation_context: OperationContext,
    *,
    fallback_message: str | None = None,
) -> dict[str, Any]:
    """Build a safe, machine-readable error payload for HTTP and SSE clients."""
    code, status_code = classify_deployment_error(error, operation_context.operation)
    message = fallback_message or _client_message(error, code)
    public_error_code = (
        error.code
        if isinstance(error, DeploymentSpecificationError)
        else code.value
    )
    return {
        "error_code": public_error_code,
        "message": redact_sensitive(message),
        "operation_id": operation_context.operation_id,
        "operation": operation_context.operation,
        "project_name": operation_context.project_name,
        "provider": operation_context.provider,
        "http_status": status_code,
    }


def _client_message(error: Exception, code: DeploymentErrorCode) -> str:
    if code == DeploymentErrorCode.validation_error:
        return f"Validation failed: {error}"
    if code == DeploymentErrorCode.terraform_error:
        return "Terraform operation failed. Check server logs for redacted diagnostics."
    if code == DeploymentErrorCode.workspace_sync_error:
        return "Deployment runtime output sync failed. Check server logs."
    if code == DeploymentErrorCode.destruction_error:
        return "Destruction operation failed. Check server logs."
    if code == DeploymentErrorCode.deployment_error:
        return "Deployment operation failed. Check server logs."
    return "Unexpected deployment error. Check server logs."
