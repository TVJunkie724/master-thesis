"""Provider-parity tests for credential-checker secret redaction."""

from unittest.mock import patch

import pytest

from src.api.azure_credentials_checker import check_azure_credentials
from src.api.credentials_checker import check_aws_credentials
from src.api.gcp_credentials_checker import check_gcp_credentials


LEAKING_ERROR = RuntimeError(
    "client_secret=super-secret-value /app/upload/factory"
)


@pytest.mark.parametrize(
    ("checker", "credentials", "failure_target", "expected_message"),
    [
        (
            check_aws_credentials,
            {
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
                "aws_region": "eu-central-1",
            },
            "src.api.credentials_checker._create_session",
            "AWS credential validation failed unexpectedly. Check logs.",
        ),
        (
            check_azure_credentials,
            {
                "azure_subscription_id": "subscription",
                "azure_tenant_id": "tenant",
                "azure_client_id": "client",
                "azure_client_secret": "secret",
            },
            "src.api.azure_credentials_checker._create_credential",
            "Azure credential validation failed unexpectedly. Check logs.",
        ),
        (
            check_gcp_credentials,
            {
                "gcp_credentials_file": "{}",
                "gcp_region": "europe-west1",
                "gcp_project_id": "project",
            },
            "src.api.gcp_credentials_checker._parse_service_account_json",
            "GCP credential validation failed unexpectedly. Check logs.",
        ),
    ],
)
def test_unexpected_provider_errors_are_redacted(
    checker,
    credentials,
    failure_target,
    expected_message,
):
    logger_target = failure_target.rsplit(".", 1)[0] + ".logger.error"
    with patch(failure_target, side_effect=LEAKING_ERROR), patch(logger_target) as log_error:
        result = checker(credentials)

    assert result["status"] == "error"
    assert result["message"] == expected_message
    assert "super-secret-value" not in str(result)
    assert "/app/upload" not in str(result)
    assert log_error.call_args.args[1] == "client_secret=<redacted> <project-path>"
