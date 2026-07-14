"""Tests for fail-closed provider cleanup error normalization."""

import logging

import pytest

from src.providers import cleanup_registry
from src.providers.aws import cleanup as aws_cleanup
from src.providers.cleanup_observability import (
    CleanupRun,
    ProviderCleanupError,
    enforce_cleanup_outcome,
)


def test_cleanup_warning_becomes_sanitized_provider_failure():
    logger = logging.getLogger("test.cleanup.failure")

    with pytest.raises(ProviderCleanupError) as exc_info:
        with enforce_cleanup_outcome(logger, "AWS"):
            logger.warning(
                "Deletion failed: aws_secret_access_key=super-secret-value"
            )

    assert "super-secret-value" not in str(exc_info.value)
    assert "Sensitive deployment detail redacted" in str(exc_info.value)


def test_non_failure_retry_warning_does_not_fail_cleanup():
    logger = logging.getLogger("test.cleanup.retry")

    with enforce_cleanup_outcome(logger, "AWS"):
        logger.warning("Retry 1/3 after eventual-consistency response")


def test_idempotent_not_found_warning_does_not_fail_cleanup():
    logger = logging.getLogger("test.cleanup.not-found")

    with enforce_cleanup_outcome(logger, "AWS"):
        logger.warning("Resource not found; it was already deleted")


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
        (),
    )

    def failed_cleanup(*args, **kwargs):
        raise failure

    monkeypatch.setattr(aws_cleanup, "cleanup_aws_resources", failed_cleanup)

    with pytest.raises(ProviderCleanupError) as exc_info:
        cleanup_registry.cleanup_aws_resources({}, "factory", dry_run=True)

    assert exc_info.value is failure
