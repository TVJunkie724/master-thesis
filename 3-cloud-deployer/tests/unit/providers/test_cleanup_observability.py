"""Tests for fail-closed provider cleanup error normalization."""

import logging

import pytest

from src.providers import cleanup_registry
from src.providers.aws import cleanup as aws_cleanup
from src.providers.cleanup_observability import (
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


def test_registry_wrapper_fails_closed_when_legacy_cleanup_swallows_error(
    monkeypatch,
    caplog,
):
    def swallowed_failure(*args, **kwargs):
        aws_cleanup.logger.warning(
            "Deletion failed: aws_secret_access_key=super-secret-value"
        )

    monkeypatch.setattr(aws_cleanup, "cleanup_aws_resources", swallowed_failure)

    with (
        caplog.at_level("WARNING", logger=aws_cleanup.logger.name),
        pytest.raises(ProviderCleanupError),
    ):
        cleanup_registry.cleanup_aws_resources({}, "factory", dry_run=True)

    assert "super-secret-value" not in caplog.text
