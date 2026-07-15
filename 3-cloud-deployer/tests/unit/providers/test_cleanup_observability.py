"""Tests for fail-closed provider cleanup error normalization."""

import logging

import pytest

from src.providers import cleanup_registry
from src.providers.aws import cleanup as aws_cleanup
from src.providers.cleanup_observability import (
    CleanupFailure,
    CleanupRun,
    ProviderCleanupError,
)


def test_cleanup_run_aggregates_sanitized_failures_and_continues(caplog):
    logger = logging.getLogger("test.cleanup.typed")
    run = CleanupRun("AWS", logger)
    calls = []

    with caplog.at_level("WARNING", logger=logger.name):
        run.attempt(
            "S3",
            "factory-bucket",
            lambda: (_ for _ in ()).throw(
                RuntimeError("aws_secret_access_key=super-secret-value")
            ),
        )
        run.attempt("Lambda", "factory-function", lambda: calls.append("continued"))

    with pytest.raises(ProviderCleanupError) as exc_info:
        run.raise_if_failed()

    assert calls == ["continued"]
    assert exc_info.value.provider == "AWS"
    assert exc_info.value.failures[0].step == "S3"
    assert "super-secret-value" not in str(exc_info.value)
    assert "super-secret-value" not in caplog.text


def test_registry_propagates_typed_provider_cleanup_failure(monkeypatch):
    failure = ProviderCleanupError(
        "AWS",
        (
            CleanupFailure(
                step="S3",
                resource="factory-bucket",
                error_type="RuntimeError",
                detail="delete failed",
            ),
        ),
    )

    def failed_cleanup(*args, **kwargs):
        raise failure

    monkeypatch.setattr(aws_cleanup, "cleanup_aws_resources", failed_cleanup)

    with pytest.raises(ProviderCleanupError) as exc_info:
        cleanup_registry.cleanup_aws_resources({}, "factory", dry_run=True)

    assert exc_info.value is failure
