"""Tests for deployment observability helpers."""

import logging

import pytest

from src.core.observability import OperationContext, operation_step, redact_sensitive


def test_operation_context_creates_operation_id_and_log_metadata():
    context = OperationContext.create(
        operation="deploy",
        project_name="factory",
        provider="google",
        operation_id="op-123",
    )

    assert context.with_provider("gcp").provider == "gcp"
    assert context.log_extra(phase="terraform_apply") == {
        "operation_id": "op-123",
        "operation": "deploy",
        "project_name": "factory",
        "provider": "google",
        "phase": "terraform_apply",
    }


def test_redact_sensitive_masks_paths_and_secret_fragments():
    raw = (
        "Project /app/upload/factory failed in "
        "/tmp/twin2multicloud-deployer-workspaces/factory-abc/terraform "
        "with client_secret='super-secret' SharedAccessKey=abc123 "
        "Authorization: Bearer token-value "
        "private_key=-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----"
    )

    redacted = redact_sensitive(raw)

    assert "/app/upload/factory" not in redacted
    assert "/tmp/twin2multicloud-deployer-workspaces" not in redacted
    assert "super-secret" not in redacted
    assert "abc123" not in redacted
    assert "token-value" not in redacted
    assert "BEGIN PRIVATE KEY" not in redacted
    assert "<project-path>" in redacted
    assert "<workspace-path>" in redacted


def test_operation_step_logs_success_with_duration(caplog):
    logger = logging.getLogger("test.operation.success")
    context = OperationContext.create(
        operation="deploy",
        project_name="factory",
        provider="aws",
        operation_id="op-123",
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        with operation_step(logger, context, "terraform_apply"):
            pass

    assert "Deployment phase started: terraform_apply" in caplog.text
    assert "Deployment phase completed: terraform_apply" in caplog.text
    assert "op-123" in [record.operation_id for record in caplog.records]


def test_operation_step_redacts_failure_message(caplog):
    logger = logging.getLogger("test.operation.failure")
    context = OperationContext.create(
        operation="deploy",
        project_name="factory",
        provider="aws",
        operation_id="op-123",
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        with pytest.raises(RuntimeError):
            with operation_step(logger, context, "terraform_apply"):
                raise RuntimeError("client_secret=super-secret in /app/upload/factory")

    assert "super-secret" not in caplog.text
    assert "/app/upload/factory" not in caplog.text
    assert "<project-path>" in caplog.text
