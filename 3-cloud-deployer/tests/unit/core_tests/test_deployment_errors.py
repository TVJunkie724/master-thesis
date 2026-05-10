"""Tests for typed deployment error mapping."""

from src.core.deployment_errors import (
    DeploymentBoundaryError,
    DeploymentErrorCode,
    WorkspaceSyncError,
    classify_deployment_error,
    client_error_payload,
)
from src.core.observability import OperationContext
from src.terraform_runner import TerraformError


def _operation(operation: str = "deploy") -> OperationContext:
    return OperationContext.create(
        operation=operation,
        project_name="factory",
        provider="aws",
        operation_id="op-123",
    )


def test_validation_error_maps_to_400_payload_with_redaction():
    error = ValueError("Project directory not found: /app/upload/factory")

    payload = client_error_payload(error, _operation())

    assert payload["error_code"] == "VALIDATION_ERROR"
    assert payload["http_status"] == 400
    assert payload["operation_id"] == "op-123"
    assert "/app/upload/factory" not in payload["message"]
    assert "<project-path>" in payload["message"]


def test_terraform_error_maps_to_stable_safe_message():
    error = TerraformError("apply", 1, "client_secret=super-secret")

    payload = client_error_payload(error, _operation())

    assert payload["error_code"] == "TERRAFORM_ERROR"
    assert payload["http_status"] == 500
    assert "super-secret" not in payload["message"]
    assert payload["message"] == "Terraform operation failed. Check server logs for redacted diagnostics."


def test_workspace_sync_error_uses_specific_error_code():
    error = WorkspaceSyncError("failed syncing /tmp/twin2multicloud-deployer-workspaces/factory")

    payload = client_error_payload(error, _operation())

    assert payload["error_code"] == "WORKSPACE_SYNC_ERROR"
    assert payload["http_status"] == 500
    assert "<workspace-path>" not in payload["message"]
    assert payload["message"] == "Deployment runtime output sync failed. Check server logs."


def test_destroy_runtime_error_maps_to_destruction_error():
    code, status = classify_deployment_error(RuntimeError("boom"), "destroy")

    assert code == DeploymentErrorCode.destruction_error
    assert status == 500


def test_boundary_error_keeps_declared_code_and_status():
    error = DeploymentBoundaryError(
        "custom",
        code=DeploymentErrorCode.unexpected_error,
        status_code=503,
    )

    code, status = classify_deployment_error(error, "deploy")

    assert code == DeploymentErrorCode.unexpected_error
    assert status == 503
